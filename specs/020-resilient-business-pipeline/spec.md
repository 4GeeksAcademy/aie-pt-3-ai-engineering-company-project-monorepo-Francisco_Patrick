# Feature Specification: Implementing a Resilient Business Performance Pipeline

**Feature Branch**: `feature/020-resilient-business-pipeline`  
**Created**: 2026-10-20  
**Status**: Draft  
**Input**: User description: "Implementing a Resilient Business Performance Pipeline: The goal is to implement a resilient, command-line-runnable production data pipeline using Prefect—based on the approved design document—that reads from telemetry events to compute the business-facing KPIs scoped in Part 1 with built-in partial failure tolerance, smart task retries, and result caching, all while leaving the existing technical telemetry system completely untouched."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Command-Line Execution of Resilient Multi-Stage Pipeline (Priority: P1)

As a data platform engineer, I need to execute the production data pipeline directly via a command-line script (`python data/pipelines/pipeline.py`) that orchestrates independent extraction, transformation, and load stages with built-in retries for external systems, result caching for expensive transformations, and partial-failure tolerance for non-critical steps, so that executive business metrics are reliably calculated even under transient network or downstream service errors.

**Why this priority**: Without an executable, resilient pipeline, leadership cannot receive automated weekly business metrics. Fault tolerance (retries, caching, non-blocking auxiliary steps) is essential to ensure transient network glitches or non-critical notification failures do not crash the primary data delivery.

**Independent Test**: Execute `python data/pipelines/pipeline.py` from the project root. Verify that extraction, transformation, loading, and auxiliary notification/audit tasks run sequentially, that transient external failures retry as configured, and that an injected failure in a non-critical step allows the primary ETL process to finish successfully.

**Acceptance Scenarios**:

1. **Given** valid telemetry events in `telemetry_events` and domain tables, **When** the operator runs `python data/pipelines/pipeline.py`, **Then** the main flow executes extraction, transformation, and load stages without unhandled exceptions and writes the computed KPI snapshots.
2. **Given** tasks interacting with external resources (database queries and writes), **When** a transient failure occurs during execution, **Then** the task automatically retries according to configured retry parameters (`retries > 0`, `retry_delay_seconds`) with logged justifications.
3. **Given** an optional non-critical pipeline step (such as an alert notification, export snapshot, or status webhook), **When** this step encounters an error during execution, **Then** the flow captures its failure state (`return_state=True`) without interrupting or terminating the core extract-transform-load pipeline.
4. **Given** an expensive transformation task with identical inputs within the cache validity window, **When** the pipeline runs consecutively, **Then** the task utilizes its cached results rather than re-executing redundant data manipulations.

---

### User Story 2 - Idempotent Persistence & Execution Audit Tracking (Priority: P1)

As an executive stakeholder and auditor, I need every pipeline run to persist aggregated KPIs into the dedicated destination table (`reporting.executive_kpi_snapshots`) with strict idempotency and record comprehensive run metadata in the database or structured log, so that repeated executions or backfills never corrupt historical metrics or create duplicate entries.

**Why this priority**: Business leaders make critical staffing and carrier decisions based on these metrics. Duplicate rows, skewed sums, or unrecorded pipeline failures would destroy executive confidence and violate data integrity standards.

**Independent Test**: Run the pipeline over a designated historical 7-day reporting period twice in succession. Query the destination table to verify that record counts and values for `(period_start, period_end, country)` remain identical with zero duplicates. Inspect the execution log to confirm both runs recorded all mandatory audit metadata fields.

**Acceptance Scenarios**:

1. **Given** a designated extraction time window, **When** the pipeline runs twice over the exact same period, **Then** the destination table contains exactly the same unique snapshot rows for each geographic scope (`US`, `ES`, `GLOBAL`) with no duplicate records.
2. **Given** any pipeline execution (whether successful or failed), **When** the run completes or terminates, **Then** an audit record is stored containing at least five mandatory metadata fields: unique run identifier, start timestamp, end timestamp, total records processed, final status (`RUNNING`, `SUCCESS`, `FAILED`), and sanitized error details if applicable.
3. **Given** a fatal error during the load transaction, **When** the exception occurs, **Then** the database transaction rolls back cleanly, avoiding partial snapshot writes, and records the failure state in the execution audit store.

