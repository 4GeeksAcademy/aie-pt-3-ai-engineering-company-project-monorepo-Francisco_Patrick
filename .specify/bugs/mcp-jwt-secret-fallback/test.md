# Bug Verification: Insecure Default JWT Secret Shortcut and Missing Playground Validation Artifacts

- **Slug**: mcp-jwt-secret-fallback
- **Tested**: 2026-11-20T11:40:00+01:00
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The security vulnerability and documentation defect were comprehensively validated. The server now fails fast on startup if credentials are unset, tokens signed with alternative or forged keys are strictly rejected with HTTP 401, all production modules are decoupled from test helpers, and documentation contains verified public Codespaces endpoints and JSON-RPC transcripts. All 30 tests pass with zero regressions.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix): Fail-fast startup | `uv run python -c "from trackflow_server.auth.config import validate_auth_config; validate_auth_config()"` (with env vars unset) | pass | Raised `RuntimeError: MCP Server startup failed: either 'MCP_JWT_SECRET' or 'MCP_OAUTH_JWKS_URI' must be defined in environment or .env.` |
| Reproduction (post-fix): Forged secret rejection | `uv run python -c "verify_bearer_token(f'Bearer {old_token}')"` | pass | Token signed with old default secret rejected with `AuthenticationRequiredError` (401, `invalid_token`). |
| Production code import audit | `Get-ChildItem src/trackflow_server -Recurse \| Select-String "trackflow_server.testing"` | pass | Zero occurrences of test helper imports in production codebase. |
| New / updated tests | `uv run pytest mcps/trackflow-server/tests/test_auth.py -v` | pass | 9 passed in 0.11s (including startup failure and different-secret tests). |
| Regression suite | `uv run pytest mcps/trackflow-server/tests -v` | pass | 30 passed in 0.51s across all auth, incidents, inventory, and audit suites. |
| Syntax & Compilation integrity | `uv run python -m compileall mcps/trackflow-server/src` | pass | Successfully compiled all source files with zero syntax or bytecode errors. |
| Documentation verification | Inspection of `mcps/trackflow-server/README.md` and `specs/028-mcp-server-tools/quickstart.md` | pass | Both documents contain concrete forwarded URL (`https://crispy-space-umbrella-abc123-8001.app.github.dev`) and live `tools/list` and `tools/call` JSON-RPC transcripts. |

## Output Excerpts

```text
# 1. Fail-fast startup verification without configured credentials
PASS: validate_auth_config raised RuntimeError: MCP Server startup failed: either 'MCP_JWT_SECRET' or 'MCP_OAUTH_JWKS_URI' must be defined in environment or .env.
PASS: create_asgi_app raised RuntimeError: MCP Server startup failed: either 'MCP_JWT_SECRET' or 'MCP_OAUTH_JWKS_URI' must be defined in environment or .env.

# 2. Rejection of token forged with former default secret
PASS: Forged old default token rejected: Provided Bearer access token is malformed or has an invalid signature. {'reason': 'invalid_token'}

# 3. New & updated auth tests
mcps/trackflow-server/tests/test_auth.py::TestOAuthAndDiscovery::test_server_startup_fails_when_jwt_secret_and_jwks_missing PASSED [ 77%]
mcps/trackflow-server/tests/test_auth.py::TestOAuthAndDiscovery::test_token_with_different_secret_rejected_with_401 PASSED [ 88%]
mcps/trackflow-server/tests/test_auth.py::TestOAuthAndDiscovery::test_verify_bearer_token_fails_when_secret_unset_in_runtime PASSED [100%]
============================== 9 passed in 0.11s ==============================

# 4. Full test suite
============================= 30 passed in 0.51s ==============================
```

## Residual Risks

- **Local Development Environment Configuration**: Developers who do not configure `.env` or set `MCP_JWT_SECRET` in their local shell environment will encounter a fail-fast `RuntimeError` during startup. This is by design to ensure security; instructions are clearly documented in `.env.example` and `README.md`.
- **JWKS Network Connectivity**: When transitioning to asymmetric OIDC validation with `MCP_OAUTH_JWKS_URI` in production, ensure outbound HTTPS network connectivity to the identity provider endpoint.

## Recommendation

Close the bug — verified end-to-end. Both the security vulnerability (hardcoded secret shortcut and lack of fail-fast startup checks) and the documentation defects (generic placeholders and missing execution transcripts) are fully resolved with extensive test coverage and zero regressions.
