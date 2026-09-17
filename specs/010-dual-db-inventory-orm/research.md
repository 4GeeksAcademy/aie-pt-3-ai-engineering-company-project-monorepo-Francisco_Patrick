# Phase 0 Research: Dual Database Architecture + Inventory ORM

## Research Topics & Key Decisions

### 1. Dual-Database Initialization (TinyDB + Supabase SQLModel)
- **Decision**: Initialize both persistence engines in `services/api/infrastructure/database.py`. TinyDB remains configured for user/profile/incident repositories (`db.json`), while SQLModel engine connects to Supabase via standard PostgreSQL `DATABASE_URL` (using `psycopg2-binary`).
- **Rationale**: Meets project constitution and user prompt requirements. TinyDB retains existing authentication data, while relational inventory tables (`sku`, `stock_entry`, `stock_exit`) live in Supabase.
- **Alternatives Considered**: Using raw SQLAlchemy without SQLModel (rejected: SQLModel integrates seamlessly with FastAPI/Pydantic typing).

### 2. Dependency Injection for Database Sessions (`get_db`)
- **Decision**: Implement a `get_db()` generator yielding a `Session(engine)` per request via FastAPI `Depends()`, with automatic context cleanup (`try ... finally: session.close()`).
- **Rationale**: Prevents global session leaks, thread safety issues, and connection pooling bottlenecks.
- **Alternatives Considered**: Global session variable (rejected: explicitly forbidden by prompt and constitution).

### 3. Derived Stock Calculation & Negative Stock Enforcement
- **Decision**: `current_stock` for a SKU is calculated dynamically per warehouse scope (`warehouse_id`) as `COALESCE(SUM(inbound_qty), 0) - COALESCE(SUM(outbound_qty), 0)`.
- **Rationale**: Direct stock columns are forbidden. Calculating stock from order transaction history guarantees a single source of truth and prevents state drift.
- **Outbound Guard**: Before writing a `StockExit` record, the service computes `current_stock` for the target `sku_id` and `warehouse_id`. If `requested_qty > current_stock`, the API aborts with `HTTP 400 Bad Request` prior to executing any DB inserts.

### 4. TinyDB User UUID Reference Pattern
- **Decision**: Inbound (`StockEntry`) and Outbound (`StockExit`) SQLModel tables store a `user_uuid` string field extracted from the caller's JWT token payload (`sub` claim). No foreign key constraint or table replication for users exists in Supabase.
- **Rationale**: Keeps Supabase decoupled from TinyDB user storage while preserving full audit traceability of order creators.