---

### User Story 3 - Decoupled Reporting Backend Endpoints (Priority: P2)

As a frontend developer building the executive backoffice dashboard, I need dedicated REST API endpoints under `services/reporting/` to query the latest pipeline execution status, trigger on-demand pipeline runs, and retrieve pre-computed executive KPI snapshots matching the briefing contract, without coupling to or duplicating internal pipeline logic.

**Why this priority**: Executive dashboards require clean, low-latency API access to pre-computed metrics. Decoupling presentation endpoints from data pipeline execution preserves monorepo architectural boundaries and ensures high dashboard responsiveness.

**Independent Test**: Send HTTP requests to `GET /api/v1/reporting/status`, `POST /api/v1/reporting/trigger`, and `GET /api/v1/reporting/kpis`. Verify that status returns the latest run metadata, trigger invokes the pipeline without duplicating ETL code, and KPI queries return correctly shaped responses matching `reporting-api.yaml`.

**Acceptance Scenarios**:

1. **Given** previous pipeline executions, **When** a client sends `GET /api/v1/reporting/status`, **Then** the service returns the status and metadata of the most recent pipeline run (status, start time, end time, records processed, health flag).
2. **Given** an authorized administrative request, **When** a client sends `POST /api/v1/reporting/trigger`, **Then** the endpoint triggers a pipeline execution by importing and invoking the flow function from `data/pipelines/` without duplicating extraction or transformation code in `services/`.
3. **Given** pre-computed KPI snapshots in the database, **When** a client sends `GET /api/v1/reporting/kpis` with optional country or date filters, **Then** the response returns the matching KPI rows conforming to the briefing schema and OpenAPI contract.
4. **Given** standard API authentication and security rules, **When** accessing reporting endpoints, **Then** the endpoints follow the application's existing authentication conventions, response formatting, and error-masking policies.

---

### User Story 4 - Data Model Fidelity & Telemetry System Preservation (Priority: P2)

As the CTO Andrés Kim, I need the implemented pipeline and endpoints to strictly honor the domain entities, naming conventions, and KPI mathematical definitions documented in `data/pipelines/PIPELINE_DESIGN.md` and `company-BRIEFING.md` while leaving existing engineering telemetry (`services/telemetry/` and `telemetry_events`) completely untouched, so that technical observability continues uninterrupted.

**Why this priority**: Reinterpreting KPIs or altering existing telemetry services would break operational observability and misalign executive reporting with real business operations.

**Independent Test**: Review git diffs across `services/telemetry/analysis.py` and `telemetry_events` table schema to ensure zero changes. Verify that flow names, task names, table names, and field names match `PIPELINE_DESIGN.md` and that KPI calculations reflect the exact business formulas.

**Acceptance Scenarios**:

1. **Given** existing telemetry services, **When** the new pipeline and reporting services are implemented and run, **Then** `services/telemetry/analysis.py` and `public.telemetry_events` remain completely untouched.
2. **Given** the 5 mandatory executive metrics (Shipments Volume, Global On-Time Delivery Rate, Operational Cost in EUR, Returns Rate, Customer Satisfaction Score), **When** transformed from raw events, **Then** their calculated values match the exact formulas specified in the design document and company briefing.
3. **Given** the entities in the pipeline, **When** inspecting code and schemas, **Then** flow names, task names, table names (`reporting.executive_kpi_snapshots`, `reporting.pipeline_execution_logs`), and field names match the approved design.

---

### Edge Cases

