# Implementation Plan: Backend Hexagonal Architecture Transition

**Branch**: `016-backend-hexagonal-architecture` | **Date**: 2026-10-13 | **Spec**: [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/016-backend-hexagonal-architecture/spec.md)

**Input**: Feature specification from `specs/016-backend-hexagonal-architecture/spec.md`

---

## Summary

Transition the `services/api` FastAPI backend service to a strict **Hexagonal Architecture (Ports and Adapters)**. This entails:
1. Auditing and documenting the baseline architecture, 23 active endpoints, and existing anti-patterns in `docs/backend-state-analysis.md`.
2. Isolating the core domain with pure Pydantic v2 entities and abstract Driven Ports (`SupplierRepositoryPort`, `InventoryRepositoryPort`, `IncidentRepositoryPort`, `UserRepositoryPort`, `SecurityPort`, `CachePort`).
3. Decoupling the dual persistence engines (TinyDB JSON store and SQLModel SQLite/PostgreSQL relational database) into dedicated driven repository adapters.
4. Refactoring application services to receive ports via constructor dependency injection, enabling pure unit testing with mock repositories.
5. Consolidating scattered controllers into canonical `presentation/api/v1/` routers with dependency injection providers in `presentation/dependencies.py`.
6. Preserving 100% backward compatibility for all legacy route paths and schemas consumed by frontends (`uis/backoffice`, `uis/website`).

---

## Technical Context

**Language/Version**: Python `>= 3.14` (`.python-version: 3.14`)

**Primary Dependencies**: 
- `fastapi >= 0.141.1`
- `pydantic >= 2.13.5`
- `sqlmodel >= 0.0.22`
- `tinydb >= 4.9.0`
- `uvicorn >= 0.52.4`
- `python-jose[cryptography]`
- `libpass[bcrypt]`
- `httpx >= 0.28.1`

**Storage**: 
- Coexistence of **TinyDB** (`db.json` NoSQL document store) for Users, Profiles, Suppliers, and Incidents.
- **SQLModel / SQLite** (`inventory.db`) or PostgreSQL for relational inventory tracking (SKUs, StockEntries, StockExits).

**Testing**: 
- `pytest >= 9.1.1`
- `pytest-cov >= 6.0.0`
- `httpx` (TestClient)

**Target Platform**: Linux container (Docker) / Windows local development

**Project Type**: REST Web Service (FastAPI backend in monorepo)

**Performance Goals**: 
- `< 50ms` internal p95 response time for cached endpoints (`incident_summary`, `suppliers`, `inventory_products`).
- Streaming CSV analysis execution maintaining $O(1)$ memory overhead via generator chunking.

**Constraints**: 
- **Zero Breaking Changes**: 100% backward compatibility for all 23 active API endpoints, request contracts, and response schemas.
- **TrackFlow Constitution Adherence**: Strict compliance with Principles I (Service Boundaries), II (Public API Compatibility), IV (Defensive Error Handling), and VI (Test-First Verification Gates).
- **Dual Database Engine Retention**: Both TinyDB and SQLModel must remain supported via clean repository adapters.

**Scale/Scope**: 
- 23 active endpoints across 8 functional domains (Suppliers, Inventory, Telemetry, Auth, Users, Profiles, Incidents, CSV Stream Analysis).
- ~30 Python modules across `services/api/`.

---

## Constitution Check

*GATE: Passed before Phase 0 research. Re-evaluated and confirmed post-Phase 1 design.*

