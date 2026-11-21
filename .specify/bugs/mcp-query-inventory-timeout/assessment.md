# Bug Assessment: MCP query_inventory Upstream Timeout and Unhandled JSON-RPC Exception

- **Slug**: mcp-query-inventory-timeout
- **Created**: 2026-11-20T15:38:30+01:00
- **Source**: Pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

The user submitted a stack trace demonstrating an unhandled timeout error when calling the MCP tool `query_inventory`:

```text
[11/20/26 14:32:47] Error calling tool 'query_inventory'                                                                                                                   
                    ╭───────────────────────────────────────────────────────── Traceback (most recent call last) ─────────────────────────────────────────────────────────╮
                    │ /workspaces/aie-pt-3-ai-engineering-company-project-monorepo-Francisco_Patrick/mcps/trackflow-server/.venv/lib/python3.14/site-packages/httpx/_tran │
                    │ sports/default.py:101 in map_httpcore_exceptions                                                                                                    │
                    │                                                                                                                                                     │
                    │    98 │   if len(HTTPCORE_EXC_MAP) == 0:                                                                                                            │
                    │    99 │   │   HTTPCORE_EXC_MAP = _load_httpcore_exceptions()                                                                                        │
                    │   100 │   try:                                                                                                                                      │
                    │ ❱ 101 │   │   yield                                                                                                                                 │
                    │   102 │   except Exception as exc:                                                                                                                  │
                    │   103 │   │   mapped_exc = None                                                                                                                     │
                    │                                                                                                                                                     │
                    │ /workspaces/aie-pt-3-ai-engineering-company-project-monorepo-Francisco_Patrick/mcps/trackflow-server/.venv/lib/python3.14/site-packages/httpx/_tran │
                    │ sports/default.py:394 in handle_async_request                                                                                                       │
                    │   394 │   │   │   resp = await self._pool.handle_async_request(req)                                                                                 │
                    │                                                                                                                                                     │
                    │ /workspaces/aie-pt-3-ai-engineering-company-project-monorepo-Francisco_Patrick/mcps/trackflow-server/.venv/lib/python3.14/site-packages/httpcore/_e │
                    │ xceptions.py:14 in map_exceptions                                                                                                                   │
                    │    14 │   │   │   │   raise to_exc(exc) from exc                                                                                                     │
                    ╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                    ReadTimeout                                                                                                                                            
                                                                                                                                                                           
                    The above exception was the direct cause of the following exception:                                                                                   
                                                                                                                                                                           
                    ╭───────────────────────────────────────────────────────── Traceback (most recent call last) ─────────────────────────────────────────────────────────╮
                    │ /workspaces/aie-pt-3-ai-engineering-company-project-monorepo-Francisco_Patrick/mcps/trackflow-server/src/trackflow_server/clients/upstream_client.p │
                    │ y:102 in _request                                                                                                                                   │
                    │   102 │   │   │   │   │   response = await client.request(                                                                                          │
                    │   103 │   │   │   │   │   │   method=method,                                                                                                        │
                    │   104 │   │   │   │   │   │   url=url,                                                                                                              │
                    │   105 │   │   │   │   │   │   params=params,                                                                                                        │
                    │                                                                                                                                                     │
                    │ /workspaces/aie-pt-3-ai-engineering-company-project-monorepo-Francisco_Patrick/mcps/trackflow-server/.venv/lib/python3.14/site-packages/httpx/_clie │
                    │ nt.py:1540 in request                                                                                                                               │
                    │   1540 │   │   return await self.send(request, auth=auth, follow_redirects=follow_redirects)                                                        │
                    │                                                                                                                                                     │
                    │ /workspaces/aie-pt-3-ai-engineering-company-project-monorepo-Francisco_Patrick/mcps/trackflow-server/.venv/lib/python3.14/site-packages/httpx/_tran │
                    │ sports/default.py:118 in map_httpcore_exceptions                                                                                                    │
                    │   118 │   │   raise mapped_exc(message) from exc                                                                                                    │
                    ╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                    ReadTimeout                                                                                                                                            
                                                                                                                                                                           
                    The above exception was the direct cause of the following exception:                                                                                   
                                                                                                                                                                           
                    ╭───────────────────────────────────────────────────────── Traceback (most recent call last) ─────────────────────────────────────────────────────────╮
                    │ /workspaces/aie-pt-3-ai-engineering-company-project-monorepo-Francisco_Patrick/mcps/trackflow-server/.venv/lib/python3.14/site-packages/fastmcp/ser │
                    │ ver/server.py:1598 in call_tool                                                                                                                     │
                    │                                                                                                                                                     │
                    │ /workspaces/aie-pt-3-ai-engineering-company-project-monorepo-Francisco_Patrick/mcps/trackflow-server/src/trackflow_server/clients/upstream_client.p │
                    │ y:332 in query_inventory                                                                                                                            │
                    │   332 │   │   │   response = await self._request(                                                                                                   │
                    │   333 │   │   │   │   "GET", "/api/v1/inventory/products", params=params or None                                                                    │
                    │   334 │   │   │   )                                                                                                                                 │
                    │                                                                                                                                                     │
                    │ /workspaces/aie-pt-3-ai-engineering-company-project-monorepo-Francisco_Patrick/mcps/trackflow-server/src/trackflow_server/clients/upstream_client.p │
                    │ y:110 in _request                                                                                                                                   │
                    │   110 │   │   │   raise UpstreamUnavailableError(                                                                                                   │
                    │   111 │   │   │   │   f"Upstream request '{method} {path}' timed out after                                                                          │
                    │       {self._timeout_seconds:.1f}s.",                                                                                                               │
                    │   112 │   │   │   │   details={"method": method, "path": path, "reason": "timeout"},                                                                │
                    │   113 │   │   │   ) from exc                                                                                                                        │
                    ╰─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
                    UpstreamUnavailableError: Upstream request 'GET /api/v1/inventory/products' timed out after 4.0s.                                                      
ERROR:mcp.shared.jsonrpc_dispatcher:handler for 'tools/call' raised
Traceback (most recent call last):
  File "/workspaces/aie-pt-3-ai-engineering-company-project-monorepo-Francisco_Patrick/mcps/trackflow-server/src/trackflow_server/app.py", line 113, in on_call_tool
    result = await call_next(context)
             ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/workspaces/aie-pt-3-ai-engineering-company-project-monorepo-Francisco_Patrick/mcps/trackflow-server/.venv/lib/python3.14/site-packages/fastmcp/server/server.py", line 1663, in call_tool
    raise ToolError(f"Error calling tool {name!r}: {e}") from e
fastmcp.exceptions.ToolError: Error calling tool 'query_inventory': Upstream request 'GET /api/v1/inventory/products' timed out after 4.0s.

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "/workspaces/aie-pt-3-ai-engineering-company-project-monorepo-Francisco_Patrick/mcps/trackflow-server/.venv/lib/python3.14/site-packages/mcp/shared/jsonrpc_dispatcher.py", line 740, in _handle_request
    result = await on_request(dctx, req.method, req.params)
...
  File "/workspaces/aie-pt-3-ai-engineering-company-project-monorepo-Francisco_Patrick/mcps/trackflow-server/src/trackflow_server/app.py", line 138, in on_call_tool
    raise domain_err from exc
trackflow_server.models.errors.UpstreamUnavailableError: Upstream request 'GET /api/v1/inventory/products' timed out after 4.0s.
```

