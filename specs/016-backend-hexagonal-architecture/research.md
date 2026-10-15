# Phase 0 Research: Backend Hexagonal Architecture Transition

**Feature**: Backend Architecture - Switch to Hexagonal  
**Branch**: `016-backend-hexagonal-architecture`  
**Date**: 2026-10-13  
**Status**: Completed  

---

## Executive Overview

This document resolves all technical unknowns, dependency considerations, and integration patterns required to transition the `services/api` backend to a Hexagonal Architecture (Ports and Adapters). It provides concrete decisions with rationale and rejected alternatives for every architectural boundary.

---

## Research Topics & Architectural Decisions

### 1. Domain Entity Modeling & Framework Decoupling

#### Context & Problem
Currently, domain models and database tables are conflated:
- SQLModel table classes reside in the root `models.py` (`SKU`, `StockEntry`, `StockExit`), directly coupling database schema definitions with business models.
- TinyDB records are passed around as raw Python dictionaries or loosely coupled Pydantic schemas.
- Domain logic is scattered across route handlers (`routes/suppliers.py`, `routers/inventory.py`).

#### Decision
Define pure domain entities in `domain/<domain_name>/models.py` using **Pydantic v2** (`BaseModel`) or frozen dataclasses with **zero dependencies on FastAPI, SQLModel, SQLAlchemy, or TinyDB**.

#### Rationale
- Pydantic v2 is already a core dependency of TrackFlow.
- Pure Pydantic domain models enforce strict attribute typing, boundary validation, and immutable data rules (`model_config = ConfigDict(frozen=True)` where appropriate) without coupling to database tables.
- Separation between database persistence models (e.g. `infrastructure/persistence/sqlmodel/models.py`) and domain entities (e.g. `domain/inventory/models.py`) ensures schema migrations or storage alterations do not impact core business logic.

#### Alternatives Considered
- **Standard Python `dataclasses`**: Clean and stdlib-only, but requires manual type validation converters when receiving or returning Pydantic DTOs.
- **SQLModel models as Domain Entities**: Rejected. SQLModel conflates SQLAlchemy ORM engine columns and database session mechanics with domain entities, violating Hexagonal isolation (Principle I).

---

### 2. Dual Database Coexistence (TinyDB & SQLModel) Behind Driven Ports

#### Context & Problem
The TrackFlow backend relies on two separate storage engines:
1. **TinyDB**: JSON document store (`db.json`) used for Users, Profiles, Password Reset Tokens, Audit Logs, Suppliers, and Incidents.
2. **SQLModel / SQLite / PostgreSQL**: Relational database (`inventory.db`) used for Inventory SKUs, Inbound Stock Entries, and Outbound Stock Exits.

In the current codebase, route handlers and application services directly receive SQLModel `Session` objects or call `get_tinydb()`, preventing unit testing without disk I/O.

#### Decision
Specify abstract repository ports using Python's `abc.ABC` in `domain/<domain_name>/ports.py`. Implement concrete adapters in:
- `infrastructure/persistence/tinydb/<domain>_repository.py`
- `infrastructure/persistence/sqlmodel/<domain>_repository.py`

Each repository adapter encapsulates its own storage connection lifecycle (managing TinyDB tables or SQLModel sessions) and maps storage records to/from pure domain entities.

#### Rationale
- Completely isolates database query mechanics from application services.
- `InventoryService` no longer accepts an active `Session`; instead, it receives an abstract `InventoryRepositoryPort`.
- Enables unit testing of application use cases using in-memory mock repositories with zero file system dependencies.
- Eliminates test pollution where tests read/write to active `db.json` files.

#### Alternatives Considered
- **Generic Repository Pattern (`Repository[T]`)**: Rejected. Generic CRUD repositories fail to capture domain-specific query semantics such as `calculate_stock(sku_id, warehouse_id)`, `update_supplier_rate(id, rate)`, or `count_incident_summary()`.
- **Replacing TinyDB with PostgreSQL completely**: Rejected for this specification. The specification explicitly mandates preserving the dual database engine architecture while decoupling it through ports.

---

### 3. Dependency Injection & Composition Root in FastAPI

#### Context & Problem
In `presentation/api/auth_routes.py`, database connections and repository instances are imported dynamically inside route functions (e.g., `from infrastructure.database import get_tinydb`). In `routes/suppliers.py`, `db = get_tinydb()` is called directly inside route functions.

#### Decision
Implement centralized dependency injection provider functions in `presentation/dependencies.py` using FastAPI's built-in `Depends()` system. 

Example DI flow:
1. `get_supplier_repository() -> SupplierRepositoryPort`: Returns `TinyDBSupplierRepository(db=get_tinydb())`.
2. `get_supplier_service(repo = Depends(get_supplier_repository)) -> SupplierService`: Instantiates and returns `SupplierService(repo=repo)`.
3. Route handlers declare: `service: SupplierService = Depends(get_supplier_service)`.

