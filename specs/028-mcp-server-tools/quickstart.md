# Quickstart & Validation Guide: MCP Server & Support Agent

**Feature**: `028-mcp-server-tools`  
**Date**: 2026-11-18  

This guide provides step-by-step instructions for running, testing, and verifying the standardized MCP Server and the refactored Support Agent end-to-end.

---

## 1. Prerequisites & Environment Setup

- Python 3.14+ installed
- `uv` package manager installed (`uv --version >= 0.12.0`)
- Running backend service (`services/api`) or local test database seeded with `python seed.py`

### 1.1 Install Dependencies

```powershell
# From repo root:
# 1. Install MCP server dependencies in mcps/trackflow-server
cd mcps/trackflow-server
uv sync

# 2. Ensure services/api has langchain-mcp-adapters installed
cd ../../services/api
uv add langchain-mcp-adapters
```

---

## 2. Running the MCP Server

The MCP server supports both HTTP/SSE transport (for remote clients, inspection tools, and playground) and stdio transport (for local CLI integration).

### Scenario A: Start HTTP/SSE Transport (Default for Remote & Web Clients)

> **Fail-Fast Security Note**: The server requires either `MCP_JWT_SECRET` or `MCP_OAUTH_JWKS_URI` to be set in `.env` or in the environment before starting. If absent, the server fails fast with `RuntimeError`.

```powershell
cd mcps/trackflow-server
$env:MCP_JWT_SECRET="[ENCRYPTION_KEY]"
uv run python -m trackflow_server.main --transport sse --host 0.0.0.0 --port 8001
```

- **Local SSE Stream Endpoint**: `http://localhost:8001/sse`
- **GitHub Codespaces Public Forwarded SSE Endpoint (for MCP Playground)**: `https://crispy-space-umbrella-abc123-8001.app.github.dev/sse`
- **Messages Endpoint**: `https://crispy-space-umbrella-abc123-8001.app.github.dev/messages/`
- **Protected Resource Metadata**: `https://crispy-space-umbrella-abc123-8001.app.github.dev/.well-known/oauth-protected-resource`

### Scenario B: Connecting from MCP Playground via GitHub Codespaces Public URL

1. Forward port `8001` in GitHub Codespaces and change **Port Visibility** to **Public** (`gh codespace ports visibility 8001:public`).
2. Mint a Bearer JWT token with `uv run python -m trackflow_server.testing.token_helper`.
3. Paste `https://crispy-space-umbrella-abc123-8001.app.github.dev/sse` into **MCP Playground** (do not use `localhost` in Playground) with header `Authorization: Bearer <TOKEN>`.
4. Execute complete flows for `create_incident`, `query_incidents`, `transition_incident_status`, and `query_inventory` (both read and rejected write attempts returning `INVENTORY_MUTATION_REJECTED`).

#### Live MCP Playground Execution Logs

**Discovery (`tools/list`)**:
```json
--> POST https://crispy-space-umbrella-abc123-8001.app.github.dev/messages/
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}

<-- 200 OK
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {"name": "create_incident", "required_scope": "incidents:write", "description": "Create a new incident ticket in 'open' status for warehouse, last-mile, or customer experience issues."},
      {"name": "query_incidents", "required_scope": "incidents:read", "description": "Query incident tickets matching criteria or look up a specific ticket by ID."},
      {"name": "transition_incident_status", "required_scope": "incidents:lifecycle", "description": "Update the lifecycle status of an existing incident ticket per TrackFlow transition rules."},
      {"name": "query_inventory", "required_scope": "inventory:read", "description": "Strictly read-only warehouse product inventory stock and warehouse location lookup."}
    ]
  }
}
```

**Tool Invocation (`tools/call` - `create_incident`)**:
```json
--> POST https://crispy-space-umbrella-abc123-8001.app.github.dev/messages/
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "create_incident",
    "arguments": {
      "title": "Avería en cinta clasificadora sector B",
      "description": "El sensor óptico del ramal principal detuvo la clasificación en Zaragoza.",
      "category": "warehouse",
      "origin": "branch",
      "branch": "zaragoza"
    }
  }
}

<-- 200 OK
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "status": "success",
    "ticket": {
      "id": "INC-101",
      "title": "Avería en cinta clasificadora sector B",
      "status": "open",
      "category": "warehouse",
      "origin": "branch",
      "branch": "zaragoza"
    }
  }
}
```

---

## 3. End-to-End Validation Scenarios

### Scenario 1: Authentication & Scope Verification
Verify that unauthenticated requests and requests with invalid scopes are rejected.

**Command (Unauthenticated)**:
```powershell
curl -i http://localhost:8001/sse
```
- **Expected Outcome**: HTTP `401 Unauthorized` with header `WWW-Authenticate: Bearer error="invalid_token"`.

**Command (Authenticated with Read Scope, attempting Write)**:
```powershell
# Generate a test token with scope="incidents:read"
$TOKEN = $(uv run python -m trackflow_server.testing.token_helper --scope "incidents:read")

curl -X POST http://localhost:8001/messages/ `
  -H "Authorization: Bearer $TOKEN" `
  -H "Content-Type: application/json" `
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "create_incident", "arguments": {"title": "Test", "description": "Desc", "category": "warehouse", "origin": "branch", "branch": "zaragoza"}}}'
```
- **Expected Outcome**: Execution rejected with error code `INSUFFICIENT_SCOPE` (`-32003` / HTTP 403) and detail explaining that `incidents:write` is required.

---

### Scenario 2: Incident Management Lifecycle via MCP Tool
Verify creating an incident, querying it, and transitioning its status per lifecycle rules.

1. **Create Incident**:
   - Token scope: `incidents:write`
   - Invokes `create_incident`
   - **Expected Outcome**: Returns newly created incident with assigned ID (e.g., `INC-101`) in `open` status.

2. **Transition Incident to In Progress**:
   - Token scope: `incidents:lifecycle`
   - Invokes `transition_incident_status` with `{"ticket_id": "INC-101", "status": "in_progress"}`
   - **Expected Outcome**: Updated record returned with `status: "in_progress"`.

3. **Attempt Disallowed Transition (Negative Validation)**:
   - Invokes `transition_incident_status` attempting to transition directly from `open` to `resolved` or modifying a `discarded` ticket.
   - **Expected Outcome**: Rejected with `LIFECYCLE_TRANSITION_DISALLOWED` without modifying the state.

---

### Scenario 3: Strictly Read-Only Inventory Protection
Verify that inventory stock can be inspected, but any mutation attempt is immediately blocked.

1. **Read Valid SKU**:
   - Token scope: `inventory:read`
   - Invokes `query_inventory` with `{"sku": "TF-001"}`
   - **Expected Outcome**: Returns product stock level, location, and threshold warning.

2. **Attempt Stock Mutation (Negative Validation)**:
   - Invokes `query_inventory` passing mutation parameters (e.g. `{"sku": "TF-001", "action": "update", "stock_adjustment": 50}`)
   - **Expected Outcome**: Request is rejected with `INVENTORY_MUTATION_REJECTED` code and zero changes made to `inventory.db`.

---

### Scenario 4: Automated Support Agent Integration
Verify the LangGraph Support Agent workflow uses the MCP adapter and preserves multi-source routing.

```powershell
cd services/api
uv run pytest tests/integration/test_agent_routes.py tests/unit/test_agent_workflow.py -v
```
- **Expected Outcome**: All tests pass cleanly, confirming that:
  - Agent delegates incident queries to the MCP client adapter.
  - Multi-source inquiry (ticket lookup + RAG policy query) completes successfully with grounded citations.
  - Legacy direct internal calling node is decommissioned.
