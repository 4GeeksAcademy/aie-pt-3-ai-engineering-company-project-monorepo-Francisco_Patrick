# Research & Architecture Decisions: Pipeline Subflows and Tests

**Feature Branch**: `feature/021-pipeline-subflows-and-tests`  
**Date**: 2026-10-27  
**Status**: Completed  

---

## Overview

This document records the architectural research, engineering trade-offs, and design decisions required to bring the TrackFlow business performance telemetry pipeline to production-ready status and deliver the executive backoffice reporting dashboard.

All decisions adhere strictly to the **TrackFlow Monorepo Constitution** (Principles I through VI) and the strict TypeScript typing guardrails.

---

## Architectural Decisions

### Decision 1: Prefect 3.x Subflow Decomposition & Coordination Architecture

- **Context**: The existing `data/pipelines/pipeline.py` encapsulates extraction, transformation, and loading in individual tasks (`@task`), but all orchestration is executed monolithically inside a single `@flow` (`executive_performance_pipeline_flow`). The feature requirements (FR-001 through FR-005) mandate decomposing this into at least three independent, domain-named subflows (`@flow`) coordinated by the master flow.
- **Decision**: Define three dedicated subflow functions decorated with `@flow`, plus an optional auxiliary notification subflow:
  1. `extract_fulfillment_and_telemetry_flow(period_start: datetime, period_end: datetime) -> Dict[str, pd.DataFrame]`: Calls `extract_telemetry_and_domain_data` task with retries.
  2. `transform_executive_performance_kpis_flow(raw_data: Dict[str, pd.DataFrame], period_start: datetime, period_end: datetime) -> List[Dict[str, Any]]`: Coordinates `transform_executive_kpis` and regional KPI transformations with caching and defensive bounds.
  3. `load_executive_kpi_snapshots_flow(snapshots: List[Dict[str, Any]], run_id: UUID) -> int`: Persists snapshots idempotently via `load_reporting_snapshots`.
  4. `dispatch_pipeline_notifications_flow(run_id: UUID, status: str, summary: Dict[str, Any]) -> bool`: Auxiliary notification subflow invoked by the parent flow using `return_state=True`.
  5. The overarching master flow `executive_performance_pipeline_flow` coordinates execution, manages audit logging in `reporting.pipeline_execution_logs`, and passes outputs sequentially.
- **Rationale**:
  - In Prefect 3.x, decorating subroutines with `@flow` creates native child flow runs in the Prefect state machine, providing distinct execution tracking, individual log streams, and independent restart/retry capabilities.
  - Domain-specific names (FR-003) make operational logs transparent to platform engineers and executives.
  - Isolating auxiliary notifications with `return_state=True` guarantees that non-critical webhook failures cannot abort successful core ETL persistence.
- **Alternatives Considered**:
  - *Keep only `@task` decorators without subflows*: Rejected because it violates FR-001 and fails to expose individual subflow lineage and execution states in Prefect UI.
  - *Separate into separate files (`extract_flow.py`, `transform_flow.py`)*: Rejected to preserve standalone CLI compatibility (`python data/pipelines/pipeline.py`) per FR-011 and existing deployment imports.

---

### Decision 2: Data Flow & Zero Shared Mutable State Architecture

- **Context**: FR-002 mandates that subflows communicate strictly through explicit function arguments and return values; shared mutable global variables between subflows are strictly prohibited.
- **Decision**:
  - `extract_fulfillment_and_telemetry_flow` returns an immutable dictionary mapping domain entity names (`orders`, `tracking`, `returns`, `cx`) to pandas DataFrames.
  - `transform_executive_performance_kpis_flow` takes `raw_data`, `period_start`, and `period_end` as explicit arguments and returns a list of dictionary snapshots conforming to `ExecutiveKpiSnapshot`.
  - `load_executive_kpi_snapshots_flow` takes `snapshots` and `run_id` as explicit arguments and returns the persisted record count.
  - No module-level mutable variables (such as global cache dictionaries or mutable execution contexts) are touched or shared across subflow invocations.
