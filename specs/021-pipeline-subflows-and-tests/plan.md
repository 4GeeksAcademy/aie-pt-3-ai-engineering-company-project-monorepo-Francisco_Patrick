# Implementation Plan: Pipeline Enhancement: Subflows and Tests

**Branch**: `feature/021-pipeline-subflows-and-tests` | **Date**: 2026-10-27 | **Spec**: [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/021-pipeline-subflows-and-tests/spec.md)

**Input**: Feature specification from `/specs/021-pipeline-subflows-and-tests/spec.md`

---

## Summary

Bring the existing TrackFlow business performance telemetry pipeline to production-ready status by:
1. Decomposing the monolithic pipeline in `data/pipelines/pipeline.py` into modular, domain-named Prefect 3.x subflows (`@flow`) for extraction, transformation, load, and auxiliary notification, communicating strictly through explicit arguments and return values with zero mutable global state.
2. Establishing a dedicated transformation unit test suite in `tests/pipelines/test_pipeline.py` executing 100% in memory with zero database or network dependencies, testing zero-division guardrails, defensive handling of malformed payloads, and exact mathematical precision against briefing formulas.
3. Preserving standalone CLI execution compatibility (`python data/pipelines/pipeline.py`) with default calendar windows and custom `--start-date` / `--end-date` arguments, with zero alterations to `services/telemetry/analysis.py` or `telemetry_events`.
4. Delivering a dedicated executive reporting dashboard in `uis/backoffice/` (at route `/reporting`) consuming `GET /api/v1/reporting/kpis`, displaying all five core briefing KPIs, weekly reporting period badges, hub filtering (`GLOBAL`, `US`, `ES`), loading skeletons, and accessible error recovery.
5. Publishing cross-cutting DTOs to `@repo/shared-types` adhering to strict TypeScript (zero `any`).

---

## Technical Context

**Language/Version**: Python 3.11+, TypeScript 5.9+ (Node.js 18+, Next.js 14 App Router, React 18)

**Primary Dependencies**:
- Backend & Pipeline: Prefect 3.x, pandas, numpy, SQLModel, SQLAlchemy, FastAPI, Pydantic v2
- Frontend: Next.js 14, React 18, Tailwind CSS v4
- Testing: pytest

**Storage**:
- PostgreSQL / SQLite fallback (reporting database tables: `executive_kpi_snapshots`, `pipeline_execution_logs`)
- Source Telemetry: `public.telemetry_events` (read-only query)

**Testing**:
- Backend/Pipeline: `pytest tests/pipelines/test_pipeline.py` (in-memory unit tests) and `pytest tests/pipelines/test_pipeline_etl.py` (integration tests)
- Frontend: `npm run typecheck` (`tsc --noEmit`), `npm run build`

**Target Platform**: Linux server / Windows / Node.js runtime

**Project Type**: Monorepo combining Data Pipeline CLI/Worker, FastAPI backend service, and Next.js backoffice web application

**Performance Goals**:
- Executive dashboard route (`/reporting`) Core Web Vitals: LCP ≤ 1.0s, TBT ≤ 200ms, CLS = 0
- Transformation unit test execution: < 2.0s total runtime
- Standalone CLI pipeline execution: completes full ETL within seconds on standard weekly volume

**Constraints**:
- Strict TypeScript & zero `any` policy across all frontend and shared code
- Zero modifications to `services/telemetry/analysis.py` and `telemetry_events` table definition
- Subflows communicate strictly through explicit arguments and return values (no shared mutable state)
- Transformation unit tests run in pure memory with zero live DB/network calls
- Non-critical auxiliary subflow (notifications) invoked with `return_state=True` to prevent pipeline aborts

