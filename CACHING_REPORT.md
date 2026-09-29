# TrackFlow Caching & Performance Optimization Report

This report documents the performance optimizations implemented across the TrackFlow monorepo, covering client-side dynamic loading and memoization in `uis/backoffice` and `uis/website`, server-side query caching with TTL and invalidation in `services/api/`, architectural freshness tradeoffs, and justified exclusions.

---

## 1. Frontend Decisions

### 1.1 Dynamic Lazy Loading (`next/dynamic`)

| Component | Target Route | Justification & Architecture Decision | Fallback Placeholder |
|---|---|---|---|
| **`OrdersHistoryTable`** | `/inventory/orders` | The historical orders ledger renders multi-column transaction tables, status badges, and timestamp formatting for hundreds of stock movements. Deferring this component until after the initial client shell is mounted significantly reduces initial bundle execution time and improves Time to Interactive (TTI). | Animated KPI card grid and ledger table skeleton |
| **`ProductTable`** | `/inventory/products` | The product inventory table includes stock level calculation badges, warehouse location indicators, and order action buttons. Deferring this table decouples the page header and navigation shell from heavy table rendering. | Animated multi-row table skeleton |
| **`IncidentSummaryPanel` & `IncidentListPanel`** | `/incidents` | The centralized incident management dashboard mounts a multi-metric KPI summary grid and an interactive, filterable incident list. Splitting both into independent dynamic chunks ensures the dashboard shell renders immediately while the panels load in parallel. | Tailored card and table pulse skeletons |
| **`BenefitsSection`, `HowItWorksSection`, `ExperienceSection`, `ApplicationForm`** | `/` and `/application` (Website) | Public marketing sections below the fold and the client onboarding application form are dynamically imported to maximize First Contentful Paint (FCP) and Largest Contentful Paint (LCP) on mobile networks. | Component-specific skeleton fallbacks |

---

### 1.2 Memoization Strategy (`useMemo`)

| Target Component | Computed Value | Computation Complexity | Measured / Estimated Benefit |
|---|---|---|---|
| **`OrdersHistoryTable.tsx`** | `OrdersLedgerSummary` (`totalInboundUnits`, `totalOutboundUnits`, `netMovement`, `inboundCount`, `outboundCount`) | $O(N)$ iteration over the full orders array aggregating inbound/outbound volumes and computing net inventory deltas across warehouses. | **Eliminates redundant recalculations**: When parent components re-render or unrelated UI states update, the multi-metric volume calculation is skipped as long as `orders` reference remains stable. Renders real-time KPI cards above the audit ledger without performance penalties. |

---

## 2. Backend Decisions

### 2.1 Complete API Endpoint Evaluation Matrix (`services/api/`)

All 31 backend endpoints were audited against computational cost, request frequency, and data change volatility:

| Endpoint | Method | Operation Cost | Call Frequency | Data Volatility | Decision | TTL | Invalidation Triggers |
|---|---|---|---|---|---|---|---|
| `/api/incidents/summary` | `GET` | **High**: Scans all incidents; calculates 4-dimension aggregation (status, category, origin, branch). | **Very High**: Queried on dashboard load and periodic polling. | **Moderate**: Changes on new incident or status transition. | **CACHE** | `30s` | `POST /api/incidents`, `PATCH /api/incidents/{id}/status`, `POST /api/incidents/analyze` |
| `/suppliers` | `GET` | **Moderate**: TinyDB table scan with country/category filtering. | **High**: Supplier catalog views and order form dropdowns. | **Low**: Updated only during administrative supplier changes. | **CACHE** | `60s` | `POST /suppliers`, `PATCH /suppliers/{id}/rate`, `PATCH /suppliers/{id}/status`, `DELETE /suppliers/{id}` |
| `/suppliers/{id}` | `GET` | **Low**: Single TinyDB document lookup. | **Moderate**: Supplier detail views. | **Low**: Infrequently updated. | **CACHE** | `60s` | `PATCH /suppliers/{id}/*`, `DELETE /suppliers/{id}` |
| `/inventory/products` | `GET` | **High**: SQLite query joining `sku` table and dynamically aggregating all historical `stock_entry` records. | **High**: Stock monitoring views, order forms, dashboard. | **Moderate**: Changes on stock movement. | **CACHE** | `30s` | `POST /inventory/orders/inbound`, `POST /inventory/orders/outbound`, `POST /inventory/products` |
| `/inventory/products/{id}` | `GET` | **Moderate**: Single SKU lookup with stock aggregation. | **Moderate**: Order detail modals. | **Moderate**: Changes on stock movement. | **CACHE** | `30s` | `POST /inventory/orders/*` |
| `/inventory/orders` | `GET` | **Moderate**: Transaction ledger scan. | **Moderate**: Audit ledger views. | **Moderate**: Changes on new orders. | **DO NOT CACHE** | N/A | High audit sensitivity; served directly from DB. |
| `/api/incidents` | `GET` | **Moderate**: Multi-attribute filtered query. | **High**: Incident table list with search. | **Moderate**: Changes on new incident. | **DO NOT CACHE** | N/A | Highly variable query parameters with pagination. |
| `/api/incidents/{id}` | `GET` | **Low**: Single document lookup. | **Moderate**: Detail modal. | **Moderate**: Lifecycle updates. | **DO NOT CACHE** | N/A | Low cost; direct DB query sufficient. |
| `/api/incidents/results/export` | `GET` | **Moderate (Stream)**: CSV stream serialization. | **Low**: On-demand download. | **N/A**: Binary stream buffer. | **DO NOT CACHE** | N/A | Streaming file attachment. |
| `/auth/me` | `GET` | **Low**: User lookup by JWT subject. | **High**: Session verification. | **High / Private**: Per-user auth state. | **DO NOT CACHE** | N/A | Private session identity. |
| `/profiles/me` | `GET` | **Low**: Profile lookup by user ID. | **Moderate**: User account view. | **Private**: Per-user data. | **DO NOT CACHE** | N/A | Private profile data. |
| `/users` | `GET` | **Low**: User table scan. | **Low**: Admin user management. | **Low**: Admin-only. | **DO NOT CACHE** | N/A | Security-sensitive user administration. |
| `/users/{id}` | `GET` | **Low**: User lookup. | **Low**: Admin user view. | **Low**: Admin-only. | **DO NOT CACHE** | N/A | Security-sensitive user administration. |
| *All Write Endpoints* (`POST`, `PUT`, `PATCH`, `DELETE`) | *Mutations* | **Variable**: DB writes & validations. | **Variable** | **Non-idempotent** | **DO NOT CACHE** | N/A | All write operations bypass cache and trigger immediate invalidation. |

---

### 2.2 Server-Side Cache Implementation Architecture

- **Engine**: In-memory `ResponseCache` ([services/api/infrastructure/cache.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/infrastructure/cache.py)) built with `threading.Lock` and monotonic timestamp expiration.
- **Namespacing**: Cache keys use composite parameter namespaces:
  - `incident_summary:global`
  - `suppliers:country={country}&category={category}`
  - `suppliers:{id}`
  - `inventory_products:all`
  - `inventory_products:{id}`
- **Write-Through Invalidation**: Every mutating API route calls `response_cache.invalidate_prefix(prefix)` immediately upon database commit, ensuring subsequent reads receive fresh data.

---

## 3. Tradeoffs Acknowledged: Freshness vs. Performance

### 3.1 Data Freshness Tradeoff Analysis
- **Chosen TTLs**: 30 seconds for `/api/incidents/summary` and `/inventory/products`; 60 seconds for `/suppliers`.
- **Operational Justification**:
  - In high-concurrency environments with multiple operators viewing dashboards, repeat queries execute against memory instead of triggering heavy database aggregate scans (e.g., summing thousands of stock ledger entries per SKU or counting multi-dimensional incident metrics).
  - **Why this level of staleness is acceptable**:
    1. **Immediate Internal Invalidation**: Any operator action performing a create, update, status patch, or order registration immediately purges the relevant cache prefix across the entire application instance.
    2. **Bounded Window for External Mutations**: In the rare event of asynchronous background ingestion or third-party webhooks modifying data outside direct route handlers, the maximum discrepancy window is strictly bounded to 30 seconds (or 60 seconds for suppliers), which is well within operational tolerances for summary metrics and supplier catalogs.

---

## 4. What Was Not Cached and Why

1. **Authentication & User Identity (`GET /auth/me`, `GET /profiles/me`, `GET /users/*`)**:
   - *Reason*: Storing per-user or session-specific identity payloads in a shared cache creates severe security risks (potential token leakage or cache poisoning). User profile and authentication routes are kept strictly uncached.
2. **Dynamic Streaming Responses (`GET /api/incidents/results/export`)**:
   - *Reason*: Generates an on-demand `StreamingResponse` with CSV attachment headers from dynamic stream buffers. Caching binary streams in memory increases heap pressure with minimal benefit.
3. **Audit Ledger Logs (`GET /inventory/orders`)**:
   - *Reason*: As a legal and compliance audit log of financial stock entries and exits, absolute real-time accuracy is required without intermediary caching.
4. **All Mutation Routes (`POST`, `PUT`, `PATCH`, `DELETE`)**:
   - *Reason*: Write operations are non-idempotent and modify state. They act as invalidation triggers rather than cache targets.