- **Rationale**: Eliminates hidden side effects, ensures deterministic reproducibility during unit and integration testing, and allows any subflow to be run independently with mocked inputs.
- **Alternatives Considered**:
  - *Passing data via shared file artifacts (e.g. Parquet in `/tmp`)*: Unnecessary disk I/O overhead for weekly aggregated metrics; in-memory transfer between subflows is optimal and resilient.

---

### Decision 3: Isolated In-Memory Transformation Testing Architecture (`tests/pipelines/test_pipeline.py`)

- **Context**: FR-006 through FR-010 require a dedicated test module at `tests/pipelines/test_pipeline.py` containing at least three unit tests targeting the pipeline's transformation tasks, running 100% in memory with zero database or network dependencies.
- **Decision**: Implement `tests/pipelines/test_pipeline.py` using `pytest` and pure in-memory synthetic fixtures shaped as pandas DataFrames:
  1. `test_transformation_zero_division_guardrails()`: Tests `compute_regional_metrics` with completely empty DataFrames, verifying default neutral metrics (Volume: 0, On-Time: 1.0, Operational Cost: 0.0, Returns: 0.0, CSAT: 100.0) without throwing exceptions.
  2. `test_transformation_malformed_and_missing_payloads()`: Tests defensive handling of `None` values, missing columns, string costs (`"invalid"`), negative values, and unexpected CSAT ratings (> 5.0 or null). Verifies no uncaught exceptions and safe normalization.
  3. `test_transformation_exact_mathematical_precision()`: Tests against deterministic hand-calculated ground truth for dual hubs (`US-LAX-01`, `ES-ZAZ-01`) and consolidated `GLOBAL` scope based on `company-BRIEFING.md` formulas:
     - Shipments Volume = count of fulfilled orders.
     - Global On-Time Delivery Rate = `mean(is_delivered_on_time)` over latest tracking status per hash.
     - Operational Cost in EUR = `sum(total_cost_eur)`.
     - Returns Rate = `(return_items_count / shipments_volume) * 100.0`.
     - Customer Satisfaction Score = `(avg_rating / 5.0 * 100.0) * 0.70 + (fcr_rate * 100.0) * 0.30`.
- **Rationale**:
  - Testing the transformation logic in isolation from database engines (SQLite/PostgreSQL) and Prefect flow orchestration guarantees sub-second test execution and prevents environmental flakiness.
  - Satisfies FR-007, FR-008, FR-009, and FR-010 with exit code 0.
- **Alternatives Considered**:
  - *Testing through the main flow with a test SQLite database*: While integration tests (`test_pipeline_etl.py`) already do this, FR-007 explicitly requires unit tests in `test_pipeline.py` with zero database dependencies.

---

### Decision 4: Backoffice Executive Dashboard (`/reporting`) Architecture & UX

- **Context**: FR-013 through FR-016 require a dedicated executive reporting dashboard within `uis/backoffice/` at `/reporting`, styled with Tailwind CSS, displaying all five briefing KPIs, weekly cadence date range, regional hub filtering (`GLOBAL`, `US`, `ES`), responsive loading skeletons, and user-friendly error recovery.
- **Decision**:
  - Path: `uis/backoffice/app/reporting/page.tsx`.
  - Client component (`'use client'`) interacting with `/api/v1/reporting/kpis` through a dedicated typed API client (`uis/backoffice/lib/reportingApi.ts`).
  - Layout & Design:
    - Executive Header: Displays page title ("Executive Performance Reporting"), weekly period date badge (e.g. `2026-10-12 to 2026-10-18 UTC`), and hub selector toggle buttons (`GLOBAL`, `US (LAX)`, `ES (ZAZ)`).
    - 5 Core KPI Metric Cards:
      1. **Shipments Volume**: Formatted integer with packages icon.
      2. **On-Time Delivery Rate**: Formatted percentage (e.g., `94.2%`) with SLA badge (green >= 95%, amber >= 90%, red < 90%).
      3. **Operational Cost**: Formatted in EUR (e.g., `€42,150.00`) with cost-per-shipment calculation.
      4. **Returns Rate**: Formatted percentage (e.g., `3.4%`) with quality indicator.
      5. **Customer Satisfaction Score**: Score out of 100 (e.g., `88.5 / 100`) with breakdown indicator (CSAT + FCR).
    - Status Banner: Shows pipeline health and latest snapshot generation timestamp.
    - Error State: When API fetch fails, renders a prominent alert with an accessible retry button ("Retry Loading Metrics") rather than a blank screen.
    - Loading Skeleton: Displays animated pulse placeholders matching card geometries while fetching, eliminating Cumulative Layout Shift (CLS = 0).
  - Navigation: Add "Reporting" link to `uis/backoffice/components/Header.tsx` navbar.
