# Research: Automated Nightly Telemetry Export & Orchestration

**Feature**: `022-nightly-telemetry-export` | **Branch**: `022-nightly-telemetry-export`
**Created**: 2026-10-27

---

## 1. Target Date Resolution & Timezone Standardization

### Context
FR-002 requires the system to resolve the target date to the preceding calendar day in UTC by default, or accept an optional date override via an environment variable (`TARGET_DATE`) formatted as `YYYY-MM-DD`. Additionally, malformed date formats must be caught and rejected before processing.

### Decision
- **Default Resolution**: Use `datetime.now(timezone.utc).date() - timedelta(days=1)`. Format as ISO-8601 calendar date string `YYYY-MM-DD`.
- **Environment & CLI Override**: Support `TARGET_DATE` environment variable with optional CLI `--date` flag fallback. Validate against the strict regex `^\d{4}-\d{2}-\d{2}$` and parse using `datetime.strptime(val, "%Y-%m-%d").date()`.
- **Window Boundaries**: For database querying and pipeline execution, the target date spans from `{target_date}T00:00:00Z` to `{target_date}T23:59:59.999999Z` (or ISO boundary `{target_date}T23:59:59Z`).

### Rationale
- Using explicit UTC guarantees consistency regardless of host machine local timezone (e.g., developer laptops on CET/PST vs cloud containers on UTC).
- Rigid format validation prevents corrupt target date keys in the `job_runs` table and malformed CSV filenames.

### Alternatives Considered
- *Using host local date*: Rejected because local timezone variance causes inconsistencies around midnight, leading to shifted date windows.
- *Accepting arbitrary date formats (e.g., MM/DD/YYYY)*: Rejected to adhere to ISO-8601 standard across the monorepo.

---

## 2. Concurrency Locking & Race Condition Prevention

### Context
FR-005 and SC-002 mandate that if two instances of the nightly job run simultaneously (e.g., overlapping cron schedules or accidental manual execution while a job is running), subsequent instances must detect the active lock, silently abort without unhandled errors, log at `INFO` level, and exit with code 0.

### Decision
- **Database-Backed Lock**: Use the `job_runs` table with a lifecycle state machine (`pending`, `processing`, `completed`, `failed`).
- **Lock Check Query**: Query for any existing `job_runs` record where `job_name == "nightly_export"` and `status == "processing"`.
- **Atomic Transition**:
  - In SQLite and PostgreSQL, execute within a transaction:
    ```sql
    SELECT id FROM job_runs WHERE job_name = 'nightly_export' AND status = 'processing';
    ```
    If an active processing record exists, log `"Concurrent execution detected: active job is currently processing. Skipping this run."` and exit cleanly (status skipped).
  - If no active record exists, immediately insert the new `job_runs` record with `status = 'processing'` and commit.
- **Lock Staleness / Zombie Prevention**: Any unexpected error or unhandled exception must be captured in an outer `try...except` and `finally` block to update the status to `failed` and clear the `processing` state.

### Rationale
- Centralized database locking requires no additional infrastructure (such as Redis or ZooKeeper) and works identically in local development (SQLite `inventory.db`) and production (PostgreSQL/Supabase).
- Silent exit with code 0 prevents alerting systems and crontabs from reporting spurious failures when a job simply skips due to an active run.

### Alternatives Considered
- *OS-level file lock (`fcntl` / `msvcrt`)*: Rejected because file locks do not work across multiple Docker containers or distributed worker instances sharing a centralized database.
- *Redis distributed lock*: Rejected because introducing Redis adds an unnecessary external dependency for a single nightly job.

---

## 3. Per-Day Idempotency & Audit CSV Retention Policy

### Context
FR-003, FR-006, and SC-005 mandate strict idempotency per target date. If `(job_name, target_date)` is already `completed`, the run must skip file export and pipeline execution. If `data/raw/telemetry_YYYY-MM-DD.csv` already exists, it must not be overwritten.

### Decision
- **Idempotency Check**: Query `job_runs` for `job_name == "nightly_export"`, `target_date == target_date`, and `status == "completed"`.
- **Existing CSV Handling**: Check `os.path.exists(csv_path)`:
  - If the file exists, log an informational message and reuse the existing snapshot file.
  - If the file does not exist, query `telemetry_events` for events within the target date window, serialize to CSV via `pandas.to_csv(index=False)` or standard Python `csv.writer`, and save to `data/raw/telemetry_YYYY-MM-DD.csv`.
  - If 0 telemetry events exist for that date, generate a valid CSV containing the standard header row.

### Rationale
- Preserves raw audit snapshots as immutable point-in-time archives for regulatory compliance and disaster recovery.
- Avoids redundant expensive pipeline reprocessing for dates already successfully calculated.

