# Feature Specification: Pipeline Enhancement: Subflows and Tests

**Feature Branch**: `feature/021-pipeline-subflows-and-tests`

**Created**: 2026-10-27

**Status**: Draft

**Input**: User description: "Bring your existing business performance telemetry pipeline to production-ready status by upgrading orchestration, enforcing test coverage, preserving CLI execution, and exposing actionable metrics to leadership via a dedicated backoffice dashboard."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Executive Dashboard for Business Performance Metrics (Priority: P1)

As CEO Daniel Espinoza and executive leadership, I need a dedicated, business-facing reporting dashboard within the backoffice web application (`/reporting`) that displays all five core TrackFlow KPIs (Shipments Volume, Global On-Time Delivery Rate, Operational Cost in EUR, Returns Rate, and Customer Satisfaction Score) calculated across dual fulfillment hubs (Los Angeles and Zaragoza), so that I can evaluate commercial health, carrier SLA compliance, and unit economics during Monday morning reviews without deciphering technical logs or running manual database queries.

**Why this priority**: The ultimate purpose of a business intelligence pipeline is delivering accessible, actionable insights to decision-makers. Visualizing pre-aggregated metrics on an executive backoffice screen provides immediate business value and eliminates the Sunday spreadsheet assembly bottleneck.

**Independent Test**: Navigate to `/reporting` in the backoffice application. Verify that all five briefing KPIs are displayed with explicit business labels, that the current weekly reporting period is clearly shown, that geographic filtering (US, ES, GLOBAL) updates the metrics accurately, and that data is fetched directly from the reporting service endpoint without rendering raw technical fields.

**Acceptance Scenarios**:

1. **Given** pre-computed KPI snapshots stored in the reporting database, **When** the executive navigates to `/reporting` in `uis/backoffice/`, **Then** the page renders every KPI defined in the company briefing (Shipments Volume, Global On-Time Delivery Rate, Operational Cost in EUR, Returns Rate, Customer Satisfaction Score) with non-technical, domain-accurate labels.
2. **Given** the weekly operational reporting cycle, **When** viewing the dashboard, **Then** the page visibly displays the reporting period date window (start date and end date) corresponding to the displayed snapshot.
3. **Given** multi-hub operations across `US-LAX-01` and `ES-ZAZ-01`, **When** the executive toggles between geographic scopes (`GLOBAL`, `US`, `ES`), **Then** the metrics dynamically update to show regional values for the selected hub or consolidated global figures.
4. **Given** an error state or network failure while querying the reporting endpoint, **When** the page fails to load data, **Then** the dashboard displays an understandable, user-friendly error message with a retry action, rather than an unhandled blank screen or exposed raw stack trace.

---

### User Story 2 - Modular Subflow Architecture Decomposition (Priority: P1)

As a data platform engineer, I need the monolithic main pipeline flow in `data/pipelines/pipeline.py` refactored into at least three independent, domain-named subflows (`@flow`) covering extraction, transformation, and load—coordinated by an overarching master flow—so that each ETL stage can be developed, tested, and executed in isolation with explicit inputs and outputs and without global variable coupling.

**Why this priority**: Production pipelines require modular architecture following the DRY principle. Deconstructing extraction, transformation, and persistence into discrete subflows enables modular debugging, independent scheduling, clear lineage tracking in Prefect UI, and safe testing without side effects.

**Independent Test**: Execute each individual subflow independently in an automated runner or script. Verify that the extraction subflow accepts date window parameters and outputs structured domain datasets; that the transformation subflow accepts raw datasets and outputs aggregated KPI snapshots; and that the load subflow accepts snapshots and idempotently persists them with an audit log.

**Acceptance Scenarios**:

