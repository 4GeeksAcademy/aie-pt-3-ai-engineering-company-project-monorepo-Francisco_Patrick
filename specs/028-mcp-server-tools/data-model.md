# Phase 1 Data Model: Standardized MCP Server & Agent Integration

**Feature**: `028-mcp-server-tools`  
**Date**: 2026-11-18  
**Status**: Ready  

## 1. Domain Entities & Schemas

### 1.1 MCP Tool Definition
Represents an exposed capability published by the MCP server for autonomous agent discovery.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | Yes | Unique tool name (`create_incident`, `query_incidents`, `transition_incident_status`, `query_inventory`). |
| `description` | `string` | Yes | Human- and agent-readable markdown documentation of the tool's purpose and usage constraints. |
| `input_schema` | `object` (JSON Schema) | Yes | Strict JSON schema specifying parameter types, required fields, and constraints. |
| `output_schema` | `object` (JSON Schema) | Yes | Structured response schema returned upon execution. |
| `required_scope` | `string` | Yes | OAuth 2.1 scope required to invoke this tool (`incidents:write`, `incidents:read`, `incidents:lifecycle`, `inventory:read`). |

---

### 1.2 Incident Ticket Entity
Represents an operational incident ticket within TrackFlow, aligning with the Incidents Manager domain model (`domain/incident_model.py` and `presentation/api/v1/incidents.py`).

| Field | Type | Constraints / Enum | Description |
|---|---|---|---|
| `id` | `string` | Pattern: `^INC-[A-Za-z0-9_-]+$` | Unique incident identifier assigned by the central system. |
| `title` | `string` | Min: 3 chars, Max: 200 chars | Summary title of the operational issue. |
| `description` | `string` | Min: 5 chars, Max: 2000 chars | Detailed explanation of the incident context. |
| `status` | `string` | `open`, `in_progress`, `resolved`, `discarded` | Current lifecycle state. |
| `category` | `string` | `warehouse`, `delay`, `damage`, `billing`, `stock`, `system`, `reverse_logistics`, `last_mile`, `customer_experience`, `other` | Problem classification category. |
| `origin` | `string` | `customer`, `branch`, `internal`, `warehouse`, `carrier`, `partner` | Source channel that reported the incident. |
| `branch` | `string` | Known branches: `zaragoza`, `los_angeles`, `valencia`, `central`, `madrid`, `barcelona`, `bilbao`, `sevilla` | Warehouse or operating branch location. |
| `created_at` | `string` (ISO 8601) | Timestamp | Record creation timestamp. |
| `updated_at` | `string` (ISO 8601) | Timestamp | Timestamp of last modification or status transition. |

#### Lifecycle State Transitions:
```text
           ┌───────────┐
           │   open    │
           └─────┬─────┘
                 │
       ┌─────────┴─────────┐
       ▼                   ▼
┌─────────────┐     ┌─────────────┐
│ in_progress │     │  discarded  │ (Terminal)
└──────┬──────┘     └─────────────┘
       │
       ▼
┌─────────────┐
│  resolved   │ (Terminal)
└─────────────┘
```
- **Allowed Transitions**:
  - `open` → `in_progress`
  - `open` → `discarded`
  - `in_progress` → `resolved`
  - `in_progress` → `discarded`
- **Disallowed Transitions (Rejected with `LIFECYCLE_TRANSITION_DISALLOWED`)**:
  - `resolved` → `open`, `in_progress`, or `discarded`
  - `discarded` → `open`, `in_progress`, or `resolved`
  - `open` → `resolved` (direct jump without `in_progress` is rejected by lifecycle rules)

---

### 1.3 Inventory Product Record
Represents physical stock availability and warehouse allocation, aligning with `domain/inventory/models.py`.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | `integer` | Positive integer | Unique numerical database identifier. |
| `sku` | `string` | Unique SKU string (e.g. `TF-001`, `SKU-A12`) | Stock Keeping Unit code. |
| `name` | `string` | Non-empty string | Commercial product name. |
| `description` | `string` | Optional string | Product description or specifications. |
| `stock` | `integer` | Non-negative integer (≥ 0) | Real-time calculated stock on hand. |
| `min_threshold` | `integer` | Non-negative integer (≥ 0) | Low stock trigger threshold. |
| `is_low_stock` | `boolean` | Computed (`stock <= min_threshold`) | Flag indicating low stock urgency. |
| `warehouse_id` | `string` | String identifier | Physical warehouse storing the stock. |

#### Read-Only Guardrail Rule:
The inventory capability is strictly read-only across the MCP interface:
- Tool parameters accept only: `sku` (optional string), `product_id` (optional integer), `query` (optional string).
- Any parameter payload indicating mutation intent (such as `action="create"`, `quantity_change`, `stock_adjustment`, `order_type`) triggers immediate rejection with `INVENTORY_MUTATION_REJECTED`.

---

### 1.4 OAuth Security Context
Authentication and authorization state validated from the caller's Bearer JWT token.

| Field | Type | Description |
|---|---|---|
| `client_id` | `string` | Registered OAuth 2.1 client identifier. |
| `subject` | `string` | User or machine subject identifier (`sub`). |
| `issuer` | `string` | Token issuer URL (`iss`). |
| `audience` | `string` | Intended recipient resource server identifier (`aud`). |
| `scopes` | `list[string]` | Granted permissions (e.g., `["incidents:read", "inventory:read"]`). |
| `expires_at` | `integer` | Token expiration UNIX epoch timestamp (`exp`). |

---

### 1.5 Audit Log Record
Traceability event emitted for every tool invocation.

| Field | Type | Description |
|---|---|---|
| `timestamp` | `string` (ISO 8601) | Execution timestamp in UTC. |
| `trace_id` | `string` (UUIDv4) | Unique end-to-end request trace ID. |
| `client_id` | `string` | Authenticated client ID (or `"unauthenticated"`). |
| `tool_name` | `string` | Name of the tool requested. |
| `arguments` | `object` | Sanitized input parameters (PII and secrets redacted). |
| `outcome` | `string` | Enum: `SUCCESS`, `REJECTED`, `ERROR`. |
| `error_code` | `string` (optional) | Canonical error code if outcome is `REJECTED` or `ERROR`. |
| `latency_ms` | `float` | Tool execution duration in milliseconds. |

---

## 2. Categorized Error Taxonomy

All errors returned by the MCP Server use standardized error models:

| Error Code | HTTP / RPC Status | Description |
|---|---|---|
| `AUTHENTICATION_REQUIRED` | `401 Unauthorized` / `-32001` | Missing, expired, or malformed Bearer JWT token. |
| `INSUFFICIENT_SCOPE` | `403 Forbidden` / `-32003` | Client token lacks the required scope for the target tool. |
| `INVENTORY_MUTATION_REJECTED` | `403 Forbidden` / `-32003` | Prohibited write or mutation attempted on read-only inventory. |
| `VALIDATION_ERROR` | `422 Unprocessable` / `-32602` | Input arguments fail Pydantic or JSON schema validation. |
| `LIFECYCLE_TRANSITION_DISALLOWED`| `400 Bad Request` / `-32004` | Invalid incident status change per state machine rules. |
| `RESOURCE_NOT_FOUND` | `404 Not Found` / `-32005` | Requested incident ID or SKU does not exist. |
| `UPSTREAM_UNAVAILABLE` | `503 Unavailable` / `-32002` | Incidents Manager API or Inventory database timed out or unreachable. |
