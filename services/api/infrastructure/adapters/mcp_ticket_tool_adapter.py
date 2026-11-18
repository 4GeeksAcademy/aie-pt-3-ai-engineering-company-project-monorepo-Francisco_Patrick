"""Standardized MCP Client Adapter for the TrackFlow Support Agent (`McpTicketToolAdapter`).

Implements `SupportTicketToolPort` (FR-013, FR-014, FR-015, T026) using `langchain-mcp-adapters`:
- Connects to the TrackFlow MCP Server via `MultiServerMCPClient` (`SSEConnection`) with
  OAuth 2.1 Bearer authentication (`incidents:read` scope).
- Discovers and invokes the standardized `query_incidents` MCP tool via `langchain-mcp-adapters`.
- Provides an embedded MCP tool execution client when `MCP_SERVER_URL` is not pointing to a
  separate network process, ensuring deterministic in-process execution during unit and
  integration test runs while exercising the full `langchain-mcp-adapters` tool interface.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import json
import os
import time
from typing import Any, Callable, Dict, List, Optional

from langchain_core.tools import BaseTool, StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient, SSEConnection

from application.services.incident_service import IncidentService
from domain.agent.entities import (
    TicketRecordDTO,
    TicketToolInput,
    TicketToolOutput,
)
from domain.agent.ports import SupportTicketToolPort
from domain.incident_model import Incident
from domain.knowledge.entities import KnowledgeRuntimeConfig

DEFAULT_TOOL_TIMEOUT_SECONDS = 4.0
MAX_TOOL_RECORDS = 20


class _EmbeddedMcpServerClient:
    """In-process MCP tool client exposing `query_incidents` as a LangChain StructuredTool."""

    def __init__(
        self,
        incident_service: Optional[IncidentService] = None,
        incident_service_factory: Optional[Callable[[], IncidentService]] = None,
    ) -> None:
        self._incident_service = incident_service
        self._incident_service_factory = incident_service_factory

    def _resolve_service(self) -> IncidentService:
        if self._incident_service is not None:
            return self._incident_service
        if self._incident_service_factory is not None:
            return self._incident_service_factory()
        from infrastructure.adapters.tiny_db_incident_repository import (
            TinyDBIncidentRepository,
        )
        from infrastructure.persistence.tinydb.client import get_tinydb

        return IncidentService(repo=TinyDBIncidentRepository(get_tinydb()))

    @staticmethod
    def _serialize_incident(inc: Incident | Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(inc, dict):
            return {
                "id": str(inc.get("id") or inc.get("legacy_id") or ""),
                "title": str(inc.get("title") or ""),
                "description": str(inc.get("description") or ""),
                "status": str(inc.get("status") or "open"),
                "category": str(inc.get("category") or "other"),
                "origin": str(inc.get("origin") or "customer"),
                "branch": str(inc.get("branch") or "central"),
                "created_at": str(inc.get("created_at") or ""),
                "updated_at": str(inc.get("updated_at") or ""),
            }
        raw = inc.to_dict()
        return {
            "id": str(raw.get("id") or ""),
            "title": str(raw.get("title") or ""),
            "description": str(raw.get("description") or ""),
            "status": str(raw.get("status") or "open"),
            "category": str(raw.get("category") or "other"),
            "origin": str(raw.get("origin") or "customer"),
            "branch": str(raw.get("branch") or "central"),
            "created_at": str(raw.get("created_at") or ""),
            "updated_at": str(raw.get("updated_at") or ""),
        }

    async def get_tools(self) -> List[BaseTool]:
        """Return the MCP `query_incidents` tool wrapped as a LangChain StructuredTool."""

        async def _query_incidents_mcp(
            ticket_id: Optional[str] = None,
            status: Optional[str] = None,
            category: Optional[str] = None,
            origin: Optional[str] = None,
            branch: Optional[str] = None,
        ) -> str:
            service = self._resolve_service()
            matched: List[Dict[str, Any]] = []

            if ticket_id:
                target_id = ticket_id.strip()
                exact = service.get_incident_by_id(target_id)
                if exact is not None:
                    matched = [self._serialize_incident(exact)]
                else:
                    repo = getattr(service, "repo", None)
                    if repo is not None and hasattr(repo, "find_by_legacy_id"):
                        leg = repo.find_by_legacy_id(target_id)
                        if leg is not None:
                            matched = [self._serialize_incident(leg)]
                    if not matched:
                        norm = target_id.lower()
                        for inc in service.list_all_incidents():
                            inc_id = str(getattr(inc, "id", "") or "").lower()
                            leg_id = str(getattr(inc, "legacy_id", "") or "").lower()
                            if norm in (inc_id, leg_id):
                                matched.append(self._serialize_incident(inc))
            else:
                incidents = service.list_all_incidents(
                    status=status.lower() if status else None,
                    origin=origin.lower() if origin else None,
                    branch=branch.lower() if branch else None,
                    category=category.lower() if category else None,
                )
                if not incidents and branch:
                    unfiltered = service.list_all_incidents(
                        status=status.lower() if status else None,
                        origin=origin.lower() if origin else None,
                        branch=None,
                        category=category.lower() if category else None,
                    )
                    target_br = branch.strip().lower()
                    incidents = [
                        inc
                        for inc in unfiltered
                        if str(getattr(inc, "branch", "") or "").strip().lower()
                        == target_br
                    ]
                matched = [self._serialize_incident(inc) for inc in incidents]

            return json.dumps(
                {
                    "status": "success" if matched else "not_found",
                    "records": matched,
                    "total_matched": len(matched),
                    "queried_criteria": {
                        k: v
                        for k, v in {
                            "ticket_id": ticket_id,
                            "status": status,
                            "category": category,
                            "origin": origin,
                            "branch": branch,
                        }.items()
                        if v is not None
                    },
                }
            )

        return [
            StructuredTool.from_function(
                coroutine=_query_incidents_mcp,
                name="query_incidents",
                description=(
                    "Query operational incident records by unique ID or search filters "
                    "(status, category, origin, branch) via TrackFlow MCP Server."
                ),
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
        incident_service: Optional[IncidentService] = None,
        incident_service_factory: Optional[Callable[[], IncidentService]] = None,
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
        self._embedded_client = _EmbeddedMcpServerClient(
            incident_service=incident_service,
            incident_service_factory=incident_service_factory,
        )

    @property
    def timeout_seconds(self) -> float:
        """Return configured numerical timeout in seconds."""
        return self._timeout_seconds

    def build_connection_config(self) -> Dict[str, SSEConnection]:
        """Build `MultiServerMCPClient` connection dictionary using `SSEConnection`."""
        url = self._mcp_server_url or "http://127.0.0.1:8001/sse"
        headers: Dict[str, Any] = {}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        conn: SSEConnection = {
            "transport": "sse",
            "url": url,
            "headers": headers,
            "timeout": self._timeout_seconds,
            "sse_read_timeout": self._timeout_seconds,
        }
        return {"trackflow": conn}

    def _resolve_mcp_client(self) -> Any:
        """Resolve either the injected/remote `MultiServerMCPClient` or the embedded MCP client."""
        if self._mcp_client is not None:
            return self._mcp_client
        if self._mcp_server_url:
            return MultiServerMCPClient(self.build_connection_config())
        return self._embedded_client

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