- **Zero Ingestion Volume**: When an extraction window contains zero source telemetry events, the transformation stage must apply zero-division guardrails (e.g. on-time rate defaults to 1.0, returns rate defaults to 0.0, CSAT defaults to 100.0) and produce valid zero-volume snapshot records without division-by-zero exceptions.
- **Concurrent Trigger Conflict**: When a manual trigger request (`POST /reporting/trigger`) is received while a pipeline run is already in `RUNNING` status, the endpoint must return a structured conflict status (`409 Conflict`) to prevent overlapping race conditions.
- **Transient Database Connection Dropout**: When the database adapter experiences a network timeout or connection reset during extraction or load tasks, the task retry mechanism must retry up to the configured limit before bubbling a terminal failure.
- **Partial Flow Failure in Auxiliary Steps**: When an optional task (such as external notification dispatch or evaluation snapshot creation) raises an exception, the flow explicitly traps the error via `return_state=True`, logs the warning, and allows downstream load and audit tasks to finish with status `SUCCESS`.
- **Duplicate Run Key Collision**: When backfilling or repeating a pipeline run for an existing `(period_start, period_end, country)` tuple, the load task executes an atomic upsert (`ON CONFLICT DO UPDATE`), overwriting existing records without primary key constraint violation.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST implement the primary orchestration flow in `data/pipelines/pipeline.py` using `@flow(name="executive_performance_pipeline_flow")` adhering to the design structure in `PIPELINE_DESIGN.md`.
- **FR-002**: System MUST structure the pipeline into independent tasks using `@task` with explicit inputs and typed outputs, covering at a minimum extraction (`extract_telemetry_and_domain_data`), transformation (`transform_executive_kpis`), and load (`load_reporting_snapshots`).
- **FR-003**: System MUST include at least one optional/non-critical task (e.g., status notification or secondary audit snapshot) invoked within the flow using `return_state=True` so that its failure does not interrupt core ETL execution.
- **FR-004**: System MUST configure `retries` (> 0) and `retry_delay_seconds` on every task interacting with external services (database, network I/O) and include code comments justifying the retry count.
- **FR-005**: System MUST explicitly handle at least one task failure in the flow using `return_state=True` rather than allowing unhandled exception propagation.
- **FR-006**: System MUST configure result caching (`cache_key_fn` and `cache_expiration`) on at least one expensive transformation task, accompanied by code comments explaining the cache key definition and expiration window.
- **FR-007**: System MUST implement an idempotent loading strategy into the destination table (`reporting.executive_kpi_snapshots`) keyed on the composite constraint `(period_start, period_end, country)` such that executing the pipeline repeatedly over the same time window yields identical results without duplicate rows.
- **FR-008**: System MUST record execution metadata for every pipeline invocation into the database (`reporting.pipeline_execution_logs`) or a structured log, capturing at least five mandatory fields: `run_id`, `started_at`, `ended_at`, `records_processed`, `status` (`RUNNING`, `SUCCESS`, `FAILED`), and `error_details`.
- **FR-009**: System MUST support direct command-line execution via `python data/pipelines/pipeline.py` using an `if __name__ == "__main__":` entry point block.
- **FR-010**: System MUST document the intended execution schedule (weekly Mondays at 06:00 UTC for Monday 07:00 executive review) and the direct CLI execution command in `data/pipelines/PIPELINE_DESIGN.md` and inline file header comments.
- **FR-011**: System MUST establish a dedicated backend reporting module in `services/reporting/` completely isolated from `services/telemetry/`.
- **FR-012**: System MUST implement `GET /api/v1/reporting/status` in `services/reporting/` to query the status and execution metadata of the last pipeline run.
- **FR-013**: System MUST implement `POST /api/v1/reporting/trigger` in `services/reporting/` to trigger a manual pipeline run, importing flow/runner functions directly from `data/pipelines/` without duplicating pipeline logic.
- **FR-014**: System MUST implement `GET /api/v1/reporting/kpis` in `services/reporting/` to query pre-computed KPI rows from the destination table, conforming to the contract defined in `reporting-api.yaml`.
- **FR-015**: Reporting endpoints in `services/reporting/` MUST follow standard API authentication conventions, consistent response formatting, and defensive error-masking without leaking internal credentials or stack traces.
- **FR-016**: System MUST preserve existing telemetry assets completely untouched: `services/telemetry/analysis.py` and `public.telemetry_events` must not be modified.
- **FR-017**: System MUST calculate the five business-facing KPIs exactly as defined in `company-BRIEFING.md` and `PIPELINE_DESIGN.md`: Shipments Volume, Global On-Time Delivery Rate, Operational Cost in EUR, Returns Rate, and Customer Satisfaction Score across `US`, `ES`, and `GLOBAL` scopes.
- **FR-018**: System MUST maintain strict naming fidelity: flow names, task names, table names, and field names must strictly match those defined in `data/pipelines/PIPELINE_DESIGN.md`.

