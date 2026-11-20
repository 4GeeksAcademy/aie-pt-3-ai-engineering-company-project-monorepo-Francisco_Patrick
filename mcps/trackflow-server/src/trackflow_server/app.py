"""FastMCP application initialization, OAuth/Audit middlewares, and Starlette ASGI assembly."""

import json
import time
from typing import Any, Dict, Literal, Optional

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from pydantic import ValidationError as PydanticValidationError
from starlette.applications import Starlette
from starlette.middleware import Middleware as StarletteMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

from trackflow_server.auth.config import validate_auth_config
from trackflow_server.auth.metadata import (
    create_mcp_auth_instance,
    create_metadata_routes,
)
from trackflow_server.auth.middleware import (
    OAuthBearerResourceMiddleware,
    get_current_security_context,
)
from trackflow_server.auth.scopes import TOOL_REQUIRED_SCOPES, check_tool_scope
from trackflow_server.clients.upstream_client import UpstreamClient
from trackflow_server.logging.audit import get_audit_logger
from trackflow_server.models.errors import (
    McpErrorCode,
    ToolValidationError,
    TrackFlowMcpError,
)

_upstream_client_instance: Optional[UpstreamClient] = None
_mcp_instance: Optional[FastMCP] = None

REJECTED_ERROR_CODES = {
    McpErrorCode.AUTHENTICATION_REQUIRED.value,
    McpErrorCode.INSUFFICIENT_SCOPE.value,
    McpErrorCode.INVENTORY_MUTATION_REJECTED.value,
}


def get_upstream_client() -> UpstreamClient:
    """Return the active UpstreamClient instance (creating a default one if unset)."""
    global _upstream_client_instance
    if _upstream_client_instance is None:
        _upstream_client_instance = UpstreamClient()
    return _upstream_client_instance


def set_upstream_client(client: Optional[UpstreamClient]) -> None:
    """Override the active UpstreamClient instance (used for testing and dependency injection)."""
    global _upstream_client_instance
    _upstream_client_instance = client


def _extract_domain_error(exc: BaseException) -> TrackFlowMcpError:
    """Unwrap an exception (including FastMCP ToolError) into a categorized TrackFlowMcpError."""
    curr: Optional[BaseException] = exc
    while curr is not None:
        if isinstance(curr, TrackFlowMcpError):
            return curr
        if isinstance(curr, PydanticValidationError):
            return ToolValidationError(f"Tool parameter validation failed: {curr}")
        curr = curr.__cause__ or curr.__context__

    msg = str(exc)
    if "Invalid arguments" in msg or "validation error" in msg.lower():
        return ToolValidationError(msg)
    return ToolValidationError(msg)


class TrackFlowAuditAndScopeMiddleware(Middleware):
    """FastMCP middleware enforcing fine-grained OAuth scopes, inventory mutation guard, and structured audit logging."""

    async def on_call_tool(
        self,
        context: MiddlewareContext[Any],
        call_next: CallNext[Any, Any],
    ) -> Any:
        start_ns = time.perf_counter()
        tool_name = str(getattr(context.message, "name", "") or "")
        raw_args: Dict[str, Any] = dict(getattr(context.message, "arguments", None) or {})
        security_ctx = get_current_security_context()
        client_id = security_ctx.client_id if security_ctx else "unauthenticated"
        audit_logger = get_audit_logger()

        try:
            # 1. Enforce fine-grained OAuth 2.1 scope check for the requested tool
            check_tool_scope(tool_name, security_ctx)

            # 2. Pre-flight structural mutation check for query_inventory before schema stripping
            if tool_name == "query_inventory":
                from trackflow_server.tools.inventory import (
                    enforce_inventory_read_only_guard,
                )

                extra = {
                    k: v
                    for k, v in raw_args.items()
                    if k not in ("sku", "product_id", "query")
                }
                enforce_inventory_read_only_guard(
                    sku=raw_args.get("sku"),
                    product_id=raw_args.get("product_id"),
                    query=raw_args.get("query"),
                    extra_kwargs=extra,
                )

            result = await call_next(context)
            elapsed_ms = (time.perf_counter() - start_ns) * 1000.0
            audit_logger.log_invocation(
                tool_name=tool_name,
                arguments=raw_args,
                outcome="SUCCESS",
                latency_ms=elapsed_ms,
                client_id=client_id,
            )
            return result
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start_ns) * 1000.0
            domain_err = _extract_domain_error(exc)
            err_code = domain_err.error_code.value
            outcome: Literal["REJECTED", "ERROR"] = (
                "REJECTED" if err_code in REJECTED_ERROR_CODES else "ERROR"
            )
            audit_logger.log_invocation(
                tool_name=tool_name,
                arguments=raw_args,
                outcome=outcome,
                error_code=err_code,
                latency_ms=elapsed_ms,
                client_id=client_id,
            )
            raise ToolError(f"[{err_code}] {domain_err.message}") from domain_err


async def health_endpoint(_request: Request) -> JSONResponse:
    """Return service health status."""
    return JSONResponse(
        {
            "status": "healthy",
            "service": "trackflow-mcp-server",
            "version": "0.1.0",
        }
    )