## Symptom

When executing `tools/call` for `query_inventory` against `trackflow-server`, `UpstreamClient` issues `GET /api/v1/inventory/products` against the upstream API. If the upstream service takes longer than 4.0 seconds to respond, `httpx` raises a `ReadTimeout`. While `UpstreamClient._request` maps this into a domain `UpstreamUnavailableError`, `TrackFlowAuditAndScopeMiddleware.on_call_tool` catches FastMCP's internal `ToolError` and re-raises `domain_err` (`UpstreamUnavailableError`) as an unhandled exception. This causes the MCP protocol runner (`mcp.shared.jsonrpc_dispatcher`) to crash with `ERROR:mcp.shared.jsonrpc_dispatcher:handler for 'tools/call' raised` instead of returning a clean MCP error response (`isError=True` with a structured message) to the MCP client.

Expected behavior:
1. When the upstream HTTP service times out or is unreachable, the tool call should gracefully return a standardized MCP error payload (`isError=True` or `ToolError`) describing the upstream timeout, rather than causing an unhandled exception that crashes `jsonrpc_dispatcher`.
2. The client timeout should be configurable via environment variable (e.g. `TRACKFLOW_UPSTREAM_TIMEOUT` or `TRACKFLOW_HTTP_TIMEOUT`) instead of being hard-coded with an unmodifiable 4.0-second cap.
3. The upstream endpoint `GET /api/v1/inventory/products` in `services/api` should not block the HTTP request thread during task dispatch or Redis metadata registration.

