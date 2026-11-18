# TrackFlow Standardized MCP Server (`trackflow-server`)

Standardized Model Context Protocol (MCP) Server exposing TrackFlow operational tools protected by OAuth 2.1 / OIDC Bearer authentication, RFC 9728 Protected Resource Metadata, fine-grained scope enforcement, and structured JSON audit logging.

---

## Architecture & Key Design Decisions

1. **Independent Package Boundary (`mcps/trackflow-server`)**:
   - Decoupled from `services/api`, communicating exclusively via upstream HTTP REST APIs (`/api/incidents` and `/api/v1/inventory`) using `httpx.AsyncClient` with a hard 4.0-second timeout (`UPSTREAM_UNAVAILABLE` on timeout or 5xx).
2. **Transport Protocol (HTTP/SSE Primary + stdio Local Option)**:
   - Defaults to **HTTP with Server-Sent Events (SSE)** (`--transport sse --port 8001`) so remote agents, cloud-forwarded ports (GitHub Codespaces), MCP Inspector/Playground, and `langchain-mcp-adapters` (`SSEConnection`) can connect over HTTP with standard `Authorization: Bearer <token>` headers.
   - Supports `--transport stdio` for local subprocess integrations.
3. **OAuth 2.1 Resource Server & Least-Privilege Scope Matrix**:
   - Powered by `mcpauth` and `PyJWT`, publishing RFC 9728 Protected Resource Metadata at `GET /.well-known/oauth-protected-resource` and OAuth Server Metadata at `GET /.well-known/oauth-authorization-server`.
   - Enforces fine-grained per-tool scopes:
     | MCP Tool | Required Scope | Capability |
     |---|---|---|
     | `create_incident` | `incidents:write` | Create a new incident ticket in `open` status |
     | `query_incidents` | `incidents:read` | Query incident tickets by ID or filters (`status`, `category`, `origin`, `branch`) |
     | `transition_incident_status` | `incidents:lifecycle` | Transition status (`in_progress`, `resolved`, `discarded`) strictly via `PATCH /api/incidents/{id}/status` |
     | `query_inventory` | `inventory:read` | Strictly read-only warehouse stock lookup by `sku`, `product_id`, or `query` |
4. **Structural Read-Only Inventory Guardrail (`INVENTORY_MUTATION_REJECTED`)**:
   - No write, adjustment, or order-creation tools exist on the server.
   - Any attempt to pass mutation parameters (`action`, `stock_adjustment`, `quantity_change`, `order_type`, etc.) or mutation commands in `query_inventory` is intercepted prior to upstream execution and rejected with HTTP 403 / JSON-RPC `-32003` (`INVENTORY_MUTATION_REJECTED`).
5. **Structured Audit Logging with PII & Secret Redaction**:
   - 100% of tool executions emit structured JSON audit records (`timestamp`, `trace_id`, `client_id`, `tool_name`, `arguments`, `outcome`, `error_code`, `latency_ms`) with customer email addresses, JWTs, Bearer tokens, and secret keys automatically masked.

---

## Quickstart

### 1. Install Dependencies

```powershell
cd mcps/trackflow-server
uv sync
```

### 2. Run the MCP Server (HTTP/SSE Transport)

```powershell
cd mcps/trackflow-server
uv run python -m trackflow_server.main --transport sse --port 8001
```

Endpoints:
- **SSE Stream**: `http://localhost:8001/sse`
- **JSON-RPC Messages**: `http://localhost:8001/messages/`
- **RFC 9728 Protected Resource Metadata**: `http://localhost:8001/.well-known/oauth-protected-resource`
- **Health Check**: `http://localhost:8001/health`

### 3. Generate a Test OAuth 2.1 Bearer Token

```powershell
cd mcps/trackflow-server
uv run python -m trackflow_server.testing.token_helper --scope "incidents:read incidents:write incidents:lifecycle inventory:read"
```

### 4. Run Test Suite

```powershell
cd mcps/trackflow-server
uv run pytest -v
```