def create_mcp_server() -> FastMCP:
    """Initialize and return a configured FastMCP server instance with registered tools and middleware."""
    from trackflow_server.tools.incidents import register_incident_tools
    from trackflow_server.tools.inventory import register_inventory_tools

    mcp = FastMCP(
        name="trackflow-mcp-server",
        instructions=(
            "Standardized TrackFlow Operational MCP Server providing OAuth 2.1 protected "
            "incident ticket management (create_incident, query_incidents, transition_incident_status) "
            "and strictly read-only warehouse inventory stock queries (query_inventory)."
        ),
    )
    mcp.add_middleware(TrackFlowAuditAndScopeMiddleware())
    register_incident_tools(mcp)
    register_inventory_tools(mcp)
    return mcp


def get_mcp_server() -> FastMCP:
    """Return the singleton FastMCP server instance."""
    global _mcp_instance
    if _mcp_instance is None:
        _mcp_instance = create_mcp_server()
    return _mcp_instance


def _build_jsonrpc_messages_handler(
    mcp: FastMCP, fallback_app: Any
) -> Any:
    """Handle direct JSON-RPC POSTs to `/messages/` while forwarding SSE session requests."""

    async def handle_messages(request: Request) -> Response:
        # If session_id is present in query params, delegate to FastMCP SSE session handler
        if "session_id" in request.query_params:
            scope = dict(request.scope)
            received_status = 200
            received_headers: list[tuple[bytes, bytes]] = []
            body_chunks: list[bytes] = []

            async def send(message: dict[str, Any]) -> None:
                nonlocal received_status, received_headers
                if message["type"] == "http.response.start":
                    received_status = message["status"]
                    received_headers = list(message.get("headers", []))
                elif message["type"] == "http.response.body":
                    body_chunks.append(message.get("body", b""))

            await fallback_app(scope, request.receive, send)
            headers_dict = {
                k.decode("latin-1"): v.decode("latin-1")
                for k, v in received_headers
            }
            return Response(
                content=b"".join(body_chunks),
                status_code=received_status,
                headers=headers_dict,
            )

        try:
            payload = await request.json()
        except Exception:
            return JSONResponse(
                status_code=400,
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"},
                },
            )

        rpc_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params") or {}

        if method == "tools/list":
            tools = await mcp.list_tools()
            tool_list = [
                {
                    "name": t.name,
                    "description": t.description,
                    "required_scope": TOOL_REQUIRED_SCOPES.get(t.name),
                    "inputSchema": t.parameters,
                }
                for t in tools
            ]
            return JSONResponse(
                status_code=200,
                content={"jsonrpc": "2.0", "id": rpc_id, "result": {"tools": tool_list}},
            )

        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments") or {}
            try:
                tool_result = await mcp.call_tool(tool_name, arguments)
                text_parts = [
                    getattr(c, "text", "")
                    for c in tool_result.content
                    if hasattr(c, "text")
                ]
                combined = "\n".join(text_parts)
                try:
                    parsed_result = json.loads(combined)
                except Exception:
                    parsed_result = {"text": combined}
                return JSONResponse(
                    status_code=200,
                    content={"jsonrpc": "2.0", "id": rpc_id, "result": parsed_result},
                )
            except Exception as exc:
                domain_err = _extract_domain_error(exc)
                err_dict = domain_err.to_dict()
                err_dict["jsonrpc"] = "2.0"
                err_dict["id"] = rpc_id
                err_dict["error"] = {
                    "code": domain_err.rpc_code,
                    "message": domain_err.message,
                    "data": {"error_code": domain_err.error_code.value},
                }
                return JSONResponse(
                    status_code=domain_err.http_status,
                    content=err_dict,
                )

        return JSONResponse(
            status_code=400,
            content={
                "jsonrpc": "2.0",
                "id": rpc_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            },
        )

    return handle_messages


def create_asgi_app(
    mcp: Optional[FastMCP] = None,
    transport: Literal["sse", "http", "streamable-http"] = "sse",
) -> Starlette:
    """Assemble the OAuth 2.1 protected Starlette ASGI application wrapping FastMCP HTTP/SSE transport."""
    validate_auth_config()
    resolved_mcp = mcp or get_mcp_server()
    mcp_auth = create_mcp_auth_instance()
    mcp_http_app = resolved_mcp.http_app(transport=transport)

    metadata_routes = create_metadata_routes(mcp_auth)
    messages_handler = _build_jsonrpc_messages_handler(resolved_mcp, mcp_http_app)

    routes = [
        Route("/health", health_endpoint, methods=["GET"]),
        *metadata_routes,
        Route("/messages/", messages_handler, methods=["POST"]),
        Route("/messages", messages_handler, methods=["POST"]),
        Mount("/", app=mcp_http_app),
    ]
    return Starlette(
        routes=routes,
        middleware=[StarletteMiddleware(OAuthBearerResourceMiddleware)],
        lifespan=mcp_http_app.lifespan,
    )


__all__ = [
    "TrackFlowAuditAndScopeMiddleware",
    "create_asgi_app",
    "create_mcp_server",
    "get_mcp_server",
    "get_upstream_client",
    "health_endpoint",
    "set_upstream_client",
]
