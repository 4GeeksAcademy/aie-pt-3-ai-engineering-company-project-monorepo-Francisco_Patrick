# Implementation Plan: Implementing a Resilient Business Performance Pipeline

**Branch**: `020-resilient-business-pipeline` | **Date**: 2026-10-20 | **Spec**: [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/020-resilient-business-pipeline/spec.md)

**Input**: Feature specification from `/specs/020-resilient-business-pipeline/spec.md`

---

## Summary

Implement a resilient, command-line runnable production data pipeline using Prefect 3.x that extracts operational telemetry events and domain records, calculates five executive KPIs (Shipments Volume, Global On-Time Delivery Rate, Operational Cost in EUR, Returns Rate, and Customer Satisfaction Score) using vectorized Pandas transformations, idempotently persists pre-computed snapshots into `reporting.executive_kpi_snapshots`, and records audit metadata in `reporting.pipeline_execution_logs`. Decoupled FastAPI endpoints under `services/reporting/` expose run health, ad-hoc execution triggers, and KPI query interfaces conforming to the briefing contract while leaving existing engineering telemetry (`services/telemetry/analysis.py` and `telemetry_events`) completely untouched.

---

## Technical Context

**Language/Version**: Python >= 3.11 (Python 3.14 via `services/api/.venv`)  
**Primary Dependencies**: Prefect 3.8.8, pandas >= 3.0.6, FastAPI >= 0.141.1, Pydantic >= 2.13.5, SQLModel >= 0.0.22, SQLAlchemy >= 2.0.0  
**Storage**: SQLite (`services/api/inventory.db`) with PostgreSQL / Supabase compatibility for `reporting` schema tables  
**Testing**: pytest (`pytest-cov`, `httpx` for TestClient)  
**Target Platform**: Windows / Linux server / Docker container  
**Project Type**: Data pipeline CLI script + REST API microservice presentation module  
**Performance Goals**: Pipeline batch execution < 5 minutes SLA; sub-100ms p95 latency for pre-computed `GET /api/v1/reporting/kpis` queries  
**Constraints**: Zero `any` in TypeScript DTOs, zero modifications to `services/telemetry/analysis.py`, atomic transaction rollback on failure, composite unique constraint `(period_start, period_end, country)` for idempotency  
**Scale/Scope**: 5 core KPIs across 3 geographic slices (US, ES, GLOBAL); 7-day rolling batch with 7-day lookback window  

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Requirement | Plan Alignment | Status |
| :--- | :--- | :--- | :---: |
| **I. Service Boundaries & Domain Isolation** | Monorepo architectural boundaries preserved. No inline ETL in routes. Frontends consume via HTTP. | `data/pipelines/` encapsulates ETL and calculation logic. `services/reporting/` is a pure presentation layer importing boundary functions from `data.pipelines.reporting_interface`. Existing `services/telemetry/` is untouched. | PASS |
| **II. Public API Compatibility & Strict Serialization** | Endpoints declare explicit Pydantic response models and typed parameters. No raw ORM leakage. | All endpoints in `services/reporting/` declare Pydantic DTOs matching `reporting-api.yaml`. Projections strictly prevent ORM model leaks. | PASS |
| **III. Strict TypeScript & Static Type Safety** | Shared types satisfy zero `any`, strict compiler flags, explicit `import type`, JSDoc comments. | Any frontend DTO interfaces added to packages adhere strictly to zero `any` and static typing standards. | PASS |
| **IV. Defensive Error Handling & Zero Sensitive Data Leaks** | Zero raw exception exposure in HTTP 500. Zero PII/credentials logged. No swallowed errors. | Database transactions wrapped in atomic blocks with rollback on error. Audit logs sanitize error details. Exception handlers return user-safe messages. | PASS |
| **V. Performance-First Architecture** | High performance, sub-100ms p95 queries. Pre-computed snapshots. Vectorized transformations. | Vectorized Pandas operations (no iterrows). Pre-computed snapshots stored in indexed tables queried in sub-100ms. | PASS |
| **VI. Test-First Development & Deterministic Gates** | Unit and integration test suites. Deterministic seeding. Automated verification gates. | Automated tests for pipeline flow, retries, caching, idempotency, non-critical task failure tolerance, and API route responses. | PASS |

---

## Project Structure

### Documentation (this feature)

```text
specs/020-resilient-business-pipeline/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── reporting-api.yaml
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```text
data/pipelines/
├── pipeline.py                 # Core Prefect flow, tasks, retries, caching, CLI runner
├── reporting_interface.py     # Pure boundary functions consumed by presentation routes
├── models.py                  # SQLModel / SQLAlchemy definitions for reporting schema
└── PIPELINE_DESIGN.md         # Approved architectural design document (updated with run commands)

services/reporting/
├── __init__.py
├── domain/
│   ├── __init__.py
│   └── schemas.py             # Pydantic DTO models matching reporting-api.yaml
└── presentation/
    ├── __init__.py
    └── routes.py              # FastAPI router (/status, /trigger, /kpis) mounted in main.py

services/api/
└── main.py                    # Mounts /api/v1/reporting router into API application

tests/
├── pipelines/
│   ├── test_pipeline_etl.py           # Tests extraction, transformation, and load
│   └── test_pipeline_resilience.py    # Tests retries, caching, idempotency, partial failure
└── reporting/
    └── test_reporting_endpoints.py    # Tests /status, /trigger, /kpis API responses
```

**Structure Decision**:
Follows the hexagonal/layered boundaries defined in TrackFlow Constitution Principle I. Pipeline compute and persistence logic live in `data/pipelines/`, while presentation controllers and Pydantic schemas live in `services/reporting/`. The reporting router is cleanly mounted into the primary FastAPI application at `services/api/main.py`.

---

## Complexity Tracking

*No constitutional violations identified. Standard architectural boundaries and patterns applied.*

| Component | Why Needed | Alternative Rejected |
| :--- | :--- | :--- |
| `data/pipelines/reporting_interface.py` | Provides a clean, decoupled boundary adapter for HTTP routes | Inline database/ETL queries inside route handlers was rejected (violates Monorepo Constitution Principle I) |
| Prefect `@flow` and `@task` | Provides declarative state handling, automatic task retries, and result caching | Ad-hoc Python scripts with custom retry loops rejected (lacks standardized state inspection, lineage, and observability) |
