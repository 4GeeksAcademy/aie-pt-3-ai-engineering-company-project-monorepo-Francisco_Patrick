# Feature Specification: Dual Database Architecture + Inventory ORM

**Feature Branch**: `010-dual-db-inventory-orm`

**Created**: 2026-09-17

**Status**: Draft

**Input**: User description: "The FastAPI application must connect to two databases simultaneously: TinyDB (existing, for users and authentication) and Supabase (new, for inventory and orders). All products and stock must live in Supabase. Stock must not be a directly editable column; it is always derived from the order history. Inbound orders increment stock; outbound orders reduce it. They reference the TinyDB user UUID (NO user table is replicated in Supabase). Check your CONTEXT.md — entity names, field constraints, and business rules are company-specific."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Multi-Database Initialization & Product Management (Priority: P1)

As a TrackFlow logistics operator or developer, I want the system to connect to both TinyDB (for authentication) and Supabase (for inventory), allowing authenticated users to register SKUs across warehouses (Los Angeles and Zaragoza) without directly setting stock levels.

**Why this priority**: Core architectural foundation; establishing the dual-database connection and SQLModel ORM models is required before any stock calculations or order tracking can occur.

**Independent Test**: Can be independently tested by starting the application, verifying database connections, creating a SKU via `POST /inventory/products` with valid JWT credentials, and confirming initial `current_stock` resolves to 0.

**Acceptance Scenarios**:

1. **Given** a running FastAPI server with valid `.env` credentials, **When** the application starts, **Then** both TinyDB and Supabase SQLModel connections are initialized, and SQLModel tables (`sku`, `stock_entry`, `stock_exit`) are automatically created in Supabase.
2. **Given** an authenticated warehouse user (with JWT from TinyDB), **When** a `POST /inventory/products` request is sent with SKU code, name, and warehouse identifier (`wh-la` or `wh-zgz`), **Then** the product is persisted in Supabase and returned with a initial calculated `current_stock` of 0.
3. **Given** an unauthenticated request to `POST /inventory/products`, **When** sent to the server, **Then** the request is rejected with HTTP `401 Unauthorized`.

---

### User Story 2 - Inbound & Outbound Stock Adjustments via Orders (Priority: P2)

As a warehouse operator in Los Angeles (`wh-la`) or Zaragoza (`wh-zgz`), I want to record inbound inventory arrivals and outbound shipments so that current stock levels update dynamically based on order history.

**Why this priority**: Enables core inventory movement and ensures stock is strictly derived from verified transaction logs rather than arbitrary field edits.

**Independent Test**: Can be tested by creating an inbound order (`POST /inventory/orders/inbound`), verifying `current_stock` increases accordingly on `GET /inventory/products/{id}`, and creating a valid outbound order (`POST /inventory/orders/outbound`) to confirm stock decreases.

**Acceptance Scenarios**:

1. **Given** an existing SKU and an authenticated user, **When** `POST /inventory/orders/inbound` is called with quantity 50 for warehouse `wh-la`, **Then** a `StockEntry` record is saved storing the TinyDB `user_uuid`, and the product's `current_stock` for `wh-la` increases by 50.
2. **Given** a product with 50 units in `wh-la`, **When** `POST /inventory/orders/outbound` is called with quantity 20 for warehouse `wh-la`, **Then** a `StockExit` record is saved storing the creator's `user_uuid`, and `current_stock` evaluates to 30.
3. **Given** an authenticated request to `GET /inventory/orders`, **When** called, **Then** all inbound and outbound transactions are listed with associated product metadata, quantities, timestamps, and creator `user_uuid` strings.

---

### User Story 3 - Stock Boundary Protection & Multi-Warehouse Isolation (Priority: P3)

As a inventory manager, I want the system to enforce stock constraints per warehouse partition and prevent any outbound order that would result in negative stock.

**Why this priority**: Protects supply chain integrity by preventing overselling or stock allocation errors across geographically distinct warehouses.

**Independent Test**: Can be tested by attempting to submit an outbound order exceeding available stock for a specific warehouse and verifying an immediate HTTP 400 rejection without database mutation.

**Acceptance Scenarios**:

1. **Given** a SKU with 10 units in warehouse `wh-la`, **When** an outbound order for 15 units is requested in `wh-la`, **Then** the API rejects the transaction with `HTTP 400 Bad Request` and an explicit error message, leaving stock unchanged at 10.
2. **Given** a SKU with 100 units in `wh-la` and 0 units in `wh-zgz`, **When** an outbound order for 10 units is requested in `wh-zgz`, **Then** the request is rejected with `HTTP 400 Bad Request` because stock isolation is strictly bounded by warehouse.

---

### Edge Cases

