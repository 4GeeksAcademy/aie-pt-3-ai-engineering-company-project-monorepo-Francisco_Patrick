# Implementation Plan: Dual Database Architecture + Inventory ORM

**Branch**: `010-dual-db-inventory-orm` | **Date**: 2026-09-17 | **Spec**: [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/010-dual-db-inventory-orm/spec.md)

**Input**: Feature specification from `/specs/010-dual-db-inventory-orm/spec.md`

## Summary

Implement a dual-database architecture in `services/api` connecting simultaneously to TinyDB (for user authentication and profiles) and Supabase PostgreSQL via SQLModel ORM (for inventory entities and orders). Stock is dynamically derived as `SUM(inbound) - SUM(outbound)` per warehouse scope (`wh-la` or `wh-zgz`), with outbound stock validation rejecting transactions that would cause negative stock (`HTTP 400`). Order records capture the creator's TinyDB `user_uuid` as a reference string without foreign key replication.

## Technical Context

**Language/Version**: Python 3.11+ (FastAPI backend in `services/api/`)

**Primary Dependencies**: FastAPI, SQLModel, Pydantic, TinyDB, `psycopg2-binary`, `python-jose`, `passlib`

**Storage**: Dual Database — TinyDB (`services/api/db.json`) for Auth & User profiles; Supabase (PostgreSQL via SQLModel engine) for Inventory (`SKU`, `StockEntry`, `StockExit`)

**Testing**: `pytest` and `httpx` / `fastapi.testclient.TestClient` (`uv run pytest`)

**Target Platform**: Linux/Windows web service container / server (`services/api/`)

**Project Type**: Monorepo Web Application Service (Hexagonal Architecture)

**Performance Goals**: < 50ms for stock calculation and order posting

**Constraints**: Dual database parameters strictly in `.env`; request-scoped SQLModel session generator (`get_db`) via `Depends()`; Pydantic schemas in `schemas.py` structurally separate from ORM models in `models.py`.

**Scale/Scope**: TrackFlow warehouses (`wh-la` in Los Angeles, `wh-zgz` in Zaragoza), SKU catalog items, and inbound/outbound order transactions.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Principle I: Hexagonal Architecture (Ports & Adapters)**: PASS — Core logic separated into `domain/`, `application/`, `infrastructure/`, and `presentation/`.
- **Principle II: FastAPI & Pydantic Type Contracts**: PASS — API schemas (`schemas.py`) distinct from SQLModel models (`models.py`).
- **Principle III: Dual-Database Persistence**: PASS — TinyDB retained for Auth; SQLModel + `psycopg2-binary` engine initialized for Supabase; `get_db` session generator injected per request.
- **Principle IV: Next.js Frontend Framework**: N/A — Backend API feature.
- **Principle V: Strict Type & Boundary Integrity**: PASS — Python type annotations strictly defined; zero direct ORM model leaks.

## Project Structure

### Documentation (this feature)

```text
specs/010-dual-db-inventory-orm/
├── plan.md              # Implementation plan
├── research.md          # Phase 0 research & technical decisions
├── data-model.md        # Phase 1 ORM & Pydantic schema specifications
├── quickstart.md        # Phase 1 verification guide
└── contracts/           # OpenAPI contract specifications
    └── inventory-api.json
```

### Source Code (repository root)

```text
services/api/
├── main.py                          # Application entry point & router registration
├── infrastructure/
│   └── database.py                  # Dual DB initialization (TinyDB + SQLModel engine & get_db)
├── models.py                        # SQLModel ORM models (SKU, StockEntry, StockExit)
├── schemas.py                       # Pydantic API schemas (ProductResponse with current_stock)
├── routers/
│   └── inventory.py                 # Inventory APIRouter (/inventory endpoints)
├── application/
│   └── services/
│       └── inventory_service.py     # Domain logic for derived stock & order validation
└── tests/
    └── test_inventory.py            # Unit & integration tests for dual DB and inventory endpoints
```

**Structure Decision**: Monorepo Web Service structure utilizing `services/api/` following Hexagonal Architecture layer boundaries.

## Complexity Tracking

*No constitution violations present.*