#### Rationale
- Native to FastAPI; zero extra third-party libraries required.
- Eliminates dynamic in-function imports and circular dependency risks.
- Provides seamless test mocking via `app.dependency_overrides[get_supplier_repository] = lambda: MockSupplierRepository()`.

#### Alternatives Considered
- **External DI Frameworks (`dependency-injector`, `pinject`)**: Rejected. Introduces unnecessary overhead and complex container configurations when FastAPI's `Depends` already provides clean hierarchical DI and test override hooks.
- **Global Singletons**: Rejected. Prevents concurrency safety, leaks state across tests, and creates hidden dependencies.

---

### 4. Incident CSV Stream Analysis State Encapsulation

#### Context & Problem
In `main.py` (lines 170–229), two endpoints (`POST /api/incidents/analyze` and `GET /api/incidents/results/export`) are defined inline, relying on a module-level global variable: `last_analysis_result = None`.

#### Decision
1. Extract an `AnalysisService` in `application/incidents/analysis_service.py` responsible for invoking `shared.analyzer.engine.analyze_csv_stream`.
2. Abstract analysis result caching behind a driven port `AnalysisResultStorePort` (or using the shared `CachePort`).
3. Relocate both route endpoints to `presentation/api/v1/incidents.py`.
4. Implement `MemoryAnalysisResultStore` (with option for Redis in production) to store the latest analysis state.

#### Rationale
- Eliminates global mutable state from `main.py`, allowing `main.py` to function strictly as the composition root.
- Unifies all incident-related routes under the incidents domain presentation layer.
- Thread-safe and compatible with multi-worker ASGI server deployments.

#### Alternatives Considered
- **Persisting CSV Analysis Results to Database**: Rejected. The export feature is designed for temporary user downloads after an analysis run; persistent database storage would require new schema tables and lifecycle pruning.
- **Retaining routes in `main.py`**: Rejected. Violates Single Responsibility Principle and litters the composition root with presentation routing logic.

---

### 5. Route Prefix Reconciliation & 100% Backward Compatibility

#### Context & Problem
Current endpoints have divergent path conventions:
- `/suppliers` (root prefix)
- `/inventory/*` (root prefix)
- `/auth/*` (root prefix)
- `/users/*` (root prefix)
- `/profiles/*` (root prefix)
- `/telemetry/*` and `/api/v1/telemetry/*` (mixed)
- `/api/incidents/*` (`/api` prefix)

Frontends in `uis/backoffice` and `uis/website` consume these legacy routes. Any breaking path change violates TrackFlow Monorepo Constitution Principle II.

#### Decision
- Organize canonical router modules under `presentation/api/v1/<domain>.py`.
- In `main.py`, mount each router under **both** the canonical `/api/v1/<domain>` prefix and its legacy path prefix (`/suppliers`, `/inventory`, `/auth`, etc.).

#### Rationale
- 100% backward compatibility for all existing HTTP requests originating from frontend clients and automated test suites.
- Establishes a clean, consistent, versioned API structure (`/api/v1/...`) for all future endpoints.
- Zero client-side migration risk or lockstep deployments required.

#### Alternatives Considered
- **HTTP 307/308 Redirects**: Rejected. HTTP redirects can fail for POST payloads or trigger cross-origin redirect complications in browser clients.
- **Breaking path changes**: Rejected. Explicit violation of Constitution Principle II.

---

### 6. Defensive Error Handling & Domain Exception Mapping

#### Context & Problem
Route handlers currently handle exceptions inconsistently:
- Some catch generic `Exception` and return 500 with `str(e)` (violating Constitution Principle IV).
- Others raise `HTTPException` directly within business logic.

#### Decision
1. Define domain exception hierarchy in `domain/common/exceptions.py`:
   - `DomainException(Exception)`
   - `EntityNotFoundError(DomainException)`
   - `BusinessRuleViolationError(DomainException)`
   - `UnauthorizedOperationError(DomainException)`
2. Application services raise domain exceptions exclusively (no `HTTPException`).
3. Configure global FastAPI exception handlers in `core/exceptions.py` to intercept domain exceptions and map them to standard, sanitized HTTP responses:
   - `EntityNotFoundError` -> `HTTP 404 Not Found` (`{"detail": sanitized_message}`)
   - `BusinessRuleViolationError` -> `HTTP 400 Bad Request` (`{"detail": sanitized_message}`)
   - Unhandled exceptions -> Log full traceback internally; return `HTTP 500 Internal Server Error` with `{"detail": "Internal server error"}`.

#### Rationale
- Completely eliminates raw stack traces and internal exception leaking to HTTP clients (Constitution Principle IV).
- Keeps application services completely free from HTTP framework concepts (`HTTPException`).

#### Alternatives Considered
- **Catching and re-raising `HTTPException` inside every router function**: Rejected. Introduces repetitive boilerplate across all 23 endpoints.

---

## Conclusion & Gate Status

All architectural unknowns and technical decisions have been resolved. The target architecture fully complies with the TrackFlow Monorepo Constitution and preserves 100% backward compatibility. Ready to proceed to **Phase 1: Design & Contracts**.
