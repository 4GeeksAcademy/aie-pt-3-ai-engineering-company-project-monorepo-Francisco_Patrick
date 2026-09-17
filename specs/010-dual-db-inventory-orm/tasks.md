# Tasks: Dual Database Architecture + Inventory ORM

**Input**: Design documents from `/specs/010-dual-db-inventory-orm/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Backend Service: `services/api/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project configuration, environment setup, and git safety verification.

- [x] T001 Configure `DATABASE_URL` and TinyDB database parameters in `services/api/.env.example` and `services/api/.env`
- [x] T002 Verify `.env` is listed in `services/api/.gitignore` and repository root `.gitignore`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Initialize dual database connections (TinyDB client + SQLModel engine using `psycopg2-binary`) in `services/api/infrastructure/database.py`
- [x] T004 Implement request-scoped `get_db` generator yielding SQLModel `Session(engine)` via `Depends()` in `services/api/infrastructure/database.py`
- [x] T005 Configure application startup hook in `services/api/main.py` to execute `SQLModel.metadata.create_all(engine)`

**Checkpoint**: Foundation ready — dual database setup and per-request session dependency ready for user story implementation.

---

## Phase 3: User Story 1 - Multi-Database Initialization & Product Management (Priority: P1) 🎯 MVP

**Goal**: Establish SKU ORM model and Pydantic schemas, implement product creation and product listing endpoints with initial derived stock equal to 0.

**Independent Test**: Create a SKU via `POST /inventory/products` with valid JWT token, verify it persists in Supabase, and confirm `GET /inventory/products/{id}` returns initial `current_stock` equal to 0.

### Implementation for User Story 1

- [x] T006 [P] [US1] Create `SKU` ORM model (`table=True`) in `services/api/models.py`
- [x] T007 [P] [US1] Create `ProductCreate` and `ProductResponse` Pydantic schemas (with `current_stock`) in `services/api/schemas.py`
- [x] T008 [US1] Implement `POST /inventory/products` (authenticated) and `GET /inventory/products` / `GET /inventory/products/{id}` endpoints in `services/api/routers/inventory.py`
- [x] T009 [US1] Register `/inventory` router in FastAPI application in `services/api/main.py`
- [x] T010 [US1] Add unit and integration tests for product creation and retrieval in `services/api/tests/test_inventory_products.py`

**Checkpoint**: User Story 1 (MVP) fully functional and testable independently.

---

## Phase 4: User Story 2 - Inbound & Outbound Stock Adjustments via Orders (Priority: P2)

**Goal**: Implement Inbound (`StockEntry`) and Outbound (`StockExit`) models, dynamic stock calculation from transaction history, and order endpoints storing creator `user_uuid`.

**Independent Test**: Register an inbound order (`POST /inventory/orders/inbound`), verify stock increases on `GET /inventory/products/{id}`, then register a valid outbound order (`POST /inventory/orders/outbound`) and verify stock decreases accordingly.

### Implementation for User Story 2

- [x] T011 [P] [US2] Create `StockEntry` and `StockExit` ORM models (`table=True`, storing `user_uuid`) in `services/api/models.py`
- [x] T012 [P] [US2] Create `InboundOrderCreate`, `OutboundOrderCreate`, and `OrderResponse` Pydantic schemas in `services/api/schemas.py`
- [x] T013 [US2] Implement dynamic stock calculation logic (`SUM(inbound) - SUM(outbound)`) in `services/api/application/services/inventory_service.py`
- [x] T014 [US2] Implement `POST /inventory/orders/inbound` endpoint storing TinyDB creator `user_uuid` in `services/api/routers/inventory.py`
- [x] T015 [US2] Implement `POST /inventory/orders/outbound` endpoint storing TinyDB creator `user_uuid` in `services/api/routers/inventory.py`
- [x] T016 [US2] Implement `GET /inventory/orders` endpoint listing all orders in `services/api/routers/inventory.py`
- [x] T017 [US2] Add integration tests for order execution and dynamic stock derivation in `services/api/tests/test_inventory_orders.py`


**Checkpoint**: User Stories 1 AND 2 both functional independently.

---

## Phase 5: User Story 3 - Stock Boundary Protection & Multi-Warehouse Isolation (Priority: P3)

**Goal**: Enforce warehouse scoping (`wh-la` / `wh-zgz`) and reject outbound orders exceeding available stock with HTTP 400.

**Independent Test**: Submit an outbound order exceeding available warehouse stock and verify immediate `HTTP 400 Bad Request` response without database mutation.

### Implementation for User Story 3

- [x] T018 [US3] Implement pre-write stock validation guard in `services/api/application/services/inventory_service.py` checking requested quantity against computed stock per `warehouse_id`
- [x] T019 [US3] Update `POST /inventory/orders/outbound` in `services/api/routers/inventory.py` to return `HTTP 400 Bad Request` on stock deficit
- [x] T020 [US3] Add integration tests for negative stock rejection and multi-warehouse stock isolation in `services/api/tests/test_inventory_stock_guard.py`


**Checkpoint**: All user stories functional and protected by stock boundary guards.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Seed data initialization and end-to-end validation.

- [x] T021 [P] Populate seed data for TrackFlow warehouses (`wh-la`, `wh-zgz`) and initial stock entries in `services/api/seed.py`
- [x] T022 Execute full test suite via `uv run pytest` from `services/api/` and validate scenarios in `specs/010-dual-db-inventory-orm/quickstart.md`


---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Stories (Phase 3+)**: Depend on Foundational completion.
  - US1 (P1) → US2 (P2) → US3 (P3) in priority order.
- **Polish (Phase 6)**: Depends on all user stories completing.

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational phase (Phase 2).
- **User Story 2 (P2)**: Depends on US1 models (`SKU`) being defined.
- **User Story 3 (P3)**: Depends on US2 order posting and stock calculation logic.

### Parallel Opportunities

- T006 (`SKU` ORM) and T007 (`Product` Pydantic schemas) can run in parallel.
- T011 (`StockEntry`/`StockExit` ORM) and T012 (`Order` Pydantic schemas) can run in parallel.
- T021 (seed data) can run in parallel with polish tasks once routers are ready.
