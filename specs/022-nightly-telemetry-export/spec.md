# Feature Specification: Automated Nightly Telemetry Export & Orchestration

**Feature Branch**: `feature/Background_Processes`

**Created**: 2026-10-27

**Status**: Draft

**Input**: User description: "Implement an automated, resilient nightly background process that orchestrates the daily telemetry export and triggers the data pipeline without manual intervention."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Autonomous Daily Orchestration & Pipeline Execution (Priority: P1)

As a TrackFlow data analyst and executive stakeholder, I need the system to automatically extract the previous day's telemetry events and trigger the daily KPI analytical pipeline every night without human intervention, so that fresh business performance metrics and executive dashboards are ready at the start of each business day.

**Why this priority**: Daily business operations and executive reviews depend on up-to-date KPI calculations. Manual execution creates operational bottlenecks, delays reporting, and introduces human error into critical metrics delivery.

**Independent Test**: Trigger the nightly orchestration process in a test environment with a set target date. Verify that the telemetry events for that date are archived into an audit snapshot file, that the downstream KPI analytical pipeline completes successfully, and that the execution lifecycle is fully recorded in the audit log.

**Acceptance Scenarios**:

1. **Given** telemetry events recorded for a target date in the central database, **When** the nightly export process runs autonomously, **Then** it generates an audit snapshot CSV in the raw data directory named `telemetry_YYYY-MM-DD.csv` corresponding to that target date.
2. **Given** the export step has successfully produced the audit file, **When** the export finishes, **Then** the process automatically invokes the downstream telemetry KPI pipeline as an isolated subprocess.
3. **Given** the pipeline run finishes successfully, **When** the orchestration cycle concludes, **Then** the job run record is updated to `completed` with explicit start and finish timestamps.
4. **Given** an automated schedule, **When** the process executes in the background, **Then** it operates outside the application server's web request thread, having zero impact on public API availability and response latency.

---

### User Story 2 - Concurrency Locking & Duplicate Run Prevention (Priority: P1)

As a platform operations engineer, I need the background process to enforce execution locking so that if multiple instances of the nightly job are triggered concurrently or overlap, subsequent instances terminate immediately without performing duplicate exports or overlapping pipeline calculations.

**Why this priority**: Concurrent execution of data pipelines causes database write contention, duplicate audit artifacts, skewed KPI aggregates, and unnecessary cloud computing overhead.

**Independent Test**: Launch two simultaneous instances of the nightly export script. Verify that the first instance acquires the processing lock, while the second instance detects an active job, silently aborts without raising unhandled errors, and logs the cancellation event.

**Acceptance Scenarios**:

1. **Given** an active nightly export currently marked with status `processing`, **When** a secondary instance of the nightly process is launched, **Then** the second instance detects the active lock, skips execution immediately, and logs the cancellation at `INFO` level.
2. **Given** an instance aborted due to concurrency locking, **When** inspecting system state, **Then** no duplicate audit CSV files are created and the secondary instance does not trigger a duplicate pipeline subprocess.
3. **Given** the active job subsequently finishes, **When** the state transitions to `completed` or `failed`, **Then** the processing lock is effectively released for subsequent scheduled intervals.

---

### User Story 3 - Per-Day Idempotency & Historical Re-runs (Priority: P1)

As a data reliability engineer or operations analyst, I need the nightly process to be strictly idempotent per target date and support an optional date override, so that re-running the job for an already-completed day does not duplicate work, while historical backfills can be safely executed on demand.

**Why this priority**: Network hiccups, scheduler retries, or manual re-executions must never duplicate processing or corrupt existing audit snapshots. Historical backfilling must be predictable and safe without requiring code modifications.

**Independent Test**: Run the process for a specific target date until completion. Re-run the process with the same target date. Verify that the second run detects the existing completed record, skips the export and pipeline execution, logs the duplicate skip, and exits cleanly.

**Acceptance Scenarios**:

1. **Given** a target date that already has a record marked `completed` in the execution store, **When** the nightly process is triggered for that same date, **Then** it skips both the file export and the downstream pipeline, logging that execution was skipped as a duplicate.
2. **Given** an existing audit file `telemetry_YYYY-MM-DD.csv` in the raw data directory for the target date, **When** the export step executes, **Then** it does not overwrite or re-create the existing audit file.
3. **Given** the optional target date environment variable is provided (e.g. `TARGET_DATE=2026-10-25`), **When** the script is executed, **Then** it targets that specific calendar date instead of defaulting to the previous UTC day.
4. **Given** no target date override is provided, **When** the script is executed, **Then** it resolves the target date to yesterday in UTC calendar time.

---

### User Story 4 - Fault Resiliency & Clean State Recovery (Priority: P2)

As a system administrator, I need any unexpected runtime failure during export or pipeline execution to transition the job status cleanly to `failed` with descriptive diagnostic messages, ensuring no job is left stranded in `processing` status.

**Why this priority**: Zombie locks left in `processing` prevent future scheduled runs from executing, requiring manual administrative intervention to clear. Comprehensive error capture ensures prompt incident diagnosis.

**Independent Test**: Simulate an execution error (e.g., simulating pipeline subprocess failure or export error). Verify that the unhandled exception is caught, the job status is set to `failed`, the error message is recorded, the lock is cleared, and an error-level log is emitted.

**Acceptance Scenarios**:

1. **Given** an unexpected exception during file export or a non-zero exit code from the pipeline subprocess, **When** the failure occurs, **Then** the job run record is updated with status `failed`, records the error summary, and updates the `finished_at` timestamp.
2. **Given** any termination path (success or failure), **When** the process exits, **Then** no record remains in `processing` status.
3. **Given** an execution failure, **When** inspected in the log stream, **Then** an `ERROR` level log entry is emitted with timestamp, job identifier, and error details.

