# Implementation Plan: Telemetry Report Endpoint & Operational Dashboard

**Branch**: `018-telemetry-report-endpoint` | **Date**: 2026-10-17 | **Spec**: [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/018-telemetry-report-endpoint/spec.md)

**Input**: Feature specification from `/specs/018-telemetry-report-endpoint/spec.md`

---

## Summary

Build an operational telemetry analysis pipeline and reporting interface for system health monitoring:
1. **Analysis Pipeline** (`services/telemetry/analysis.py`): Encapsulates side-effect-free, vectorized Pandas metric functions calculating daily event volumes (`events_per_day`), operational error distributions (`error_rate_by_type`), and authentication failure rates (`auth_failure_rate`), with mandatory UTC timezone normalization before grouping.
2. **FastAPI Report Endpoint** (`GET /telemetry/report` and `/api/v1/telemetry/report`): Resolves a UTC time window (defaulting to the past 7 days), passes explicit bounds to the analysis pipeline, and serves responses cached with a thread-safe 60-second TTL in memory.
3. **Operational Visual Dashboard** (`uis/backoffice/app/telemetry/page.tsx`): A lightweight, accessible Next.js UI rendering the operational metrics with active period display, responsive SVG/Tailwind charts/tables, and resilient error states.

---

## Technical Context

**Language/Version**: Python 3.14 (Backend), TypeScript 5.9+ / Node.js 20+ (Frontend)

**Primary Dependencies**: 
- Backend: `fastapi>=0.141.1`, `sqlmodel>=0.0.22`, `pandas>=2.2.0`, `pydantic>=2.13.5`, `uvicorn>=0.52.4`
- Frontend: `next@14.2.5`, `react@18.3.1`, `tailwindcss@4.0.0`

**Storage**: SQLite (`inventory.db`) with fallback to PostgreSQL via SQLModel persistence adapter; table `telemetry_events`.

**Testing**: 
- Backend: `pytest>=9.1.1` (unit and API integration tests in `services/api/tests`)
- Frontend: `jest`, `ts-jest`, `tsc --noEmit`

**Target Platform**: Linux / Windows containerized service and Node.js web runtime.

**Project Type**: Monorepo with web service API (`services/api`), Python telemetry analysis module (`services/telemetry`), and Next.js frontend (`uis/backoffice`).

**Performance Goals**: 
- Report endpoint response latency: < 500ms on cache miss, < 50ms on cache hit.
- In-memory cache hit ratio: 100% of identical queries within 60-second TTL.
- Dashboard initial page paint: LCP ≤ 1.0s, TBT ≤ 200ms.

**Constraints**:
- Strict UTC normalization prior to any temporal grouping.
- Vectorized Pandas calculations only (no procedural `for`/`while` loops).
- Zero business-domain metrics (sales, conversion rates, revenue).
- Strict TypeScript & zero implicit `any` in frontend code.

**Scale/Scope**: Telemetry reporting over standard operational windows (1 to 30 days, default 7 days), processing up to 100,000 raw events per query window.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked post Phase 1 design.*

