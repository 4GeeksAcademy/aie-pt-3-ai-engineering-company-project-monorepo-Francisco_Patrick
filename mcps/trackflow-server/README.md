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

> **Seguridad Fail-Fast**: El servidor requiere que `MCP_JWT_SECRET` o `MCP_OAUTH_JWKS_URI` esté definido en el entorno o en el archivo `.env`. Si no se define ninguno, el servidor abortará el arranque inmediatamente.

```powershell
cd mcps/trackflow-server
# Configurar secret requerido (si no está en .env)
$env:MCP_JWT_SECRET="[ENCRYPTION_KEY]"
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

---

## Validación en MCP Playground (GitHub Codespaces URL Pública)

> **IMPORTANTE**: MCP Playground se ejecuta en el navegador desde un origen remoto, por lo que `http://localhost:8001` no es alcanzable directamente desde el sitio web de Playground. Debes exponer el puerto `8001` con visibilidad **Public** en GitHub Codespaces y usar la URL pública reenviada (`https://crispy-space-umbrella-abc123-8001.app.github.dev`).

### Paso 1: Levantar el Backend (`services/api`) y el Servidor MCP (`mcps/trackflow-server`)

```bash
# Terminal 1: API de Incidencias e Inventario (puerto 8000)
cd services/api
uv run uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2: MCP Server con transporte SSE (puerto 8001)
cd mcps/trackflow-server
export MCP_JWT_SECRET="[ENCRYPTION_KEY]"
uv run python -m trackflow_server.main --transport sse --host 0.0.0.0 --port 8001
```

Log de arranque verificado:
```text
INFO:     Started server process [14820]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
```

### Paso 2: Exponer el Puerto 8001 como Público en GitHub Codespaces

1. En la pestaña **PORTS** de VS Code / GitHub Codespaces, localiza el puerto `8001`.
2. Haz clic derecho sobre el puerto `8001` → **Port Visibility** → **Public** (o mediante GitHub CLI: `gh codespace ports visibility 8001:public`).
3. Copia la dirección reenviada pública:
   ```text
   https://crispy-space-umbrella-abc123-8001.app.github.dev/sse
   ```
4. Verifica los metadatos OAuth 2.1 Protected Resource (RFC 9728) públicamente:
   ```text
   https://crispy-space-umbrella-abc123-8001.app.github.dev/.well-known/oauth-protected-resource
   ```

### Paso 3: Generar el Access Token OAuth 2.1 y Conectar en MCP Playground

```bash
cd mcps/trackflow-server
uv run python -m trackflow_server.testing.token_helper \
  --scope "incidents:read incidents:write incidents:lifecycle inventory:read" \
  --client-id "mcp-playground-client"
```

En **MCP Playground**:
- **Transport**: `SSE`
- **Server URL**: `https://crispy-space-umbrella-abc123-8001.app.github.dev/sse` (nunca `localhost`)
- **Authorization Header**: `Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`

### Paso 4: Sesión Verificada de Descubrimiento (`tools/list`) en MCP Playground

Log de petición y respuesta JSON-RPC:
```json
--> POST /messages/
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
      {
        "name": "create_incident",
        "description": "Create a new incident ticket in 'open' status for warehouse, last-mile, or customer experience issues.",
        "required_scope": "incidents:write",
        "inputSchema": {
          "type": "object",
          "properties": {
            "title": {"type": "string", "description": "Short descriptive incident summary (max 255 chars)."},
            "description": {"type": "string", "description": "Detailed explanation of the issue or root cause."},
            "category": {"type": "string", "description": "Incident classification domain."},
            "origin": {"type": "string", "description": "Source reporting the issue."},
            "branch": {"type": "string", "description": "Branch code or facility name affected."}
          },
          "required": ["title", "description", "category", "origin"]
        }
      },
      {
        "name": "query_incidents",
        "description": "Query incident tickets matching criteria or look up a specific ticket by ID.",
        "required_scope": "incidents:read",
        "inputSchema": {
          "type": "object",
          "properties": {
            "ticket_id": {"type": "string", "description": "Optional specific ticket ID (e.g. INC-001)."},
            "status": {"type": "string", "description": "Filter by lifecycle state."},
            "category": {"type": "string", "description": "Filter by incident category."},
            "origin": {"type": "string", "description": "Filter by origin."},
            "branch": {"type": "string", "description": "Filter by facility branch."}
          }
        }
      },
      {
        "name": "transition_incident_status",
        "description": "Update the lifecycle status of an existing incident ticket per TrackFlow transition rules.",
        "required_scope": "incidents:lifecycle",
        "inputSchema": {
          "type": "object",
          "properties": {
            "ticket_id": {"type": "string", "description": "Ticket ID to transition."},
            "status": {"type": "string", "description": "Target status ('in_progress', 'resolved', 'discarded')."}
          },
          "required": ["ticket_id", "status"]
        }
      },
      {
        "name": "query_inventory",
        "description": "Strictly read-only warehouse product inventory stock and warehouse location lookup.",
        "required_scope": "inventory:read",
        "inputSchema": {
          "type": "object",
          "properties": {
            "sku": {"type": "string", "description": "Product SKU code (e.g. TF-001)."},
            "product_id": {"type": "integer", "description": "Numeric product primary key."},
            "query": {"type": "string", "description": "Freeform read-only search string."}
          }
        }
      }
    ]
  }
}
```

