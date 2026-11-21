# Bug Fix: MCP query_inventory Upstream Timeout and Protocol Error Handling

- **Slug**: mcp-query-inventory-timeout
- **Fixed**: 2026-11-20T15:46:00+01:00
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Fixed unhandled protocol exception dispatch failures during upstream timeouts in `trackflow-server` by wrapping domain exceptions in FastMCP `ToolError` within `TrackFlowAuditAndScopeMiddleware`, ensuring MCP clients receive a valid `is_error=True` `CallToolResult`. Additionally made `UpstreamClient` timeout configurable via environment variables (`TRACKFLOW_UPSTREAM_TIMEOUT_SECONDS`, `TRACKFLOW_HTTP_TIMEOUT`) and removed the hardcoded 4.0-second timeout ceiling.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `mcps/trackflow-server/src/trackflow_server/app.py` | modified | Replaced `raise domain_err from exc` with `raise ToolError(f"[{err_code}] {domain_err.message}") from domain_err` and enhanced `_extract_domain_error` to recursively unwrap nested causes |
| `mcps/trackflow-server/src/trackflow_server/clients/upstream_client.py` | modified | Allowed custom timeout configuration via `TRACKFLOW_UPSTREAM_TIMEOUT_SECONDS` / `TRACKFLOW_HTTP_TIMEOUT` or constructor argument, removing unmodifiable 4.0s clamp |
| `mcps/trackflow-server/tests/test_inventory_tool.py` | modified | Added `test_query_inventory_upstream_timeout_produces_mcp_error_result` verifying `ToolError` propagation and `CallToolResult(is_error=True)` wire response |
| `mcps/trackflow-server/tests/test_upstream_client.py` | added | Added unit suite verifying default 4.0s timeout, environment variable overrides, constructor override without 4.0s ceiling, and invalid input fallbacks |

## Diff Highlights (optional)

```python
# mcps/trackflow-server/src/trackflow_server/app.py
-            raise domain_err from exc
+            raise ToolError(f"[{err_code}] {domain_err.message}") from domain_err
```

```python
# mcps/trackflow-server/src/trackflow_server/clients/upstream_client.py
-        if timeout_seconds <= 0.0 or timeout_seconds > 4.0:
-            timeout_seconds = min(max(timeout_seconds, 0.1), 4.0)
+        if timeout_seconds is None:
+            env_timeout = (
+                os.environ.get("TRACKFLOW_UPSTREAM_TIMEOUT_SECONDS")
+                or os.environ.get("TRACKFLOW_HTTP_TIMEOUT")
+            )
+            if env_timeout:
...
```

## Tests Added or Updated

- `mcps/trackflow-server/tests/test_inventory_tool.py::TestInventoryTool::test_query_inventory_upstream_timeout_produces_mcp_error_result` — Pins down that upstream `ReadTimeout` during `query_inventory` triggers domain error on direct call, propagates `ToolError` across FastMCP `call_tool`, and returns `CallToolResult(is_error=True)` without bubbling unhandled exceptions to `jsonrpc_dispatcher`.
- `mcps/trackflow-server/tests/test_upstream_client.py::TestUpstreamClientTimeout::test_default_timeout_is_four_seconds` — Verifies default timeout is 4.0 seconds.
- `mcps/trackflow-server/tests/test_upstream_client.py::TestUpstreamClientTimeout::test_explicit_timeout_seconds_overrides_default_without_four_second_cap` — Verifies timeouts greater than 4.0s (e.g., 12.5s) are respected.
- `mcps/trackflow-server/tests/test_upstream_client.py::TestUpstreamClientTimeout::test_env_var_upstream_timeout_seconds` — Verifies `TRACKFLOW_UPSTREAM_TIMEOUT_SECONDS` sets client timeout.
- `mcps/trackflow-server/tests/test_upstream_client.py::TestUpstreamClientTimeout::test_env_var_http_timeout` — Verifies `TRACKFLOW_HTTP_TIMEOUT` fallback sets client timeout.
- `mcps/trackflow-server/tests/test_upstream_client.py::TestUpstreamClientTimeout::test_invalid_or_negative_timeout_falls_back_to_default` — Verifies invalid string and non-positive numbers safely fall back to default.

## Local Verification

- Commands run: `& "mcps/trackflow-server/.venv/Scripts/pytest.exe" "mcps/trackflow-server/tests"` → 37 passed, 17 warnings in 1.44s
- Manual checks: Verified simulated timeout via FastMCP `_on_call_tool` returns `<CallToolResult is_error=True content=[TextContent(text="[UPSTREAM_UNAVAILABLE] ...")]>` with no uncaught exception escaping to dispatcher.

## Deviations from Assessment

None. The preferred remediation plan from `assessment.md` was applied verbatim.

## Follow-ups

- Consider adding upstream endpoint timeout / connection pooling configuration in backend `services/api` if slow database aggregations persist under high concurrency.