---

### Edge Cases

- **Exact-millisecond concurrent startup**: If two worker processes start at the exact same moment, database transaction constraints or atomic update semantics must ensure only one process obtains the `processing` lock while the other exits cleanly.
- **Empty telemetry events on target date**: If no telemetry events occurred during the target date (e.g. holiday or quiet period), the process exports an empty/header-only audit CSV, proceeds with the pipeline run, and records normal completion.
- **Subprocess execution failure**: If the downstream pipeline script fails with a non-zero exit code or uncaught error, the orchestrator must catch the subprocess failure, mark the job run as `failed` with the error output, and exit with a non-zero exit code.
- **Malformed target date override**: If an invalid `TARGET_DATE` format is provided (e.g. `2026-13-45` or text), the script must validate the format, log a clear validation error, mark the record as `failed`, and abort prior to processing.
- **Pre-existing CSV with missing completion record**: If `data/raw/telemetry_YYYY-MM-DD.csv` exists but no completed job run exists (e.g., prior interrupted run), the script preserves the existing CSV and proceeds to run the pipeline, updating the status accordingly.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an autonomous CLI entry point (`scripts/nightly_export.py`) that runs as an independent operating system process outside the web application's main thread.
- **FR-002**: System MUST resolve the target date to the preceding calendar day in UTC by default, or accept an optional date override via an environment variable (`TARGET_DATE`) formatted as `YYYY-MM-DD`.
- **FR-003**: System MUST export telemetry event records for the resolved target date to an audit CSV file located in `data/raw/telemetry_YYYY-MM-DD.csv` only if that file does not already exist.
- **FR-004**: System MUST maintain execution tracking in a dedicated `job_runs` data table capturing lifecycle states: `pending`, `processing`, `completed`, and `failed`.
- **FR-005**: System MUST enforce concurrency locking by checking for active `processing` records for the job name before starting work, silently aborting duplicate executions if a lock is detected.
- **FR-006**: System MUST enforce idempotency per target date by checking for a `completed` record for `(job_name, target_date)` before beginning work, skipping execution if already completed.
- **FR-007**: System MUST invoke the downstream analytical telemetry KPI pipeline as an isolated subprocess upon successful export.
- **FR-008**: System MUST guarantee via defensive error handling that any failure transitions the job record status to `failed` with the diagnostic error message, leaving zero records stranded in `processing`.
- **FR-009**: System MUST structure and isolate job runner persistence and business logic inside `services/` while keeping CLI entry points in `scripts/`.
- **FR-010**: System MUST emit structured log events at `INFO` level for regular lifecycle milestones (start, skip, complete) and `ERROR` level for exceptions, including timestamp, job name, and status.
- **FR-011**: System MUST document the cron trigger schedule expression and deployment configuration for production execution.

### Key Entities *(include if feature involves data)*

- **Job Run (`job_runs`)**:
  - `id`: Unique identifier for the job execution.
  - `job_name`: Descriptive identifier of the background process (e.g., `nightly_export`).
  - `target_date`: Calendar date representing the operational cohort being processed.
  - `status`: Lifecycle state (`pending`, `processing`, `completed`, `failed`).
  - `started_at`: Timestamp recording when active processing began.
  - `finished_at`: Timestamp recording when the execution finalized (success or failure).
  - `error_message`: Detailed description of the error if status is `failed`.
  - `created_at`: Record creation timestamp.
  - *Index*: Composite index on `(job_name, target_date)` for high-efficiency idempotency checks.

- **Daily Audit Snapshot**:
  - Point-in-time CSV export file (`data/raw/telemetry_YYYY-MM-DD.csv`) containing archived telemetry event records for compliance, disaster recovery, and operational auditing.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of nightly executions run autonomously via the scheduler without requiring manual CLI triggering or human intervention.
- **SC-002**: 0% duplicate pipeline runs when concurrent instances of the script are initiated simultaneously.
- **SC-003**: 100% of job failures cleanly update their status to `failed` and populate error diagnostics, leaving zero orphaned `processing` records.
- **SC-004**: 0ms added latency to web API endpoints, verified by executing the background process while API endpoints operate concurrently without thread contention.
- **SC-005**: 100% idempotency for re-run executions, verifying that re-triggering a previously completed target date produces zero duplicate files and triggers zero duplicate pipeline runs.
- **SC-006**: 100% audit trail compliance, ensuring every target date processed produces a verified CSV backup in `data/raw/`.

---

## Assumptions

- **Operational Database**: The PostgreSQL/SQLite monorepo database contains the `telemetry_events` table populated with operational events.
- **Pipeline Interface**: The analytical KPI data pipeline is accessible via CLI command execution (e.g. `python -m data.pipelines.telemetry_kpi_daily.run --no-prefect` or equivalent monorepo CLI entry point).
- **Core Pipeline Data Source**: The analytical pipeline continues to query the authoritative database tables directly; the raw CSV snapshot serves strictly as an audit and backup artifact.
- **Separate Lifecycle Context**: The `job_runs` table manages orchestration and scheduler-level background jobs and does not replace or conflate with the domain-level `pipeline_runs` table from the analytics layer.
- **Timezone Standardization**: All scheduling, export cutoffs, and default date calculations operate strictly against UTC calendar boundaries.
- **Execution Scheduler**: Operating system crontab or a dedicated container scheduler is available in the target environment to trigger the script at the designated nightly schedule.