| Principle | Requirement | Assessment | Mitigation / Verification |
| :--- | :--- | :--- | :--- |
| **I. Service Boundaries & Domain Isolation** | Backend must maintain clean hexagonal boundaries (`domain/`, `application/`, `infrastructure/`, `presentation/`). Domain core must have 0 imports of frameworks or DBs. Direct database access from controllers prohibited. | **PASS** | Domain layer contains pure Pydantic models and abstract ports. Driven adapters encapsulate all TinyDB and SQLModel calls. `domain/` contains zero external framework imports. |
| **II. Public API Compatibility & Strict Contract Serialization** | 100% of FastAPI endpoints must declare explicit Pydantic `response_model`. Internal models must never leak. Zero breaking changes to existing route paths or schemas. | **PASS** | All 23 endpoints retain exact response models (`SupplierResponse`, `ProductResponse`, `UserResponse`, etc.). Dual mounting in `main.py` preserves legacy paths (`/suppliers`, `/inventory/*`, `/auth/*`, `/api/incidents/*`) alongside canonical `/api/v1/*`. |
| **III. Strict TypeScript & Static Type Safety** | Python backend modules must maintain corresponding type hygiene using type annotations and Pydantic validation across all domain boundaries. | **PASS** | 100% explicit type hints on all domain models, port methods, application services, and route handlers. Zero untyped `Any` payloads. |
| **IV. Defensive Error Handling & Zero Sensitive Data Leaks** | Zero raw stack traces or internal errors (`str(e)`) exposed to clients. Zero PII/credential leaks. Domain exceptions mapped to sanitized HTTP errors. | **PASS** | Domain exceptions (`EntityNotFoundError`, `BusinessRuleViolationError`) mapped via global handlers in `core/exceptions.py`. Sensitive fields excluded from DTO projections. |
| **V. Performance-First Architecture** | Ensure cached endpoints meet latency requirements. Bounded memory consumption for stream processing. | **PASS** | CachePort provides 30s-60s TTL caching for summary and catalog queries. CSV analyzer operates via stream generators. |
| **VI. Test-First Development & Deterministic Verification Gates** | Automated test verification at every phase. Idempotent test suites. Unit tests isolated from disk databases. | **PASS** | Unit tests leverage mock repository ports, eliminating disk pollution of `db.json` and `inventory.db`. Verification gates mandate full pytest pass at each milestone. |

---

## Project Structure

### Documentation (this feature)

```text
specs/016-backend-hexagonal-architecture/
├── plan.md              # Implementation Plan (/speckit-plan output)
├── research.md          # Phase 0 Architectural Decisions & Best Practices
├── data-model.md        # Phase 1 Domain Entities, Invariants & Mappings
├── contracts/           # Phase 1 Interface Contracts
│   ├── suppliers-contract.md
│   ├── inventory-contract.md
│   ├── auth-users-contract.md
│   ├── incidents-contract.md
│   └── ports-contracts.md
├── quickstart.md        # Phase 1 Runnable Validation Guide
├── checklists/
│   └── requirements.md  # Quality Checklist
└── tasks.md             # Phase 2 Implementation Tasks (/speckit-tasks output)
```

### Source Code (`services/api/` target layout)