- What happens if a non-existent `sku_id` is referenced during order creation? The request fails with `HTTP 404 Not Found`.
- What happens if an outbound order quantity is zero or negative? Pydantic request validation returns `HTTP 422 Unprocessable Entity`.
- What happens if Supabase database connection fails at startup? Startup fails with a descriptive database connection exception.
- What happens if TinyDB user UUID does not match an active user token during order creation? JWT middleware rejects the request before order processing with `HTTP 401 Unauthorized`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST configure dual database connectivity, using TinyDB for user authentication and Supabase (via SQLModel engine) for inventory entities.
- **FR-002**: Database parameters (`DATABASE_URL`, TinyDB file paths, JWT secrets) MUST be loaded from environment variables specified in `.env`, with `.env` listed in `.gitignore`.
- **FR-003**: System MUST provide a per-request SQLModel session generator `get_db` using FastAPI `Depends()` dependency injection, avoiding global session instances.
- **FR-004**: System MUST execute `SQLModel.metadata.create_all(engine)` upon application startup to automatically ensure schema existence in Supabase.
- **FR-005**: ORM models in `models.py` MUST define `SKU`, `StockEntry` (inbound), and `StockExit` (outbound) using `SQLModel` with `table=True`.
- **FR-006**: Inbound (`StockEntry`) and Outbound (`StockExit`) ORM models MUST include a foreign key to the SKU entity (`sku_id`) and store creator identity as a raw string `user_uuid` without FK constraints or table replication from TinyDB.
- **FR-007**: Pydantic schemas in `schemas.py` MUST be structurally separate from ORM models in `models.py`, ensuring API endpoints never expose raw SQLModel ORM objects directly.
- **FR-008**: Product response schemas MUST include a dynamically calculated `current_stock` field (`SUM(inbound quantities) - SUM(outbound quantities)` bounded by warehouse scope), prohibiting direct stock column modification.
- **FR-009**: All inventory endpoints MUST be grouped under an `APIRouter` with prefix `/inventory` registered in the main FastAPI application (`main.py`).
- **FR-010**: `POST /inventory/products`, `POST /inventory/orders/inbound`, and `POST /inventory/orders/outbound` endpoints MUST enforce JWT authentication, retrieving the authenticated user's TinyDB `user_uuid` from the token payload.
- **FR-011**: System MUST reject any outbound order request that would cause `current_stock` to drop below 0 within the target warehouse scope, returning `HTTP 400 Bad Request` prior to persisting the transaction.
- **FR-012**: System MUST include pre-configured seed data for TrackFlow warehouses (`wh-la` in Los Angeles and `wh-zgz` in Zaragoza) and sample SKUs, reflecting net stock upon initial query.

### Key Entities

- **SKU (Product Entity)**: Represents a catalog item managed across TrackFlow warehouses. Attributes: `id` (integer/UUID primary key), `sku` (string, unique code e.g., `SKU-1001`), `name` (string), `warehouse_id` (string, e.g., `wh-la` or `wh-zgz`), `low_stock_threshold` (integer), `created_at` (datetime).
- **StockEntry (Inbound Order)**: Represents inbound inventory additions. Attributes: `id` (primary key), `sku_id` (foreign key to SKU), `warehouse_id` (string), `quantity` (positive integer), `user_uuid` (string referencing TinyDB user), `created_at` (datetime).
- **StockExit (Outbound Order)**: Represents outbound inventory fulfillments/shipments. Attributes: `id` (primary key), `sku_id` (foreign key to SKU), `warehouse_id` (string), `quantity` (positive integer), `user_uuid` (string referencing TinyDB user), `created_at` (datetime).
- **ProductResponse (Pydantic Schema)**: Public representation of SKU metadata combined with derived `current_stock` (integer).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of product endpoints calculate `current_stock` on-the-fly from historical inbound and outbound transactions without relying on a stored stock column.
- **SC-002**: 100% of invalid outbound order attempts (quantity exceeding available warehouse stock) are rejected with `HTTP 400` in under 50ms without executing database write operations.
- **SC-003**: 100% of created order records accurately capture the authenticated TinyDB creator's `user_uuid` in Supabase transaction tables.
- **SC-004**: Automated API test suite achieves 0 TypeScript/Python build or lint errors across dual-database dependency injection patterns.

## Assumptions

- TinyDB authentication middleware (`OAuth2PasswordBearer` and JWT validation) implemented in existing services is reused to extract `user_uuid`.
- Supabase SQLModel engine relies on standard PostgreSQL driver compatibility (e.g. `psycopg2` or `asyncpg` / `sqlite` fallback for local automated test execution).
- Warehouses in TrackFlow domain (`wh-la` for Los Angeles and `wh-zgz` for Zaragoza) serve as partition boundaries for inventory calculation.
