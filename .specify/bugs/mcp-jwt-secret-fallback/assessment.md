# Bug Assessment: Insecure Default JWT Secret Shortcut and Missing Playground Validation Artifacts

- **Slug**: mcp-jwt-secret-fallback
- **Created**: 2026-11-20T11:25:47+01:00
- **Source**: Pasted text
- **Verdict**: valid
- **Severity**: critical

## Report (verbatim or summarized)

The user submitted the following security vulnerability and documentation defect report:

```text
The authentication system includes a shortcut—`testing/token_helper.py`—which contains a hardcoded `DEFAULT_JWT_SECRET`. The middleware falls back to this value if `MCP_JWT_SECRET` is missing; this allows anyone to sign an HS256 token using the default issuer/audience and execute tools. You shall remove this default (ensuring the application fails to start if the secret is missing), implement JWKS/OIDC or require the secret to be defined in the `.env` file, and add a test case that uses a different secret. Furthermore, the README/quickstart guide references `<codespace-name>`, yet there is no actual screenshot or log from the MCP Playground showing the public URL; please include the URL along with an example of executing `tools/list` and `tools/call`.
```

## Symptom

1. **Security Vulnerability**: When `MCP_JWT_SECRET` is not set in the environment and `MCP_OAUTH_JWKS_URI` is omitted, the production authentication middleware silently falls back to a hardcoded shared secret (`[ENCRYPTION_KEY]`) imported from the test utility module `testing/token_helper.py`. This allows any unauthorized actor possessing knowledge of the default key to sign valid HS256 JWT access tokens with arbitrary scopes and invoke MCP tools. Furthermore, the MCP server starts up cleanly without throwing any warning or error despite having no secure secret configured.
2. **Documentation & Verification Defect**: In both [README.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/mcps/trackflow-server/README.md#L71) and [quickstart.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/028-mcp-server-tools/quickstart.md#L43-L45), the MCP Playground connection instructions rely exclusively on a generic `<codespace-name>` or `<tu-codespace-id>` placeholder. There are no actual logs or concrete session outputs showing the public forwarded URL, nor are there explicit, verifiable execution logs demonstrating `tools/list` and `tools/call` over the wire.

Expected behavior:
- If neither `MCP_OAUTH_JWKS_URI` nor `MCP_JWT_SECRET` is configured in the environment / `.env` file, the server must fail fast during startup and abort immediately with an informative fatal configuration error.
- Production middleware must not import from or rely on `trackflow_server.testing.token_helper`.
- Tokens signed with an invalid or alternative secret must be strictly rejected with HTTP 401 (`AUTHENTICATION_REQUIRED`).
- Documentation must include concrete, realistic public forwarded URL examples and detailed logs of executing both `tools/list` and `tools/call`.

## Reproduction

1. **Vulnerability Reproduction**:
   - Ensure `MCP_JWT_SECRET` and `MCP_OAUTH_JWKS_URI` are unset in the shell environment.
   - Run the server startup CLI: `python -m trackflow_server.main --transport sse --port 8001`. Observe that the server boots successfully without raising any configuration errors.
   - Forge a JWT token using the hardcoded secret `DEFAULT_JWT_SECRET = "[ENCRYPTION_KEY]"` with `iss="https://auth.trackflow.local"`, `aud="https://api.trackflow.local/mcp/"`, and `scope="incidents:read"`.
   - Send a `POST /messages/` request with the forged Bearer token calling `tools/list` or `tools/call`.
   - Observe that the server validates the signature and executes the request with `200 OK`, confirming unauthorized tool execution.

2. **Documentation Defect Reproduction**:
   - Inspect [README.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/mcps/trackflow-server/README.md#L71-L97) lines 71, 89-97, and 109.
   - Inspect [quickstart.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/028-mcp-server-tools/quickstart.md#L43-L52) lines 43-45 and 51.
   - Observe the presence of `<codespace-name>` / `<tu-codespace-id>` placeholders without any concrete captured terminal log or JSON-RPC interaction transcript for `tools/list` or `tools/call`.

## Suspected Code Paths

- [token_helper.py:11, 22-25, 85](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/mcps/trackflow-server/src/trackflow_server/testing/token_helper.py#L11): Hardcodes `DEFAULT_JWT_SECRET = "[ENCRYPTION_KEY]"` and provides `get_jwt_secret()` which defaults to this value when `MCP_JWT_SECRET` is unset.
- [middleware.py:30-34, 152-163](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/mcps/trackflow-server/src/trackflow_server/auth/middleware.py#L30-L34): Imports `get_jwt_secret` directly from `trackflow_server.testing.token_helper` into production middleware and uses it in `verify_bearer_token` without checking if a secret was explicitly configured.
- [app.py:207-250](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/mcps/trackflow-server/src/trackflow_server/app.py#L207-L250): `create_asgi_app` builds the Starlette application without validating that required security credentials (`MCP_JWT_SECRET` or `MCP_OAUTH_JWKS_URI`) are present in the environment.
- [main.py:48-74](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/mcps/trackflow-server/src/trackflow_server/main.py#L48-L74): `main()` serves requests via `uvicorn.run()` without startup preflight checks for JWT secret or JWKS URI configuration.
- [conftest.py:15-21, 260-262](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/mcps/trackflow-server/tests/conftest.py#L15-L21): Pytest test fixtures import and re-export `DEFAULT_JWT_SECRET`, reinforcing the implicit fallback.
- [test_auth.py:43-64](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/mcps/trackflow-server/tests/test_auth.py#L43-L64): Contains tests for expired and malformed tokens, but lacks a test asserting failure on startup when secrets are missing and lacks an explicit test proving rejection of tokens signed with a different secret.
- [README.md:71, 89-97, 109](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/mcps/trackflow-server/README.md#L71): Mentions `https://<codespace-name>-8001.app.github.dev` without actual logs or session examples.
- [quickstart.md:43-45, 51](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/028-mcp-server-tools/quickstart.md#L43-L45): Mentions `https://<codespace-name>-8001.app.github.dev` without concrete public URL logs or `tools/list` and `tools/call` execution logs.

## Root Cause Hypothesis

During the rapid development of feature `028-mcp-server-tools`, `testing/token_helper.py` was introduced as a convenience helper for local testing and CLI token minting. Rather than decoupling production auth configuration from testing utilities, the production middleware in `auth/middleware.py` was implemented to import `get_jwt_secret` directly from `testing/token_helper.py`. Because `get_jwt_secret()` falls back to `DEFAULT_JWT_SECRET` whenever `MCP_JWT_SECRET` is unset, the server operates in an insecure state by default. Furthermore, no startup assertion exists in `app.py` or `main.py` to check that either `MCP_JWT_SECRET` or `MCP_OAUTH_JWKS_URI` is provided. In documentation, placeholder references (`<codespace-name>`) were committed without being complemented by concrete MCP Playground execution logs.

Confidence: High.

## Proposed Remediation

**Preferred**:
1. **Decouple Production Auth Configuration**:
   - Create a dedicated production configuration/auth module (or update `trackflow_server.auth`) that retrieves authentication settings (`MCP_JWT_SECRET`, `MCP_OAUTH_JWKS_URI`, `MCP_OAUTH_ISSUER`, `MCP_OAUTH_AUDIENCE`) directly from the environment or `.env`.
   - Remove `get_jwt_secret` import from `testing.token_helper` in `trackflow_server.auth.middleware` and `trackflow_server.auth.metadata`.
   - In `token_helper.py`, remove the production fallback or make `DEFAULT_JWT_SECRET` strictly internal to test helpers when explicitly requested, eliminating any default secret fallback in production runtime code.
2. **Enforce Startup Validation (Fail-Fast)**:
   - In `create_asgi_app` / `main.py`, introduce a validation step: if neither `MCP_OAUTH_JWKS_URI` nor `MCP_JWT_SECRET` is set (or if `MCP_JWT_SECRET` is empty), raise a descriptive `RuntimeError` (`"MCP Server startup failed: either 'MCP_JWT_SECRET' or 'MCP_OAUTH_JWKS_URI' must be defined in environment or .env."`).
   - Support loading `.env` via `python-dotenv` if available or document setting `MCP_JWT_SECRET` in `.env.example`.
3. **Add Tests for Different Secret and Missing Configuration**:
   - Add a test verifying that `create_asgi_app()` / server startup raises `RuntimeError` when neither `MCP_JWT_SECRET` nor `MCP_OAUTH_JWKS_URI` is set.
   - Add a test verifying that a token signed with an alternative secret (e.g. `secret="different-unauthorized-key"`) is rejected with HTTP 401 (`AuthenticationRequiredError` with `invalid_token` / signature mismatch) when the server is configured with a valid secret.
   - Update `tests/conftest.py` so test fixtures explicitly configure `MCP_JWT_SECRET` in `monkeypatch` / environment during testing.
4. **Enrich Documentation with Concrete Public URL and Execution Logs**:
   - Update `mcps/trackflow-server/README.md` and `specs/028-mcp-server-tools/quickstart.md` with:
     - A concrete, realistic public forwarded URL example (e.g. `https://crispy-space-umbrella-abc123-8001.app.github.dev/sse`).
     - Terminal session transcripts and MCP Playground interaction logs demonstrating discovery (`tools/list`) and invocation (`tools/call` for `create_incident`, `query_incidents`, `transition_incident_status`, and `query_inventory`).

**Alternatives**:
- *Require only JWKS/OIDC without symmetric secrets*: Remove HS256 JWT decoding entirely and require an external identity provider (IdP) publishing JWKS. *Trade-off*: Would break lightweight offline development and unit tests that rely on self-signed HMAC tokens without a running IdP server. Retaining both `MCP_OAUTH_JWKS_URI` and `MCP_JWT_SECRET` (with fail-fast validation) is optimal.

**Files likely to change**:
- `mcps/trackflow-server/src/trackflow_server/testing/token_helper.py`
- `mcps/trackflow-server/src/trackflow_server/testing/__init__.py`
- `mcps/trackflow-server/src/trackflow_server/auth/middleware.py`
- `mcps/trackflow-server/src/trackflow_server/auth/metadata.py`
- `mcps/trackflow-server/src/trackflow_server/app.py`
- `mcps/trackflow-server/src/trackflow_server/main.py`
- `mcps/trackflow-server/tests/conftest.py`
- `mcps/trackflow-server/tests/test_auth.py`
- `mcps/trackflow-server/README.md`
- `specs/028-mcp-server-tools/quickstart.md`
- `.env.example`

**Tests to add or update**:
- `test_server_startup_fails_when_jwt_secret_and_jwks_missing`: Assert that creating the application without `MCP_JWT_SECRET` and `MCP_OAUTH_JWKS_URI` raises a `RuntimeError`.
- `test_token_with_different_secret_rejected_with_401`: Assert that a token signed with a different key is rejected with `AuthenticationRequiredError`.
- Ensure all existing unit and integration tests in `test_auth.py`, `test_incident_tools.py`, `test_inventory_tool.py`, and `test_audit_logging.py` continue to pass with explicit test secret configuration.

## Risks & Considerations

- **Breaking Changes in Local Development**: Developers running `trackflow-mcp` locally without setting `MCP_JWT_SECRET` in their environment or `.env` file will now encounter a startup error. This is intentional and necessary for security; providing clear instructions and updating `.env.example` mitigates friction.
- **Test Suite Fixtures**: Tests must configure a mock secret (e.g., via `monkeypatch.setenv("MCP_JWT_SECRET", "test-secret")`) in `conftest.py` so they don't fail due to the new fail-fast validation.

## Open Questions

- None. The vulnerability and remediation requirements are clear and well-specified.