| Principle | Requirement | Status | Verification / Design Notes |
| :--- | :--- | :--- | :--- |
| **I. Service Boundaries & Domain Isolation** | Monorepo architectural boundaries strictly preserved; frontends in `uis/` must not access DB or backend modules directly; APIs communicate via HTTP REST. | **PASS** | Dashboard in `uis/backoffice` communicates exclusively via HTTP fetch to `/telemetry/report`. Shared DTO types are published in `packages/shared/types/telemetry.ts`. |
| **II. Public API Compatibility & Strict Contract Serialization** | 100% of FastAPI endpoints declare Pydantic `response_model`, typed query parameters, status codes; no internal ORM leakage. | **PASS** | `GET /telemetry/report` and `/api/v1/telemetry/report` declare explicit Pydantic `response_model=TelemetryReportResponse`, projection DTOs, and typed parameters. |
| **III. Strict TypeScript & Static Type Safety** | Compiler flags adherence (`strict: true`, `noUncheckedIndexedAccess`), zero `any`, explicit return types, explicit type imports. | **PASS** | `uis/backoffice` code and shared contracts use explicit types, JSDoc annotations, `import type`, and zero `any`. |
| **IV. Defensive Error Handling & Zero Sensitive Data Leaks** | No raw tracebacks in HTTP 500; no PII leaks; resilient UI error states with retry mechanisms. | **PASS** | Endpoints catch calculation errors and return sanitized `ErrorResponse`. UI implements error boundaries and retry actions. |
| **V. Performance-First Architecture** | CWV standards (LCP ≤ 1.0s, TBT ≤ 200ms); in-memory caching to eliminate redundant database compute. | **PASS** | Thread-safe 60s TTL in-memory cache on backend. Pure SVG/Tailwind chart rendering without heavy JavaScript chart library overhead. |
| **VI. Test-First Development & Deterministic Verification** | Automated unit and integration tests passing static analysis gates (`pytest`, `tsc --noEmit`, `jest`). | **PASS** | Dedicated tests for `services/telemetry/analysis.py`, cache TTL behavior, FastAPI routes, and Next.js page components. |

---

## Project Structure

### Documentation (this feature)

```text
specs/018-telemetry-report-endpoint/
├── plan.md              # Implementation plan (this document)
├── research.md          # Phase 0 decisions & technical context
├── data-model.md        # Phase 1 data models & validation rules
├── quickstart.md        # Phase 1 end-to-end validation scenarios
├── contracts/           # Phase 1 interface contracts
│   ├── telemetry-report-api.yaml  # OpenAPI 3.1 specification
│   └── shared-types.ts            # TypeScript shared definitions
└── tasks.md             # Phase 2 output (/speckit-tasks command)
```

### Source Code (repository layout)

```text
packages/
└── shared/
    └── types/
        ├── index.ts                   # Export telemetry types
        └── telemetry.ts               # Shared TypeScript DTO contracts

services/
├── telemetry/
│   ├── __init__.py                    # Telemetry service package
│   └── analysis.py                    # Vectorized Pandas operational analysis pipeline
└── api/
    ├── application/
    │   └── telemetry/
    │       ├── cache.py               # Thread-safe in-memory report cache (60s TTL)
    │       └── report_service.py      # Telemetry report orchestration service
    ├── domain/
    │   └── telemetry/
    │       └── report_models.py       # Pydantic domain models for telemetry reporting
    ├── presentation/
    │   └── api/
    │       └── v1/
    │           └── telemetry.py       # GET /telemetry/report & /api/v1/telemetry/report
    └── tests/
        ├── api/
        │   └── test_telemetry_report.py   # Endpoint & caching integration tests
        └── unit/
            └── test_telemetry_analysis.py # Pandas pipeline unit tests

uis/
└── backoffice/
    ├── app/
    │   └── telemetry/
    │       └── page.tsx               # Operational Telemetry Dashboard page
    ├── components/
    │   ├── Header.tsx                 # Updated navigation link to /telemetry
    │   └── telemetry/
    │       ├── EventVolumeChart.tsx   # SVG/Tailwind daily event volume chart
    │       ├── ErrorDistribution.tsx  # Error categories breakdown table & bars
    │       └── AuthFailureCard.tsx    # Authentication reliability metric card
    └── __tests__/
        └── telemetry.test.tsx         # Dashboard frontend unit tests
```

**Structure Decision**: 
- Backend modularity: `services/telemetry/analysis.py` encapsulates pure analytical data transformation using Pandas without framework coupling.
- Integration: `services/api/` handles HTTP presentation, query param validation, caching, and database session lifecycle.
- Frontend: `uis/backoffice` hosts the engineering dashboard utilizing the monorepo design system.

---

## Complexity Tracking

*No constitution violations. All architecture adheres strictly to TrackFlow Monorepo Constitution.*