```text
services/api/
├── main.py                              # Composition Root & FastAPI App
├── core/                                # Cross-cutting configuration & handlers
│   ├── config.py                        # Pydantic BaseSettings
│   ├── security.py                      # Cryptographic settings & JWT constants
│   └── exceptions.py                    # Global exception handlers (Domain -> HTTP)
│
├── domain/                              # Pure Business Core (Zero framework/DB deps)
│   ├── common/
│   │   ├── exceptions.py                # Base DomainException, EntityNotFoundError, etc.
│   │   └── ports.py                     # CachePort, NotificationPort
│   ├── suppliers/
│   │   ├── models.py                    # Supplier domain entity
│   │   └── ports.py                     # SupplierRepositoryPort
│   ├── inventory/
│   │   ├── models.py                    # SKU, StockEntry, StockExit, InventoryProduct
│   │   └── ports.py                     # InventoryRepositoryPort
│   ├── incidents/
│   │   ├── models.py                    # Incident entity, enums & lifecycle transitions
│   │   └── ports.py                     # IncidentRepositoryPort, AnalysisResultStorePort
│   ├── auth/
│   │   ├── models.py                    # User, Profile, Token, AuditLog entities
│   │   └── ports.py                     # UserRepositoryPort, ProfileRepositoryPort, SecurityPort
│   └── telemetry/
│       ├── models.py                    # TelemetryEvent value object
│       └── ports.py                     # TelemetrySinkPort
│
├── application/                         # Use Cases & Application Orchestration
│   ├── suppliers/
│   │   ├── supplier_service.py          # SupplierService (injected SupplierRepositoryPort)
│   │   └── dto.py                       # SupplierCreateDTO, SupplierUpdateDTO
│   ├── inventory/
│   │   ├── inventory_service.py         # InventoryService (injected InventoryRepositoryPort)
│   │   └── dto.py                       # ProductDTO, OrderDTO
│   ├── incidents/
│   │   ├── incident_service.py          # IncidentService (injected IncidentRepositoryPort)
│   │   ├── analysis_service.py          # AnalysisService (CSV stream analysis use case)
│   │   └── dto.py
│   ├── auth/
│   │   ├── auth_service.py              # AuthService (injected User/Token/Security ports)
│   │   ├── user_service.py              # UserService (user administration)
│   │   ├── profile_service.py           # ProfileService (profile mutations)
│   │   └── dto.py
│   └── telemetry/
│       ├── telemetry_service.py         # TelemetryService
│       └── dto.py
│
├── infrastructure/                      # Driven Adapters (External Systems)
│   ├── persistence/
│   │   ├── tinydb/
│   │   │   ├── client.py                # TinyDB connection & table providers
│   │   │   ├── user_repository.py       # Implements UserRepositoryPort
│   │   │   ├── profile_repository.py    # Implements ProfileRepositoryPort
│   │   │   ├── supplier_repository.py   # Implements SupplierRepositoryPort
│   │   │   └── incident_repository.py   # Implements IncidentRepositoryPort
│   │   └── sqlmodel/
│   │       ├── client.py                # Engine & session provider
│   │       ├── models.py                # SQLModel ORM table declarations (SKU, StockEntry)
│   │       └── inventory_repository.py  # Implements InventoryRepositoryPort
│   ├── security/
│   │   ├── jwt_security_adapter.py      # Implements SecurityPort
│   │   └── rate_limiter.py              # In-memory rate limiting
│   ├── cache/
│   │   └── memory_cache_adapter.py      # Implements CachePort
│   └── notifications/
│       └── email_adapter.py             # Implements NotificationPort
│
└── presentation/                        # Driving Adapters (HTTP Delivery)
    ├── dependencies.py                  # FastAPI dependency injection wiring
    └── api/
        └── v1/                          # Canonical API v1 Routers
            ├── suppliers.py             # Suppliers endpoints
            ├── inventory.py             # Products and orders endpoints
            ├── incidents.py             # Incident CRUD & CSV stream analysis
            ├── auth.py                  # Login, forgot/reset/change password
            ├── users.py                 # User administration
            ├── profiles.py              # User profiles
            └── telemetry.py             # Telemetry ingestion
```

**Structure Decision**: Selected domain-partitioned layered structure matching Hexagonal Architecture principles. Business logic lives strictly within `domain/` and `application/`, completely decoupled from external technology choices located in `infrastructure/` (driven adapters) and `presentation/` (driving adapters).

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| :--- | :--- | :--- |
| **Dual Storage Engines (TinyDB + SQLModel)** | The application currently maintains document-oriented collections (Users, Incidents, Suppliers) in TinyDB and relational inventory tables (SKUs, stock logs) in SQLite/SQLModel. | Migrating all domains to a single engine (e.g. SQLite/PostgreSQL) introduces database migration risk, schema rewrites, and data export dependencies out of scope for pure architectural decoupling. Defining domain repository ports decouples both cleanly. |
| **Dual Route Mounting in `main.py`** | Existing frontend applications (`uis/backoffice`, `uis/website`) actively query unversioned paths (`/suppliers`, `/inventory/*`, `/auth/*`, `/api/incidents/*`). | Forcing instant migration to `/api/v1/*` in frontend clients would require synchronized multi-project deployment locks, violating TrackFlow Constitution Principle II. |
| **Repository Port Abstractions for All Domains** | Eliminates direct database query execution and session passing across controller and service layers. | Direct database access in controllers (current state) prevents unit testing without disk I/O and creates tight coupling between transport handlers and database tables. |
