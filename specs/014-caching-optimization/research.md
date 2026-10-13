# Research & Technical Decisions: Caching & Lazy Loading Optimization

## 1. Frontend Dynamic Loading Strategy

### Candidates Audited in `uis/website` and `uis/backoffice`
1. **`uis/backoffice/components/inventory/OrdersHistoryTable`**:
   - *Nature*: Heavy data table component rendering multi-column ledger rows, timestamp formatting, and badge widgets.
   - *Access Pattern*: Rendered on the `/inventory/orders` route after asynchronous data fetching.
   - *Decision*: Lazy load via `next/dynamic` with a dedicated loading skeleton fallback.
   - *Benefit*: Reduces initial JavaScript bundle weight for the inventory module and defers table rendering until data arrives.
2. **`uis/backoffice/components/inventory/ProductTable`**:
   - *Nature*: Product catalog table with dynamic stock calculations, warehouse mapping, and stock status badge components.
   - *Access Pattern*: Rendered on `/inventory/products`.
   - *Decision*: Lazy load via `next/dynamic` with skeleton placeholder.
   - *Benefit*: Defer table layout and status badge styling bundle until product records are ready to mount.
3. **`uis/backoffice/components/incidents/IncidentSummaryPanel` & `IncidentListPanel`**:
   - *Nature*: Multi-metric card grid and large incident management table with inline status switching.
   - *Access Pattern*: Rendered on `/incidents`.
   - *Decision*: Lazy load panels on `/incidents/page.tsx` via `next/dynamic` with loading spinners.
   - *Benefit*: Decouples summary card grid and filterable incident list rendering.

---

## 2. Frontend Memoization Strategy (`useMemo`)

### Candidates Audited
1. **Inventory Order Volume Aggregation (`OrdersHistoryTable`)**:
   - *Computation*: Iterates over all order records to compute composite summary metrics: total inbound units received, total outbound units dispatched, and net inventory delta across warehouses.
   - *Volatility*: Orders list changes only on API fetch/refresh, but parent component or sorting/paging re-renders trigger repeated iteration.
   - *Decision*: Wrap volume calculation in `useMemo(() => computeOrderMetrics(orders), [orders])`.
   - *Benefit*: Eliminates repeated $O(N)$ iterations over historical order arrays during unrelated UI state transitions.
2. **Product Stock Status Breakdown (`ProductTable` / `InventoryProductsPage`)**:
   - *Computation*: Derived summary totals (total products, low stock alerts, warehouse unit distributions).
   - *Decision*: Memoize calculated distribution metrics with `[products]` dependency.

---

## 3. Backend Endpoint Caching & Invalidation Architecture

### Endpoint Evaluation Matrix (`services/api/`)

| Endpoint | Operation Cost | Call Frequency | Data Volatility | Decision | TTL | Invalidation Triggers |
|---|---|---|---|---|---|---|
| `GET /suppliers` | **Moderate**: TinyDB file scan & country/category filter | **High**: Catalog views, dropdowns | **Low**: Updated only by admin | **CACHE** | `60s` | `POST /suppliers`, `PATCH /suppliers/{id}/*`, `DELETE /suppliers/{id}` |
| `GET /api/incidents/summary` | **High**: Aggregates multi-dimensional counts (status, category, origin, branch) | **Very High**: Dashboard overview & poller | **Moderate**: Updates on new report or status patch | **CACHE** | `30s` | `POST /api/incidents`, `PATCH /api/incidents/{id}/status`, `POST /api/incidents/analyze` |
| `GET /inventory/products` | **High**: SQLite ledger scan computing stock per SKU across all entries | **High**: Live stock dashboard & orders form | **Moderate**: Updates on stock movement | **CACHE** | `30s` | `POST /inventory/orders/inbound`, `POST /inventory/orders/outbound`, `POST /inventory/products` |
| `GET /auth/me` | **Low**: Single DB user lookup | **High**: Session verification | **High / Private**: Per-user auth | **DO NOT CACHE** | N/A | Contains private user profile; must never share in public cache. |
| `POST /auth/login` | **High (Bcrypt)** | **High** | **Non-idempotent** | **DO NOT CACHE** | N/A | Mutating / credential exchange. |
| `GET /api/incidents/results/export` | **Moderate (CSV stream)** | **Low**: On-demand download | **N/A**: Binary stream | **DO NOT CACHE** | N/A | Streaming file attachment. |

### Invalidation Strategy
- An in-memory cache manager (`services/api/infrastructure/cache.py`) maintains stored response bodies with timestamped TTL.
- Keys are namespaced by prefix (e.g., `suppliers:`, `incident_summary:`, `inventory_products:`).
- Parameterized queries incorporate serialized query parameters into composite cache keys (e.g., `suppliers:country=USA&category=raw_materials`).
- Mutation handlers invoke `cache.invalidate_prefix(prefix)` upon successful database writes.

---

## 4. Freshness vs. Performance Tradeoffs

### Explicit Freshness Tradeoff Decision
- **Chosen Endpoint**: `GET /suppliers` (TTL = 60s) and `GET /api/incidents/summary` (TTL = 30s).
- **Justification**: In high-concurrency environments, hundreds of dashboard viewers polling `/api/incidents/summary` every few seconds would otherwise execute expensive aggregate queries against the incident database. Under the 30-second TTL (with immediate write-through invalidation on any internal update), response times remain sub-millisecond, and the maximum window of data staleness for un-invalidated external changes is strictly bounded to 30 seconds, which is well within operational tolerances for high-level monitoring metrics.
