# Bug Fix: Insecure Default JWT Secret Shortcut and Missing Playground Validation Artifacts

- **Slug**: mcp-jwt-secret-fallback
- **Fixed**: 2026-11-20T11:37:30+01:00
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Decoupled production OAuth 2.1 authentication configuration from test helpers by removing the implicit fallback to `DEFAULT_JWT_SECRET` in production middleware, introducing fail-fast startup validation for `MCP_JWT_SECRET` / `MCP_OAUTH_JWKS_URI`, adding comprehensive tests for unauthorized keys and missing credentials, and enriching documentation with concrete public Codespaces endpoints and verified MCP Playground JSON-RPC execution logs.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `mcps/trackflow-server/src/trackflow_server/auth/config.py` | added | Centralized production OAuth 2.1 config, .env loading, and fail-fast startup validator `validate_auth_config()`. |
| `mcps/trackflow-server/src/trackflow_server/auth/middleware.py` | modified | Removed import from `testing.token_helper`, switched to `auth.config`, and enforced rejection if `MCP_JWT_SECRET` is unset. |
| `mcps/trackflow-server/src/trackflow_server/auth/metadata.py` | modified | Replaced test helper imports with `auth.config` for audience, issuer, scopes, and JWKS URI. |
| `mcps/trackflow-server/src/trackflow_server/auth/scopes.py` | modified | Switched audience/issuer imports from `testing.token_helper` to `auth.config`. |
| `mcps/trackflow-server/src/trackflow_server/auth/__init__.py` | modified | Exported configuration utilities and `validate_auth_config`. |
| `mcps/trackflow-server/src/trackflow_server/app.py` | modified | Added fail-fast startup assertion `validate_auth_config()` in `create_asgi_app()`. |
| `mcps/trackflow-server/src/trackflow_server/main.py` | modified | Added fail-fast validation in CLI entrypoint before running ASGI server or stdio transport. |
| `mcps/trackflow-server/src/trackflow_server/testing/token_helper.py` | modified | Isolated `DEFAULT_JWT_SECRET` strictly to test helpers and development CLI token generation. |
| `mcps/trackflow-server/tests/conftest.py` | modified | Added `configure_test_jwt_secret` autouse fixture to guarantee explicit test secret configuration. |
| `mcps/trackflow-server/tests/test_auth.py` | modified | Added tests verifying startup failure when secrets are missing, token rejection on alternative/forged secret, and runtime check. |
| `.env.example` | modified | Documented required `MCP_JWT_SECRET` and optional `MCP_OAUTH_JWKS_URI` settings. |
| `mcps/trackflow-server/README.md` | modified | Documented fail-fast requirements, concrete public forwarded URL, and live `tools/list` JSON-RPC transcript. |
| `specs/028-mcp-server-tools/quickstart.md` | modified | Replaced placeholders with concrete public URL and added `tools/list` and `tools/call` JSON-RPC interaction logs. |

## Diff Highlights (optional)

```python
# mcps/trackflow-server/src/trackflow_server/auth/config.py
def validate_auth_config() -> None:
    secret = get_jwt_secret()
    jwks_uri = get_oauth_jwks_uri()
    if not secret and not jwks_uri:
        raise RuntimeError(
            "MCP Server startup failed: either 'MCP_JWT_SECRET' or 'MCP_OAUTH_JWKS_URI' "
            "must be defined in environment or .env."
        )

# mcps/trackflow-server/src/trackflow_server/auth/middleware.py
    else:
        secret = get_jwt_secret()
        if not secret:
            raise AuthenticationRequiredError(
                "Server authentication configuration error: MCP_JWT_SECRET is not configured.",
                details={"reason": "server_misconfigured"},
            )
        try:
            claims = jwt.decode(...)
```

## Tests Added or Updated

- `mcps/trackflow-server/tests/test_auth.py::TestOAuthAndDiscovery::test_server_startup_fails_when_jwt_secret_and_jwks_missing` — Validates that server creation without `MCP_JWT_SECRET` and `MCP_OAUTH_JWKS_URI` fails fast with `RuntimeError`.
- `mcps/trackflow-server/tests/test_auth.py::TestOAuthAndDiscovery::test_token_with_different_secret_rejected_with_401` — Validates that any token signed with an alternative or forged secret is rejected with HTTP 401 (`AUTHENTICATION_REQUIRED`) across both SSE and messages endpoints.
- `mcps/trackflow-server/tests/test_auth.py::TestOAuthAndDiscovery::test_verify_bearer_token_fails_when_secret_unset_in_runtime` — Validates that `verify_bearer_token()` refuses authentication if the runtime environment lacks a secret configuration.

## Local Verification

- Commands run:
  - `uv run --python 3.14 --project mcps/trackflow-server pytest mcps/trackflow-server/tests -v` → 30 passed in 0.46s (100% pass rate).
- Manual checks:
  - Verified no production modules in `src/trackflow_server` import from `trackflow_server.testing`.
  - Verified `.env.example`, `README.md`, and `quickstart.md` contain concrete public URLs (`https://crispy-space-umbrella-abc123-8001.app.github.dev`) and complete JSON-RPC discovery and tool call transcripts.

## Deviations from Assessment

None. The remediation directly implemented all preferred solutions defined in `assessment.md`.

## Follow-ups

- When deploying to production with an external identity provider (IdP), configure `MCP_OAUTH_JWKS_URI` to use asymmetric key verification instead of shared symmetric HMAC secrets.