**Scale/Scope**:
- Weekly operational reporting cycle (default: preceding Monday 00:00:00 to Sunday 23:59:59 UTC)
- Dual fulfillment hubs (`US-LAX-01` and `ES-ZAZ-01`) + consolidated `GLOBAL` scope
- 5 core executive KPIs: Shipments Volume, Global On-Time Delivery Rate, Operational Cost in EUR, Returns Rate, Customer Satisfaction Score

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Requirement | Compliance Analysis | Status |
|---|---|---|---|
| **I. Service Boundaries & Domain Isolation** | Frontend user interfaces in `uis/` must never directly access database files or backend Python modules; inter-service communication via HTTP REST; shared types in `packages/shared/`. | The `/reporting` page in `uis/backoffice/` communicates exclusively via HTTP `GET /api/v1/reporting/kpis` through `reportingApi.ts`. All shared DTOs are published to `packages/shared/types/reporting.ts` (`@repo/shared-types`). `data/pipelines/` interfaces with presentation routes through `data.pipelines.reporting_interface`. | **PASS** |
| **II. Public API Compatibility & Strict Contract Serialization** | Endpoints declare explicit Pydantic `response_model`, typed parameters, and status codes; zero ORM leaks; OpenAPI contracts. | `GET /api/v1/reporting/kpis` uses explicit `response_model=ExecutiveKpisResponse`, validated query parameters, and OpenAPI 3.0 contract in `contracts/reporting-api.yaml`. | **PASS** |
| **III. Strict TypeScript & Static Type Safety** | Strict compliance with `tsconfig.json` (`strict: true`, `noImplicitReturns`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`); zero `any`; explicit return types; JSDoc comments; type imports via `import type`. | All new TypeScript code in `packages/shared/types/reporting.ts`, `uis/backoffice/lib/reportingApi.ts`, and `uis/backoffice/app/reporting/page.tsx` strictly adheres to workspace `tsconfig.json`, zero `any`, and explicit JSDoc annotations. | **PASS** |
| **IV. Defensive Error Handling & Zero Sensitive Data Leaks** | No raw error exposure or stack traces to clients; sanitized errors; zero PII leakage; resilient UI error states with retry buttons; non-zero CLI exit codes on failure. | Pipeline errors are sanitized via `sanitize_error_message` before storing in audit logs; backoffice dashboard displays an accessible error banner with a retry button on fetch failure; CLI script terminates with `sys.exit(1)` on error. | **PASS** |
| **V. Performance-First Architecture & Core Web Vitals** | Production target metrics: LCP ≤ 1.0s, TBT ≤ 200ms, CLS = 0; modern JavaScript; no hydration gatekeeper blockers; loading skeletons matching card geometries. | Backoffice reporting view utilizes CSS grid and flex layouts with animated loading skeletons matching metric card geometry to prevent layout shifts (CLS = 0) and achieve sub-second render (LCP ≤ 1.0s). | **PASS** |
| **VI. Test-First Development & Deterministic Verification Gates** | Automated quality gates: TypeScript typecheck, build validation, pytest execution with zero failures; in-memory unit tests with zero DB/network calls. | Dedicated test file `tests/pipelines/test_pipeline.py` tests transformation tasks with synthetic in-memory fixtures, zero DB dependencies, zero-division guardrails, and hand-calculated mathematical validation. | **PASS** |

---

## Project Structure

### Documentation (this feature)

```text
specs/021-pipeline-subflows-and-tests/
├── plan.md              # Implementation plan (this file)
├── research.md          # Phase 0 architecture research and decisions
├── data-model.md        # Phase 1 data models, schemas, and in-memory structures
├── quickstart.md        # Phase 1 runnable validation scenarios
└── contracts/
    ├── reporting-api.yaml   # OpenAPI 3.0 contract for reporting REST endpoints
    └── pipeline-subflows.md # Python subflow signatures and execution contract
```

### Source Code (repository root)

```text
data/pipelines/
├── pipeline.py             # Refactored: decomposes into 3+ subflows (@flow) + master flow + CLI runner
├── models.py               # SQLModel entities (ExecutiveKpiSnapshot, PipelineExecutionLog)
└── reporting_interface.py  # Presentation bridge for querying KPIs and triggering runs

tests/pipelines/
├── test_pipeline.py        # NEW: Dedicated isolated in-memory transformation unit tests (FR-006-FR-010)
├── test_pipeline_etl.py    # Existing integration ETL tests
└── test_pipeline_resilience.py # Existing fault tolerance tests

packages/shared/
├── types/
│   ├── index.ts            # Re-exports reporting types
│   └── reporting.ts        # NEW: Shared TypeScript interfaces for reporting DTOs and queries
└── package.json

uis/backoffice/
├── app/
│   └── reporting/
│       └── page.tsx        # NEW: Executive reporting dashboard page (/reporting)
├── components/
│   └── Header.tsx          # Updated: Adds 'Reporting' navigation link
└── lib/
    └── reportingApi.ts     # NEW: Client-side fetcher for GET /api/v1/reporting/kpis with auth and telemetry
```

**Structure Decision**:
The feature spans across data pipelines (`data/pipelines/`), backend presentation/domain models (`services/reporting/`), shared contract types (`packages/shared/types/`), test suites (`tests/pipelines/`), and the backoffice frontend application (`uis/backoffice/`). This structure complies with Monorepo Constitution Principle I, isolating business intelligence and presentation concerns while maintaining strict contract boundaries.

---

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No constitutional violations identified. Design adheres 100% to all principles.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| *None* | *N/A* | *N/A* |