---

### Key Entities *(include if feature involves data)*

- **Executive KPI Snapshot (`reporting.executive_kpi_snapshots`)**: Represents a weekly aggregated business performance snapshot for a specific reporting period (`period_start`, `period_end`) and geographic region (`country`: `US`, `ES`, or `GLOBAL`). Attributes include `snapshot_id`, `shipments_volume`, `on_time_delivery_rate`, `operational_cost_eur`, `returns_rate`, `customer_satisfaction_score`, and `generated_at`.
- **Pipeline Execution Log (`reporting.pipeline_execution_logs`)**: Represents the audit trail of an individual pipeline invocation. Attributes include `run_id`, `flow_name`, `started_at`, `ended_at`, `records_processed`, `status` (`RUNNING`, `SUCCESS`, `FAILED`), and `error_details`.
- **Reporting Interface DTOs**: Data transfer objects defining request/response structures across the reporting boundary (`PipelineStatusResponse`, `PipelineTriggerRequest`, `PipelineTriggerResponse`, `ExecutiveKpisResponse`, `ExecutiveKpiSnapshot`).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Executing the pipeline twice consecutively across the same 7-day reporting period results in exactly 3 snapshot records (US, ES, GLOBAL) in the destination table with 0 duplicate rows or primary key constraint violations.
- **SC-002**: When an intentional failure is introduced into the optional non-critical pipeline step, the flow completes all core ETL steps (extract, transform, load) with 100% data delivery.
- **SC-003**: 100% of pipeline executions (both successful and failed runs) persist an audit record containing all five mandatory metadata fields (`run_id`, `started_at`, `ended_at`, `records_processed`, `status`, `error_details`).
- **SC-004**: The command `python data/pipelines/pipeline.py` executes from the repository root to full completion with exit code 0 under standard test conditions.
- **SC-005**: All three presentation endpoints (`/reporting/status`, `/reporting/trigger`, `/reporting/kpis`) successfully serialize responses according to `reporting-api.yaml` with p95 response latencies under 100ms for pre-computed snapshots.
- **SC-006**: Git diff verification confirms exactly zero modifications to `services/telemetry/analysis.py` and zero schema changes to the `public.telemetry_events` table.
- **SC-007**: 100% of the computed KPI metrics match the mathematical formulas specified in `data/pipelines/PIPELINE_DESIGN.md` across all three geographic scopes (US, ES, GLOBAL).

---

## Assumptions

- **Database Availability**: The SQLite database fallback (`services/api/inventory.db`) or PostgreSQL instance contains the necessary source tables (`telemetry_events`, `orders`, `stock_exit`, `sku`) or is initialized during local development setup.
- **Prefect Orchestration Environment**: Prefect 2.x/3.x is installed or available in the Python virtual environment (`requirements.txt` / active environment) to support `@flow` and `@task` decorators, task retries, state inspections (`return_state=True`), and caching.
- **Security & Authorization**: The reporting presentation endpoints in `services/reporting/` adopt the existing FastAPI authentication middleware and dependency patterns established in `services/api/`.
- **Geographic Scope**: Fulfillment hubs are strictly defined as `US-LAX-01` (`US`), `ES-ZAZ-01` (`ES`), and aggregate `GLOBAL`.
- **Extraction Window Defaults**: When no explicit parameters are passed via CLI or API trigger, the pipeline defaults to extracting the trailing 7-day window ending at the previous Sunday 23:59:59 UTC.