1. **Given** the pipeline module `data/pipelines/pipeline.py`, **When** inspecting flow definitions, **Then** the file defines at least three modular subflows decorated with `@flow` representing domain extraction, transformation, and load stages, named using TrackFlow domain vocabulary.
2. **Given** the modular subflows, **When** the main flow coordinates execution, **Then** it invokes the extraction subflow, passes its explicit returned output directly into the transformation subflow, and passes the transformation output into the load subflow without reading or mutating global state.
3. **Given** optional auxiliary stages (such as execution notification dispatch or audit reporting), **When** these stages run as subflows, **Then** the main flow invokes them capturing their execution state (`return_state=True`), allowing auxiliary failures to be logged without failing the core business data delivery.
4. **Given** individual subflow functions, **When** invoked directly outside the main flow, **Then** each subflow can execute independently provided its explicit parameter dependencies are met.

---

### User Story 3 - Isolated Transformation Unit Testing & Defensive Coverage (Priority: P2)

As a QA and data reliability engineer, I need a comprehensive suite of unit tests in `tests/pipelines/test_pipeline.py` that validates transformation tasks in complete isolation using in-memory fixtures shaped like TrackFlow telemetry events, verifying exact KPI mathematical calculations and defensive handling of malformed inputs without database or network dependencies.

**Why this priority**: High-stakes business decisions depend on metric accuracy. Automated unit tests ensure that carrier on-time rates, return percentages, and CSAT calculations never regress, and that corrupted or null-value telemetry events cannot crash scheduled production runs.

**Independent Test**: Run `python -m pytest tests/pipelines/test_pipeline.py` in an environment disconnected from databases and network services. Verify that all tests pass, that at least three transformation tasks are tested, that defensive edge cases against invalid inputs pass, and that calculated KPIs match hand-calculated expected values.

**Acceptance Scenarios**:

1. **Given** in-memory synthetic telemetry events matching the schema in `company-BRIEFING.md` and `PIPELINE_DESIGN.md`, **When** transformation tasks are invoked in unit tests, **Then** the tests run entirely in memory with zero live database queries or external network requests.
2. **Given** a deterministic set of sample telemetry records with known ground truth, **When** the KPI transformation functions execute, **Then** the computed values for all five KPIs (Volume, On-Time Rate, Operational Cost, Returns Rate, CSAT) exactly match the hand-calculated expected values per the company briefing formulas.
3. **Given** malformed, partial, or unexpected telemetry payloads (such as null delivery timestamps, missing cost columns, empty DataFrames, or invalid CSAT ratings), **When** the transformation tasks process the data, **Then** the tasks execute defensively without unhandled runtime exceptions, applying safe neutral fallbacks and zero-division guardrails.
4. **Given** the test file `tests/pipelines/test_pipeline.py`, **When** executed via `python -m pytest tests/pipelines/test_pipeline.py`, **Then** the entire test suite executes and terminates with exit code 0.

---

### User Story 4 - Preserved Standalone CLI Execution Compatibility (Priority: P2)

As a DevOps engineer and automated job scheduler, I need the refactored pipeline to remain fully runnable as a standalone CLI script (`python data/pipelines/pipeline.py`) accepting optional date window arguments, so that existing cron jobs, container entrypoints, and developer maintenance workflows continue functioning without interruption.

**Why this priority**: Existing operational infrastructure and run-command documentation rely on the established CLI entry point. Breaking script invocation would compromise scheduled executions and manual operational backfills.

**Independent Test**: Run `python data/pipelines/pipeline.py` from the project root in a terminal with default settings, and run `python data/pipelines/pipeline.py --start-date 2026-10-12T00:00:00Z --end-date 2026-10-18T23:59:59Z`. Verify that both executions complete the full ETL pipeline successfully and return a zero exit status.

**Acceptance Scenarios**:

1. **Given** default invocation without arguments, **When** running `python data/pipelines/pipeline.py`, **Then** the script calculates the default trailing 7-day reporting window, triggers the main flow and its subflows, logs progress, and exits cleanly with code 0 upon success.
2. **Given** explicit ISO date window arguments (`--start-date` and `--end-date`), **When** running `python data/pipelines/pipeline.py`, **Then** the CLI parses the arguments into UTC datetimes and executes the full ETL pipeline across the specified time bounds.
3. **Given** existing system telemetry assets (`services/telemetry/analysis.py` and `telemetry_events`), **When** the subflow refactoring is implemented and executed, **Then** these existing technical telemetry modules remain completely unmodified.

