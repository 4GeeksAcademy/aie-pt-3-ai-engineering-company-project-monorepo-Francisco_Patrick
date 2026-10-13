# Data Model: Caching & Optimization

## 1. Backend In-Memory Cache Entry Entity

### Entity: `CacheEntry`
Represents an individual cached response value in the server runtime memory cache.

| Field | Type | Description |
|---|---|---|
| `key` | `str` | Unique composite identifier (e.g., `suppliers:country=USA&category=packaging`) |
| `value` | `Any` | Serialized JSON-compatible payload or response object |
| `expires_at` | `float` | Monotonic or epoch timestamp after which the entry is considered expired |
| `created_at` | `float` | Creation timestamp used for telemetry and cache age calculation |

### Invalidation Triggers & Mappings

| Prefix / Namespace | Invalidation Scope | Triggering Endpoints |
|---|---|---|
| `suppliers:` | All supplier list and detail queries | `POST /suppliers`, `PATCH /suppliers/{id}/rate`, `PATCH /suppliers/{id}/status`, `DELETE /suppliers/{id}` |
| `incident_summary:` | Global incident counts summary | `POST /api/incidents`, `PATCH /api/incidents/{id}/status`, `POST /api/incidents/analyze` |
| `inventory_products:` | Product stock list and detail queries | `POST /inventory/orders/inbound`, `POST /inventory/orders/outbound`, `POST /inventory/products` |

---

## 2. Frontend Memoized Metric Entities

### Entity: `OrdersLedgerSummary`
Computed on the client side via `useMemo` from `readonly InventoryOrderRecord[]`.

| Field | Type | Description |
|---|---|---|
| `totalInboundUnits` | `number` | Sum of all quantities where `order_type === 'inbound'` |
| `totalOutboundUnits` | `number` | Sum of all quantities where `order_type === 'outbound'` |
| `netMovement` | `number` | Difference (`totalInboundUnits - totalOutboundUnits`) |
| `inboundCount` | `number` | Total count of inbound transactions |
| `outboundCount` | `number` | Total count of outbound transactions |