- **Rationale**: Meets CEO Daniel Espinoza's requirement for immediate executive visibility, eliminating spreadsheet bottlenecks while strictly complying with Core Web Vitals (LCP <= 1.0s) and Constitution Principle V.
- **Alternatives Considered**:
  - *Embedding reporting in the existing `/telemetry` page*: Rejected because `/telemetry` focuses on operational technical telemetry (HTTP error rates, auth failures), whereas executive leadership needs a high-level business intelligence view focused on SLA compliance, costs, and customer satisfaction.

---

### Decision 5: Type Safety & Shared Contracts Propagation (`@repo/shared-types`)

- **Context**: Constitution Principle I & III require cross-cutting types and shared contracts to be published to `packages/shared/` (`@repo/shared-types`), with zero `any` types and explicit return types.
- **Decision**:
  - Create `packages/shared/types/reporting.ts`:
    - `ExecutiveKpiSnapshot`: TypeScript interface matching SQLModel/Pydantic DTO.
    - `ExecutiveKpisResponse`: `{ count: number; snapshots: ExecutiveKpiSnapshot[]; }`.
    - `PipelineExecutionLog`: `{ run_id: string; flow_name: string; started_at: string; ... }`.
    - `PipelineStatusResponse`: `{ latest_run: PipelineExecutionLog | null; is_running: boolean; healthy: boolean; }`.
    - `ReportingGeographicScope`: `'US' | 'ES' | 'GLOBAL'`.
    - `ReportingKpisQueryParams`: `{ country?: ReportingGeographicScope; start_date?: string; end_date?: string; }`.
  - Export from `packages/shared/types/index.ts`.
  - Frontend `uis/backoffice/lib/reportingApi.ts` imports all types via `import type { ... } from '@repo/shared-types'`.
- **Rationale**: Single source of truth across backend contracts and frontend consumers, eliminating type drift and runtime deserialization bugs.
- **Alternatives Considered**:
  - *Defining types locally inside `uis/backoffice/lib/`*: Rejected because it violates Constitution Principle I.

---

### Decision 6: CLI Runner Compatibility & Execution Lifecycle

- **Context**: FR-011 requires preserving CLI execution compatibility: `python data/pipelines/pipeline.py` with default trailing 7-day window and optional `--start-date` / `--end-date` arguments.
- **Decision**:
  - Keep `argparse` configuration in `main()` in `data/pipelines/pipeline.py`.
  - Default window calculates preceding Monday 00:00:00 UTC through Sunday 23:59:59 UTC via `get_default_reporting_window()`.
  - Parse ISO strings via `parse_iso_datetime` with timezone validation.
  - Invoke `executive_performance_pipeline_flow(period_start=args.start_date, period_end=args.end_date, return_state=True)`.
  - Exit with `sys.exit(0)` on `flow_state.is_completed()`, or `sys.exit(1)` on failure/exception.
- **Rationale**: Preserves seamless backward compatibility with existing cron tasks, developer scripts, and container entrypoints.

---

### Decision 7: Preservation of Telemetry Analysis Assets

- **Context**: FR-012 and SC-004 require zero modifications to `services/telemetry/analysis.py` or the schema/records of `public.telemetry_events`.
- **Decision**:
  - The pipeline exclusively queries `telemetry_events` in read-only mode during extraction.
  - `services/telemetry/analysis.py` remains untouched.
  - An automated regression test will verify that all original telemetry calculation functions (`calculate_events_per_day`, `calculate_error_rate_by_type`, `calculate_auth_failure_rate`, `generate_telemetry_report`) remain present and unaltered.

---

## Conclusion & Verification Plan

All technical unknowns are resolved. The design satisfies all requirements, respects the Monorepo Constitution, and provides deterministic verification gates. We proceed directly to Phase 1: Data Model, Contracts, and Quickstart Guide.