---

### Edge Cases

- **Zero Ingestion Volume in Subflows**: When the extraction subflow encounters an empty event window, the returned empty datasets must flow smoothly through the transformation subflow, triggering zero-division guards (defaulting on-time rate to 1.0, returns rate to 0.0, CSAT to 100.0) and generating valid zero-volume snapshot records.
- **Malformed Event Payloads**: When incoming telemetry contains records with invalid data types (e.g., non-numeric costs or strings in boolean delivery flags), transformation tasks sanitize or coerce the invalid entries rather than failing the entire batch.
- **Reporting Endpoint Unavailability**: When the backoffice dashboard loads while the backend reporting service is temporarily unreachable, the frontend displays an accessible error notification with a retry button instead of crashing or hanging indefinitely.
- **Partial Failure in Non-Critical Subflow**: When an auxiliary subflow (e.g., webhook notification) raises an unhandled error, the main flow traps the failure state via `return_state=True`, logs the warning, and allows the primary ETL subflows to conclude with status `SUCCESS`.
- **Duplicate Execution Window**: When executing the CLI repeatedly over identical dates, the load subflow performs idempotent upserts (`ON CONFLICT DO UPDATE`), guaranteeing no duplicate snapshot records or constraint violations occur in `reporting.executive_kpi_snapshots`.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST decompose the business performance data pipeline in `data/pipelines/pipeline.py` into at least three modular subflows decorated with `@flow`:
  - An extraction subflow extracting domain telemetry records within watermark bounds.
  - A transformation subflow computing pre-aggregated executive KPIs.
  - A load subflow idempotently persisting snapshots into the destination table.
- **FR-002**: Subflows MUST communicate strictly through explicit function arguments and return values; shared mutable global variables between subflows are strictly prohibited.
- **FR-003**: System MUST name all subflows, tasks, and test functions using domain vocabulary reflecting TrackFlow business entities and KPIs (e.g., `extract_fulfillment_and_telemetry_flow`, `transform_executive_performance_kpis_flow`, `load_executive_kpi_snapshots_flow`) rather than generic names like `extract_data`.
- **FR-004**: System MUST maintain the overarching main flow in `data/pipelines/pipeline.py` that invokes the subflows in deterministic sequential order and coordinates overall execution state and audit logging.
- **FR-005**: If non-critical auxiliary steps (such as notification alerts or secondary exports) are executed as subflows, the main flow MUST invoke them with `return_state=True` so that auxiliary failures do not abort or fail the primary ETL execution.
- **FR-006**: System MUST implement a dedicated test module at `tests/pipelines/test_pipeline.py` containing at least three unit tests targeting the pipeline's transformation tasks.
- **FR-007**: Unit tests in `tests/pipelines/test_pipeline.py` MUST execute entirely in isolation, utilizing in-memory fixtures shaped like TrackFlow telemetry events with zero dependencies on live databases or external HTTP APIs.
- **FR-008**: The test suite MUST include at least one defensive unit test verifying that transformation tasks handle invalid, malformed, or missing input fields gracefully without throwing uncaught exceptions.
- **FR-009**: The test suite MUST include at least one validation test that compares computed KPI results against exact, hand-calculated values derived from the definitions in `company-BRIEFING.md` and `PIPELINE_DESIGN.md`.
- **FR-010**: All unit tests in `tests/pipelines/test_pipeline.py` MUST pass cleanly when executed via `python -m pytest tests/pipelines/test_pipeline.py`.
- **FR-011**: System MUST preserve CLI execution compatibility, ensuring `python data/pipelines/pipeline.py` executes the full ETL pipeline with default and custom `--start-date` / `--end-date` arguments without code breakage.
- **FR-012**: System MUST NOT modify `services/telemetry/analysis.py` or the schema/records of `public.telemetry_events`.
- **FR-013**: System MUST create an executive reporting page within `uis/backoffice/` (at route `/reporting`) that consumes pre-computed metrics from the `services/reporting/` REST API endpoint (`GET /api/v1/reporting/kpis`).
- **FR-014**: The reporting page MUST render all five core executive KPIs defined in `company-BRIEFING.md` (Shipments Volume, Global On-Time Delivery Rate, Operational Cost in EUR, Returns Rate, Customer Satisfaction Score) using clear, business-facing labels.
- **FR-015**: The reporting page MUST clearly display the reporting cadence period (start date to end date) that the active KPI snapshot covers.
- **FR-016**: The reporting dashboard MUST be presented with high legibility for executive stakeholders (e.g., CEO Daniel Espinoza), incorporating regional hub filtering (`GLOBAL`, `US`, `ES`), clean metric cards or summary tables, responsive loading states, and user-safe error fallbacks.