## Reproduction

1. Start `trackflow-server` in stdio or SSE mode.
2. Ensure the upstream backend `TRACKFLOW_API_BASE_URL` points to an endpoint or mock that delays responses for more than 4.0 seconds (e.g., simulating slow Celery/Redis connection during `GET /api/v1/inventory/products`).
3. Send a JSON-RPC `tools/call` request for tool `query_inventory` with `{"sku": "TF-001"}` or empty arguments `{}`.
4. Observe that after 4.0 seconds, `httpx` raises `ReadTimeout`, `UpstreamClient` maps it to `UpstreamUnavailableError`, and `TrackFlowAuditAndScopeMiddleware.on_call_tool` re-raises `domain_err`.
5. Observe `ERROR:mcp.shared.jsonrpc_dispatcher:handler for 'tools/call' raised` logged to stderr and an unhandled JSON-RPC error response (-32603) returned to the MCP client.

## Suspected Code Paths

- [mcps/trackflow-server/src/trackflow_server/app.py:123-138](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/mcps/trackflow-server/src/trackflow_server/app.py#L123-L138): In `TrackFlowAuditAndScopeMiddleware.on_call_tool`, when an exception occurs in `call_next`, it unwraps `domain_err` and executes `raise domain_err from exc`. Because `domain_err` is an arbitrary `TrackFlowMcpError` (not FastMCP's expected `ToolError`), it escapes the FastMCP middleware chain and bubbles into `mcp.shared.jsonrpc_dispatcher`, triggering an unhandled dispatch failure.
- [mcps/trackflow-server/src/trackflow_server/clients/upstream_client.py:23, 44-46, 109-113](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/mcps/trackflow-server/src/trackflow_server/clients/upstream_client.py#L23-L46): `DEFAULT_UPSTREAM_TIMEOUT_SECONDS = 4.0` is hardcoded. Lines 44-46 enforce `timeout_seconds = min(max(timeout_seconds, 0.1), 4.0)` which prevents configuring any timeout greater than 4.0 seconds via environment variable.
- [mcps/trackflow-server/src/trackflow_server/tools/inventory.py:120-125](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/mcps/trackflow-server/src/trackflow_server/tools/inventory.py#L120-L125): `query_inventory_tool` directly awaits `client.query_inventory()`. Without catching `UpstreamUnavailableError` at the tool boundary, the exception relies on FastMCP's wrapper which gets broken by `app.py`.
- [services/api/presentation/api/v1/inventory.py:49-75](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/presentation/api/v1/inventory.py#L49-L75): `GET /api/v1/inventory/products` enqueues Celery task `list_products_task.delay()` and registers metadata in Redis synchronously. If Redis is experiencing connection retries or latency, the thread blocks and causes the upstream HTTP request to exceed 4.0 seconds.

## Root Cause Hypothesis

**Confidence: High**

The bug stems from a dual failure:
1. **Protocol Exception Handling Defect in MCP Server**: In `TrackFlowAuditAndScopeMiddleware.on_call_tool` (`app.py`), the exception handler intercepts FastMCP's internal `ToolError` (which FastMCP generates to safely encode tool execution errors into protocol responses with `isError=True`). Instead of letting FastMCP handle the error or raising `fastmcp.exceptions.ToolError(domain_err.message)` (or returning a structured error response), the middleware does `raise domain_err from exc`. Because `domain_err` is `UpstreamUnavailableError`, the outer MCP dispatcher (`jsonrpc_dispatcher.py`) does not recognize it as a handled tool error and treats it as an internal server crash, logging `handler for 'tools/call' raised`.
2. **Upstream Latency and Inflexible Hardcoded Timeout**: `UpstreamClient` enforces an unmodifiable 4.0s timeout ceiling without checking environment variables (such as `TRACKFLOW_UPSTREAM_TIMEOUT_SECONDS`). When `GET /api/v1/inventory/products` takes > 4.0s due to upstream queue/Redis latency or database aggregation overhead, `httpx` triggers `ReadTimeout`, immediately tripping the unhandled exception path.

## Proposed Remediation

**Preferred**:
1. **Fix MCP Middleware Exception Handling**:
   In `mcps/trackflow-server/src/trackflow_server/app.py`, update `on_call_tool` exception handling:
   - When catching an exception during tool execution, re-raise `fastmcp.exceptions.ToolError(f"[{err_code}] {domain_err.message}")` or format the error so FastMCP catches it and yields an MCP `CallToolResult` with `isError=True`.
   - Ensure the JSON-RPC dispatcher never receives an unhandled raw domain exception from `tools/call`.
2. **Allow Configurable Upstream Timeout**:
   In `mcps/trackflow-server/src/trackflow_server/clients/upstream_client.py`:
   - Read `timeout_seconds` from `os.environ.get("TRACKFLOW_UPSTREAM_TIMEOUT_SECONDS")` or similar before falling back to `DEFAULT_UPSTREAM_TIMEOUT_SECONDS`.
   - Remove or relax the strict upper clamp (`min(..., 4.0)`) or allow dev/codespace environments to specify higher timeouts when background services or cold starts occur.
3. **Resilience in Upstream Endpoint**:
   Ensure `services/api/presentation/api/v1/inventory.py` and Celery dispatch do not block indefinitely if Redis or broker connections stall.

**Alternatives**:
- In `query_inventory_tool` (`mcps/trackflow-server/src/trackflow_server/tools/inventory.py`), catch `UpstreamUnavailableError` directly inside the tool function and return a structured JSON response `{ "status": "error", "error_code": "UPSTREAM_UNAVAILABLE", "message": "..." }`. Trade-off: tool returns `status_code: 200` with an error body instead of an MCP error signal unless `isError=True` is explicitly passed.

**Files likely to change**:
- `mcps/trackflow-server/src/trackflow_server/app.py`
- `mcps/trackflow-server/src/trackflow_server/clients/upstream_client.py`
- `mcps/trackflow-server/tests/test_inventory_tool.py`
- `mcps/trackflow-server/tests/test_incident_tools.py`

**Tests to add or update**:
- Add unit and protocol test in `tests/test_inventory_tool.py` simulating an upstream `ReadTimeout` during `query_inventory` via `mock_upstream_backend.simulate_timeout = True`.
- Assert that calling `mcp.call_tool("query_inventory", ...)` produces a valid MCP tool error result (or raises a properly handled `ToolError`), verifying `jsonrpc_dispatcher` does not crash or raise an unhandled exception.
- Add test in `test_upstream_client.py` asserting that environment variable `TRACKFLOW_UPSTREAM_TIMEOUT_SECONDS` customizes client timeout.

## Risks & Considerations

- **MCP Protocol Compatibility**: The fix must strictly preserve the MCP protocol specification where tool failures return `isError: True` with text content, avoiding breaking clients (like Claude Desktop, Cursor, or MCP Inspector) expecting standard tool call error payloads.
- **Audit Logging Invariants**: The structured audit logger in `app.py` must continue recording `ERROR` or `REJECTED` outcomes and latency measurements even when `ToolError` is propagated.

## Open Questions

- None.