### Alternatives Considered
- *Always overwriting the CSV file*: Rejected because overwriting audit files destroys point-in-time compliance snapshots and creates write contention.
- *Deleting existing CSV on retry*: Rejected for the same reason.

---

## 4. Subprocess Execution & Pipeline Isolation

### Context
FR-001, FR-007, and FR-008 require invoking the downstream analytical telemetry KPI pipeline as an isolated subprocess. The background export must execute outside the web request thread with zero latency impact on API endpoints.

### Decision
- **Subprocess Invocation**: Use `subprocess.run` with `sys.executable`:
  ```python
  cmd = [
      sys.executable,
      "data/pipelines/pipeline.py",
      "--start-date", f"{target_date}T00:00:00Z",
      "--end-date", f"{target_date}T23:59:59Z"
  ]
  result = subprocess.run(cmd, capture_output=True, text=True, check=False)
  ```
- **Error Handling**:
  - If `result.returncode != 0`, parse `result.stderr` (or `result.stdout`), sanitize the message, record status as `failed` in `job_runs`, and raise a domain exception or exit with code 1.
  - Pass the active environment (`os.environ.copy()`) to preserve database and Prefect configurations.

### Rationale
- Subprocess isolation ensures that heavy memory allocation, Prefect engine lifecycle, and Pandas calculations inside the pipeline do not leak memory into long-lived daemon threads or web workers.
- It cleanly honors existing CLI contracts established in feature `020-resilient-business-pipeline` and `021-pipeline-subflows-and-tests`.

### Alternatives Considered
- *Direct Python function import of `executive_performance_pipeline_flow`*: Subprocess was chosen because FR-007 explicitly mandates an isolated subprocess, preventing thread contention and memory contamination.

---

## 5. Persistence Architecture & Service Boundary Isolation

### Context
FR-004 and FR-009 require structuring job runner persistence and business logic inside `services/` while keeping CLI entry points in `scripts/`.
Constitution Principle I strictly isolates scripts, services, and domain data.

### Decision
- **Package Location**: `services/jobs/`
  - `services/jobs/__init__.py`: Package exports.
  - `services/jobs/models.py`: `JobRun` SQLModel entity, table `job_runs`, `JobStatus` string constants / enum, and schema initialization.
  - `services/jobs/runner.py`: `NightlyExportRunner` encapsulating date resolution, lock checking, CSV export, subprocess triggering, and lifecycle updates.
- **CLI Entry Point**: `scripts/nightly_export.py`
  - Parses optional CLI parameters (`--date`, `--force`, `--dry-run`).
  - Instantiates and invokes `NightlyExportRunner`.
  - Exits with standard POSIX return codes: `0` for success or legitimate skip, `1` for execution failure.
- **Database Engine**: Reuses the centralized database engine utility from `data.pipelines.models.get_engine()` (or initializes standard connection), supporting PostgreSQL with SQLite fallback to `services/api/inventory.db`.

### Rationale
- Complies with monorepo directory layout: `scripts/` contains thin CLI wrappers; `services/` contains domain logic and database models.
- Guarantees zero modifications to `services/telemetry/analysis.py` or existing schema of `public.telemetry_events`.

### Alternatives Considered
- *Placing everything inside `scripts/nightly_export.py`*: Rejected because it violates FR-009 and Constitution Principle I requiring domain logic in `services/`.

---

## 6. Defensive Error Handling & Error Sanitization

### Context
Constitution Principle IV and FR-008 require defensive error handling: no raw stack traces or leaked credentials (`password`, `token`, `secret`, `key`), no unhandled exceptions leaving jobs stranded in `processing`.

### Decision
- Implement `sanitize_error_message(exc: Exception | str) -> str`:
  - Scans for sensitive tokens (`password`, `token`, `secret`, `key`, `authorization`, `connection`).
  - Replaces sensitive strings with generic summaries.
  - Truncates diagnostic strings to 500 characters to prevent database bloat.
- Outer lifecycle context manager / `try...finally`:
  - Ensures any unhandled error transitions `status` to `failed`, populates `error_message`, sets `finished_at = now()`, and commits before process termination.

---

## 7. Operational Cron Scheduling & Deployment

### Context
FR-011 requires documenting the cron trigger schedule expression and deployment configuration for production execution.

### Decision
- **Cron Expression**: `0 2 * * *` (02:00 UTC daily).
- **Rationale**: 02:00 UTC allows 2 full hours for all late-arriving events from the preceding UTC calendar day (23:59:59 UTC cutoff) to be ingested and persisted across global warehouses (e.g., US-LAX-01 and ES-ZAZ-01).
- **Deployment Pattern**:
  - Container / Kubernetes CronJob or host crontab:
    ```bash
    0 2 * * * cd /workspace && python scripts/nightly_export.py >> /var/log/trackflow/nightly_export.log 2>&1
    ```