---

### Key Entities *(include if feature involves data)*

- **Executive KPI Snapshot (`reporting.executive_kpi_snapshots`)**:
  - Represents pre-aggregated weekly performance metrics for a specific geographic scope (`US`, `ES`, `GLOBAL`).
  - Key attributes: `snapshot_id`, `period_start`, `period_end`, `country`, `shipments_volume`, `on_time_delivery_rate`, `operational_cost_eur`, `returns_rate`, `customer_satisfaction_score`, `generated_at`.
- **Pipeline Execution Log (`reporting.pipeline_execution_logs`)**:
  - Audit trail documenting individual pipeline execution runs.
  - Key attributes: `run_id`, `flow_name`, `started_at`, `ended_at`, `records_processed`, `status` (`RUNNING`, `SUCCESS`, `FAILED`), `error_details`.
- **Telemetry Event (`public.telemetry_events`)**:
  - Append-only operational event stream capturing domain interactions (`outbound_order_fulfilled`, `shipment_tracking_updated`, `carrier_recommendation_selected`, `return_request_evaluated`, `cx_inquiry_resolved`).
- **Reporting DTOs (`ExecutiveKpisResponse`, `PipelineStatusResponse`)**:
  - Data transfer schemas serving structured metric snapshots and pipeline operational health to frontend clients over HTTP.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of pipeline stages (extraction, transformation, load) are encapsulated in independent subflows, eliminating inline logic from the main flow.
- **SC-002**: 100% of unit tests in `tests/pipelines/test_pipeline.py` pass without external network or database connections (`0 failures, 0 errors` in `pytest`).
- **SC-003**: The pipeline CLI command (`python data/pipelines/pipeline.py`) completes end-to-end execution with exit code 0 when run with default and custom date parameters.
- **SC-004**: Zero changes are introduced to `services/telemetry/analysis.py` and `telemetry_events` table definition.
- **SC-005**: All five briefing KPIs are visible and correctly labeled on the `/reporting` page in `uis/backoffice/`.
- **SC-006**: Executive dashboard page in `uis/backoffice/` loads and renders metrics within 1.0 second on production builds, adhering to Core Web Vitals standards.
- **SC-007**: 100% of TypeScript code in the backoffice reporting view adheres to zero `any` types and passes static type checking (`npm run typecheck`).

---

## Assumptions

- The backend reporting service (`services/reporting/`) implemented in Part 2 provides functional `GET /api/v1/reporting/kpis` and `GET /api/v1/reporting/status` endpoints accessible to the backoffice frontend.
- Prefect 3.x is the orchestration framework used across the pipeline and supports subflows decorated with `@flow` called within parent flows.
- The reporting database engine (PostgreSQL with SQLite local development fallback) is already provisioned and initialized via `init_reporting_db()`.
- The reporting cadence is weekly, defaulting to the preceding Monday 00:00:00 UTC through Sunday 23:59:59 UTC.
- The backoffice frontend application is a Next.js App Router application located in `uis/backoffice/`.