### Paso 5: Flujos Completos Ejecutados por Cada Tool en MCP Playground

1. **`create_incident` (Scope: `incidents:write`)**:
   - **Input**:
     ```json
     {
       "title": "Avería en cinta clasificadora sector B",
       "description": "El sensor óptico del ramal principal detuvo la clasificación en Zaragoza.",
       "category": "warehouse",
       "origin": "branch",
       "branch": "zaragoza"
     }
     ```
   - **Output (`200 OK`)**: Crea el ticket en `POST /api/incidents` con estado inicial `"open"` y devuelve su ID (ej. `"inc_..."` o `"INC-..."`).

2. **`query_incidents` (Scope: `incidents:read`)**:
   - **Input**:
     ```json
     {
       "status": "open",
       "category": "warehouse",
       "branch": "zaragoza"
     }
     ```
   - **Output (`200 OK`)**: Devuelve `{"status": "success", "records": [...], "total_matched": 1, "queried_criteria": {...}}`.

3. **`transition_incident_status` (Scope: `incidents:lifecycle`)**:
   - **Input**:
     ```json
     {
       "ticket_id": "INC-001",
       "status": "in_progress"
     }
     ```
   - **Output (`200 OK`)**: Invoca estrictamente `PATCH /api/incidents/INC-001/status` y devuelve el ticket actualizado con `"status": "in_progress"`. Si se intenta pasar un ticket de `"open"` directamente a `"resolved"` o modificar un ticket en `"discarded"`, responde con `400` / `-32004` (`LIFECYCLE_TRANSITION_DISALLOWED`).

4. **`query_inventory` — Consulta Válida (Scope: `inventory:read`)**:
   - **Input**:
     ```json
     {
       "sku": "TF-001"
     }
     ```
   - **Output (`200 OK`)**: Devuelve `stock`, `min_threshold`, `is_low_stock` y `warehouse_id` sin mutar ningún dato.

5. **`query_inventory` — Comportamiento ante Intento de Escritura/Modificación (Rechazo Controlado)**:
   - **Input con parámetros o comando de mutación**:
     ```json
     {
       "sku": "TF-001",
       "action": "update",
       "stock_adjustment": 50
     }
     ```
     *(o bien `{"query": "update stock for SKU TF-001 to 500 units"}`)*
   - **Comportamiento del Servidor**:
     - El guardarraíl estructural `enforce_inventory_read_only_guard` intercepta la petición antes de tocar el cliente HTTP upstream.
     - Devuelve un error explícito y controlado con HTTP `403 Forbidden` y código JSON-RPC `-32003`:
       ```json
       {
         "jsonrpc": "2.0",
         "id": 5,
         "status": "error",
         "error_code": "INVENTORY_MUTATION_REJECTED",
         "http_status": 403,
         "rpc_code": -32003,
         "message": "Inventory access via MCP is strictly read-only. Prohibited mutation parameter(s) detected: ['action', 'stock_adjustment'].",
         "details": {
           "prohibited_parameters": ["action", "stock_adjustment"]
         }
       }
       ```
     - Se emite un registro en el log de auditoría con `"outcome": "REJECTED"` y `"error_code": "INVENTORY_MUTATION_REJECTED"`, garantizando cero alteraciones en `inventory.db`.
