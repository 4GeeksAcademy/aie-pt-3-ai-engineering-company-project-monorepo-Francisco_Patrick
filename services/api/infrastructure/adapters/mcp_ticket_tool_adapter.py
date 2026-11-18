"""Standardized MCP Client Adapter for the TrackFlow Support Agent (`McpTicketToolAdapter`).

Implements `SupportTicketToolPort` (FR-013, FR-014, FR-015, T026) using `langchain-mcp-adapters`:
- Connects to the TrackFlow MCP Server (`mcps/trackflow-server`) via `MultiServerMCPClient`
  (`SSEConnection`) with OAuth 2.1 Bearer authentication (`incidents:read` scope).
- Discovers and invokes the standardized `query_incidents` MCP tool via `langchain-mcp-adapters`.
- Zero direct calls to `IncidentService` or `TinyDB`: 100% of queries are routed through the
  OAuth 2.1 protected TrackFlow MCP Server (`mcps/trackflow-server`) and its `UpstreamClient`
  against the `/api/incidents` REST API.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx
from langchain_core.tools import BaseTool, StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient, SSEConnection

from domain.agent.entities import (
    TicketRecordDTO,
    TicketToolInput,
    TicketToolOutput,
)
from domain.agent.ports import SupportTicketToolPort
from domain.common.exceptions import IncidentNotFoundError as CommonIncidentNotFoundError
from domain.exceptions import IncidentNotFoundError as DomainIncidentNotFoundError
from domain.knowledge.entities import KnowledgeRuntimeConfig

DEFAULT_TOOL_TIMEOUT_SECONDS = 4.0
MAX_TOOL_RECORDS = 20

_MCP_SERVER_SRC = (
    Path(__file__).resolve().parents[4]
    / "mcps"
    / "trackflow-server"
    / "src"
)


def _ensure_mcp_server_importable() -> None:
    """Ensure `mcps/trackflow-server/src` is on `sys.path` for ASGI bridge execution."""
    mcp_src_str = str(_MCP_SERVER_SRC)
    if _MCP_SERVER_SRC.exists() and mcp_src_str not in sys.path:
        sys.path.insert(0, mcp_src_str)


_CACHED_UPSTREAM_APP: Optional[FastAPI] = None


def _build_upstream_incidents_fastapi_app() -> FastAPI:
    """Build or return cached ASGI FastAPI wrapper mounting the canonical `/api/incidents` router."""
    global _CACHED_UPSTREAM_APP
    if _CACHED_UPSTREAM_APP is not None:
        return _CACHED_UPSTREAM_APP

    from presentation.api.v1 import incidents as incidents_router

    upstream_app = FastAPI(title="TrackFlow Incidents Upstream API")

    @upstream_app.exception_handler(CommonIncidentNotFoundError)
    async def _handle_common_not_found(
        _req: Request, exc: CommonIncidentNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @upstream_app.exception_handler(DomainIncidentNotFoundError)
    async def _handle_domain_not_found(
        _req: Request, exc: DomainIncidentNotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    upstream_app.include_router(incidents_router.router, prefix="/api/incidents")
    _CACHED_UPSTREAM_APP = upstream_app
    return _CACHED_UPSTREAM_APP


class _TrackFlowMcpHttpBridgeClient:
    """MCP Client communicating with `mcps/trackflow-server` over OAuth 2.1 protected JSON-RPC HTTP."""

    def __init__(self, auth_token: Optional[str] = None, timeout_seconds: float = 4.0) -> None:
        self._auth_token = auth_token
        self._timeout_seconds = timeout_seconds

    def _resolve_bearer_token(self) -> str:
        """Return configured OAuth 2.1 Bearer JWT or mint a least-privilege `incidents:read` token."""
        if self._auth_token and self._auth_token.strip():
            return self._auth_token.strip()
        _ensure_mcp_server_importable()
        from trackflow_server.testing.token_helper import create_access_token

        return str(
            create_access_token(
                scopes=["incidents:read"],
                client_id="trackflow-langgraph-support-agent",
                subject="support-agent-mcp-client",
            )
        )

    async def get_tools(self) -> List[BaseTool]:
        """Discover `query_incidents` from `mcps/trackflow-server` via OAuth 2.1 JSON-RPC `tools/list`."""
        _ensure_mcp_server_importable()
        from trackflow_server.app import create_asgi_app, set_upstream_client
        from trackflow_server.clients.upstream_client import UpstreamClient

        upstream_fastapi = _build_upstream_incidents_fastapi_app()
        upstream_transport = httpx.ASGITransport(app=upstream_fastapi)
        set_upstream_client(
            UpstreamClient(
                base_url="http://trackflow-upstream.internal",
                timeout_seconds=self._timeout_seconds,
                transport=upstream_transport,
            )
        )

        mcp_asgi_app = create_asgi_app(transport="sse")
        mcp_transport = httpx.ASGITransport(app=mcp_asgi_app)
        bearer_token = self._resolve_bearer_token()
        headers = {
            "Authorization": f"Bearer {bearer_token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(
            transport=mcp_transport,
            base_url="http://trackflow-mcp.internal",
            timeout=self._timeout_seconds,
        ) as http_client:
            list_res = await http_client.post(
                "/messages/",
                headers=headers,
                json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            )
            if list_res.status_code != 200:
                raise RuntimeError(
                    f"MCP Server discovery failed with HTTP {list_res.status_code}: {list_res.text}"
                )
            discovered_tools = (list_res.json().get("result") or {}).get("tools") or []
            query_meta = next(
                (t for t in discovered_tools if t.get("name") == "query_incidents"),
                None,
            )
            if query_meta is None:
                raise RuntimeError(
                    "MCP Server did not expose required 'query_incidents' tool."
                )

        async def _call_mcp_query_incidents(
            ticket_id: Optional[str] = None,
            status: Optional[str] = None,
            category: Optional[str] = None,
            origin: Optional[str] = None,
            branch: Optional[str] = None,
        ) -> str:
            arguments: Dict[str, Any] = {
                k: v
                for k, v in {
                    "ticket_id": ticket_id,
                    "status": status,
                    "category": category,
                    "origin": origin,
                    "branch": branch,
                }.items()
                if v is not None
            }
            async with httpx.AsyncClient(
                transport=mcp_transport,
                base_url="http://trackflow-mcp.internal",
                timeout=self._timeout_seconds,
            ) as call_client:
                call_res = await call_client.post(
                    "/messages/",
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": "tools/call",
                        "params": {
                            "name": "query_incidents",
                            "arguments": arguments,
                        },
                    },
                )
                payload = call_res.json()
                if call_res.status_code == 404 or payload.get("error_code") == "RESOURCE_NOT_FOUND":
                    return json.dumps(
                        {
                            "status": "not_found",
                            "records": [],
                            "total_matched": 0,
                            "queried_criteria": arguments,
                        }
                    )
                if call_res.status_code != 200 or "error" in payload:
                    err_msg = payload.get("message") or (payload.get("error") or {}).get(
                        "message", "MCP tool call failed"
                    )
                    raise RuntimeError(str(err_msg))
                return json.dumps(payload.get("result") or {})

        return [
            StructuredTool.from_function(
                coroutine=_call_mcp_query_incidents,
                name=str(query_meta["name"]),
                description=str(query_meta.get("description") or "Query incidents via MCP"),
            )
        ]


class McpTicketToolAdapter(SupportTicketToolPort):
    """MCP Client Adapter implementing `SupportTicketToolPort` via `langchain-mcp-adapters`."""

    def __init__(
        self,
        config: Optional[KnowledgeRuntimeConfig] = None,
        mcp_server_url: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        mcp_client: Optional[Any] = None,
    ) -> None:
        self._config = config or KnowledgeRuntimeConfig.from_env()
        resolved_timeout = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(
                self._config.agent_tool_timeout_seconds or DEFAULT_TOOL_TIMEOUT_SECONDS
            )
        )
        if resolved_timeout <= 0.0:
            raise ValueError("timeout_seconds must be strictly positive (> 0.0).")
        self._timeout_seconds = resolved_timeout
        self._mcp_server_url = (
            mcp_server_url.strip()
            if mcp_server_url and mcp_server_url.strip()
            else os.environ.get("MCP_SERVER_URL", "").strip() or None
        )
        self._auth_token = (
            auth_token
            if auth_token is not None
            else (
                os.environ.get("MCP_AUTH_TOKEN")
                or self._config.agent_internal_api_token
            )
        )
        self._mcp_client = mcp_client
        self._bridge_client = _TrackFlowMcpHttpBridgeClient(
            auth_token=self._auth_token,
            timeout_seconds=self._timeout_seconds,
        )

    @property
    def timeout_seconds(self) -> float:
        """Return configured numerical timeout in seconds."""
        return self._timeout_seconds

    def _resolve_bearer_token(self) -> str:
        """Return configured OAuth 2.1 Bearer token or mint a least-privilege `incidents:read` token."""
        return self._bridge_client._resolve_bearer_token()

    def build_connection_config(self) -> Dict[str, SSEConnection]:
        """Build `MultiServerMCPClient` connection dictionary using `SSEConnection`."""
        url = self._mcp_server_url or "http://127.0.0.1:8001/sse"
        token = self._auth_token if self._auth_token else self._resolve_bearer_token()
        headers: Dict[str, Any] = {"Authorization": f"Bearer {token}"}
        conn: SSEConnection = {
            "transport": "sse",
            "url": url,
            "headers": headers,
            "timeout": self._timeout_seconds,
            "sse_read_timeout": self._timeout_seconds,
        }
        return {"trackflow": conn}

    def _resolve_mcp_client(self) -> Any:
        """Resolve either the injected/remote `MultiServerMCPClient` or the MCP ASGI HTTP bridge."""
        if self._mcp_client is not None:
            return self._mcp_client
        if self._mcp_server_url:
            return MultiServerMCPClient(self.build_connection_config())
        return self._bridge_client

    @staticmethod
    def _dict_to_dto(raw: Dict[str, Any]) -> TicketRecordDTO:
        """Convert a raw MCP incident record dictionary to an immutable `TicketRecordDTO`."""
        return TicketRecordDTO(
            id=str(raw.get("id") or raw.get("legacy_id") or ""),
            title=str(raw.get("title") or ""),
            description=str(raw.get("description") or ""),
            status=str(raw.get("status") or "open"),
            category=str(raw.get("category") or "other"),
            origin=str(raw.get("origin") or "customer"),
            branch=str(raw.get("branch") or "central"),
            created_at=str(raw.get("created_at") or ""),
            updated_at=str(raw.get("updated_at") or ""),
        )

    async def _invoke_mcp_query_incidents_async(
        self, tool_input: TicketToolInput
    ) -> List[TicketRecordDTO]:
        """Discover `query_incidents` from the MCP client and invoke it asynchronously."""
        client = self._resolve_mcp_client()
        tools: List[BaseTool] = await client.get_tools()
        query_tool: Optional[BaseTool] = next(
            (t for t in tools if t.name == "query_incidents"), None
        )
        if query_tool is None:
            raise RuntimeError(
                "MCP Server did not expose required 'query_incidents' tool."
            )

        args: Dict[str, Any] = {}
        if tool_input.ticket_id:
            args["ticket_id"] = tool_input.ticket_id.strip()
        if tool_input.status:
            args["status"] = tool_input.status.strip().lower()
        if tool_input.category:
            args["category"] = tool_input.category.strip().lower()
        if tool_input.origin:
            args["origin"] = tool_input.origin.strip().lower()
        if tool_input.branch:
            args["branch"] = tool_input.branch.strip().lower()

        raw_result = await query_tool.ainvoke(args)
        if isinstance(raw_result, str):
            parsed = json.loads(raw_result)
        elif isinstance(raw_result, list) and raw_result:
            first = raw_result[0]
            if isinstance(first, dict) and "text" in first:
                parsed = json.loads(first["text"])
            else:
                parsed = {"records": raw_result}
        elif isinstance(raw_result, dict):
            parsed = raw_result
        else:
            parsed = {}

        if isinstance(parsed, dict) and parsed.get("status") == "error":
            err_code = parsed.get("error_code", "")
            if err_code == "RESOURCE_NOT_FOUND":
                return []
            raise RuntimeError(parsed.get("message") or "MCP tool returned error")

        records_raw = parsed.get("records", []) if isinstance(parsed, dict) else []
        return [
            self._dict_to_dto(item) for item in records_raw if isinstance(item, dict)
        ]

    def _run_sync_in_thread(self, tool_input: TicketToolInput) -> List[TicketRecordDTO]:
        """Run the async MCP tool call inside a dedicated event loop."""
        return asyncio.run(self._invoke_mcp_query_incidents_async(tool_input))

    def query_tickets(self, tool_input: TicketToolInput) -> TicketToolOutput:
        """Query live incident tickets via MCP Server with a strict timeout and 20-record cap."""
        if self._mcp_client is None and not self._mcp_server_url:
            _ensure_mcp_server_importable()
            _build_upstream_incidents_fastapi_app()

        start_ns = time.perf_counter()
        criteria_dict = tool_input.to_dict()
        cap_limit = max(1, min(MAX_TOOL_RECORDS, int(tool_input.limit)))

        executor = ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(self._run_sync_in_thread, tool_input)
            matched_dtos: List[TicketRecordDTO] = future.result(
                timeout=self._timeout_seconds
            )
        except (FuturesTimeoutError, TimeoutError, asyncio.TimeoutError):
            elapsed_ms = max(0.01, round((time.perf_counter() - start_ns) * 1000.0, 3))
            return TicketToolOutput(
                status="timeout",
                records=[],
                total_matched=0,
                latency_ms=elapsed_ms,
                error_message=(
                    f"Support ticket lookup via MCP timed out after {self._timeout_seconds:.1f} seconds."
                ),
                queried_criteria=criteria_dict,
            )
        except Exception as exc:
            msg = str(exc)
            if "RESOURCE_NOT_FOUND" in msg or "was not found" in msg.lower():
                matched_dtos = []
            else:
                elapsed_ms = max(
                    0.01, round((time.perf_counter() - start_ns) * 1000.0, 3)
                )
                return TicketToolOutput(
                    status="error",
                    records=[],
                    total_matched=0,
                    latency_ms=elapsed_ms,
                    error_message="The MCP Incident Manager service encountered an error and could not complete the ticket lookup.",
                    queried_criteria=criteria_dict,
                )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        sorted_dtos = sorted(
            matched_dtos,
            key=lambda r: (r.updated_at or "", r.created_at or "", r.id or ""),
            reverse=True,
        )
        total_matched = len(sorted_dtos)
        capped_records = sorted_dtos[:cap_limit]
        elapsed_ms = max(0.01, round((time.perf_counter() - start_ns) * 1000.0, 3))

        if total_matched == 0:
            if tool_input.ticket_id:
                not_found_msg = (
                    f"No incident record matched ticket_id='{tool_input.ticket_id}'."
                )
            else:
                not_found_msg = (
                    "No incident records matched the requested filter criteria."
                )
            return TicketToolOutput(
                status="not_found",
                records=[],
                total_matched=0,
                latency_ms=elapsed_ms,
                error_message=not_found_msg,
                queried_criteria=criteria_dict,
            )

        return TicketToolOutput(
            status="success",
            records=capped_records,
            total_matched=total_matched,
            latency_ms=elapsed_ms,
            error_message=None,
            queried_criteria=criteria_dict,
        )


__all__ = [
    "DEFAULT_TOOL_TIMEOUT_SECONDS",
    "MAX_TOOL_RECORDS",
    "McpTicketToolAdapter",
]
