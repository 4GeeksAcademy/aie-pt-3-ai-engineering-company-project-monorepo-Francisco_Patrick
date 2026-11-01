# Bug Assessment: Spec 022 Nightly Telemetry Export Concurrency Locking, Zombie Recovery, and State Transition Errors

- **Slug**: 022-nightly-telemetry-export-errors
- **Created**: 2026-11-01T22:25:00Z
- **Source**: Pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

The user submitted the following bug report and remediation requirements for Spec `022-nightly-telemetry-export`:

> # Spec `022-nightly-telemetry-export` Errors
> ## Overview
> The standard workflow, idempotency, and handled failures work as expected; however, the locking mechanism is not atomic—two simultaneous instances can execute the pipeline, resulting in two "completed" records. Furthermore, a `kill -9` command leaves behind a "zombie" process in the "processing" state, which blocks subsequent executions. Please make the locking mechanism atomic, implement a recovery process for stale locks, introduce a "pending" to "processing" state transition, add a proper cron schedule, and finalize the PR by including logs, CSV output, and a `cronjob` label.

## Symptom

1. **Non-Atomic Concurrency Race Condition**: When two instances of `NightlyExportRunner.execute()` or `scripts/nightly_export.py` are triggered simultaneously, both execute `check_active_lock()` and see no existing lock prior to either committing. Both instances proceed to insert a `processing` record, export CSV snapshots, execute the downstream KPI pipeline concurrently, and commit two duplicate `completed` records for the same target date in `job_runs`.
2. **Zombie Process Deadlock via `kill -9`**: When an active runner process is terminated abruptly via SIGKILL (`kill -9`, out-of-memory killer, or ungraceful container eviction), Python execution halts immediately without running `finally` blocks or exception handlers. A row remains permanently stranded in `status = 'processing'`. Subsequent invocations detect this active lock indefinitely, aborting execution forever and causing a silent pipeline deadlock.
3. **Missing `pending` State Lifecycle**: Although `JobStatus.PENDING` is declared in `services/jobs/models.py`, `NightlyExportRunner` bypasses it during active runs, creating records directly in `status = 'processing'`. There is no staged transition from `pending` to `processing` to mediate lock acquisition.
4. **Missing Scheduler Configuration & PR Deliverables**: The repository lacks an executable standalone cron specification file, and the pull request requires captured run logs, sample CSV export artifacts, and the `cronjob` PR label.

## Reproduction

1. **Simultaneous Execution Race Condition**:
   - In a Python script or parallel test harness, spin up two concurrent threads/processes executing `NightlyExportRunner().execute(target_date_override="2026-10-24")` at the exact same millisecond.
   - Inspect the `job_runs` table: both workers find `check_active_lock() == None`, both insert records with `status = 'processing'`, both trigger the downstream pipeline subprocess, and both commit `status = 'completed'`, resulting in two completed runs for the identical target date.
2. **Zombie Lock Deadlock (`kill -9`)**:
   - Launch `python scripts/nightly_export.py --date 2026-10-24`.
   - While the pipeline subprocess is running, send `kill -9 <PID>` to the parent Python process.
   - Inspect the `job_runs` table: the record remains with `status = 'processing'` and `finished_at IS NULL`.
   - Re-run `python scripts/nightly_export.py --date 2026-10-24`.
   - Observe the output: `Active job 'nightly_export' currently processing... Skipping duplicate execution.` The runner aborts with a skip, leaving the pipeline frozen indefinitely.
3. **Direct Creation in Processing Status**:
   - Inspect `services/jobs/runner.py:320-330`:
     ```python
     job_run = JobRun(
         job_name=self.job_name,
         target_date=target_date,
         status=JobStatus.PROCESSING.value,
         started_at=start_time,
     )
     ```
   - Notice the record is immediately inserted with `PROCESSING`, bypassing `PENDING`.

## Suspected Code Paths

- `services/jobs/runner.py:121-134` (`check_active_lock`): Performs a read query without locking or transaction atomicity, introducing a Time-of-Check to Time-of-Use (TOCTOU) vulnerability against `execute()`.
- `services/jobs/runner.py:276-291` & `320-330` (`execute`): Lock verification and record creation occur across detached database sessions without a mutual exclusion lock or database constraint.
- `services/jobs/runner.py:121-134`: Does not evaluate lock age or staleness against a timeout threshold; any `processing` record (regardless of how old) permanently blocks new executions.
- `services/jobs/models.py:39-95` (`JobRun`):
  - Model defaults to `status = JobStatus.PROCESSING.value` and enforces `started_at` as non-nullable, preventing creation in `pending` status prior to lock acquisition.
  - Lacks a database-level unique constraint or partial unique index on `(job_name)` for active states (`pending`, `processing`).
- `scripts/nightly_export.py:74-98`: CLI runner handles only standard exit paths and does not invoke stale lock recovery or surface pending-to-processing transitions.
- Deployment / Cron: No standalone `crontab` file or scheduler configuration exists in the codebase root or `scripts/`.

## Root Cause Hypothesis

The duplicate executions occur because `check_active_lock()` and the subsequent insertion of the `JobRun` record are non-atomic: between the read check and the database insert, another concurrent process can perform the exact same read check, determine that no lock exists, and insert its own record. Concurrently, `kill -9` deadlocks occur because `NightlyExportRunner` relies entirely on application-level `try...finally` / `except Exception` blocks to clear `processing` locks; when the operating system abruptly kills the process, no recovery logic exists to evaluate timestamps and clear abandoned zombie locks. Confidence: **High**.

## Proposed Remediation

**Preferred**:
1. **Atomic Locking & State Transition (`pending` -> `processing`)**:
   - Update `JobRun` in `services/jobs/models.py`:
     - Allow `started_at` to be nullable (`Optional[datetime] = None`), set default `status = JobStatus.PENDING.value`.
     - Add a partial unique index on `(job_name)` where `status IN ('pending', 'processing')` (supported in both SQLite 3.8+ and PostgreSQL) or implement atomic conditional update semantics:
   - In `services/jobs/runner.py`:
     - Create an initial `JobRun` record in `status = JobStatus.PENDING.value`.
     - Atomically transition the record to `JobStatus.PROCESSING.value` within a database transaction using an atomic SQL condition:
       ```python
       # Update status from PENDING to PROCESSING only if no other active processing job exists
       stmt = (
           update(JobRun)
           .where(JobRun.id == run_id)
           .where(JobRun.status == JobStatus.PENDING.value)
           .where(
               ~exists().where(
                   JobRun.job_name == self.job_name,
                   JobRun.status == JobStatus.PROCESSING.value,
                   JobRun.id != run_id,
               )
           )
           .values(
               status=JobStatus.PROCESSING.value,
               started_at=datetime.now(timezone.utc),
           )
       )
       ```
     - If the atomic update modifies 0 rows (or raises `IntegrityError` from the partial unique index), another process won the race: cleanly remove or mark the pending record as skipped, log at `INFO` level, and exit cleanly with code `0`.
2. **Stale Lock Recovery (Zombie Process Remediation)**:
   - Implement `recover_stale_locks(timeout_seconds: int = 3600) -> int` in `NightlyExportRunner`:
     - Before checking active locks, scan for `JobRun` records where `job_name == self.job_name`, `status == JobStatus.PROCESSING.value`, and `started_at <= now - timeout_seconds` (or stranded `pending` records older than 5 minutes).
     - Transition identified zombie records to `status = JobStatus.FAILED.value`, `finished_at = now`, and `error_message = "Stale lock recovered: execution timed out or process was killed abruptly (zombie lock)"`.
     - Log a warning/informational notice with the number of recovered stale locks.
3. **Standalone Cron Schedule Definition**:
   - Add a standard crontab file (`scripts/crontab` or `crontab`) containing:
     ```text
     0 2 * * * cd /workspace && python scripts/nightly_export.py >> /var/log/trackflow/nightly_export.log 2>&1
     ```
   - Document the cron trigger, schedule syntax (`0 2 * * *`), and log rotation in `data/pipelines/README.md`.
4. **PR Artifacts & Metadata**:
   - Create sample execution log output (`logs/nightly_export.log`) demonstrating successful lifecycle execution and zombie recovery.
   - Include sample CSV export output in `data/raw/telemetry_sample.csv`.
   - Include the `cronjob` label in PR metadata / documentation.

**Alternatives**:
- *File-based OS Lock (`fcntl` / `msvcrt`)*: Lock a physical file on the filesystem. Rejected due to platform-specific system calls (Linux vs. Windows incompatibility) and inability to coordinate across multi-container Docker deployments.
- *PostgreSQL Advisory Locks (`pg_try_advisory_lock`)*: Rejected because the test suite and local environment run on SQLite, which does not support PostgreSQL advisory lock primitives. The database-level conditional update and partial unique index are fully cross-compatible.

**Files likely to change**:
- `services/jobs/models.py`
- `services/jobs/runner.py`
- `scripts/nightly_export.py`
- `data/pipelines/README.md`
- `tests/unit/jobs/test_nightly_export_runner.py`
- `tests/integration/jobs/test_nightly_export_e2e.py`
- `scripts/crontab` (new)
- `data/raw/telemetry_sample.csv` (sample artifact)
- `logs/nightly_export.log` (sample artifact)

**Tests to add or update**:
- `test_atomic_locking_prevents_simultaneous_execution`: Simulate concurrent execution of two runner instances attempting to acquire the lock at the exact same moment; verify that exactly one enters `processing` and finishes, while the second cleanly skips with code `0`.
- `test_stale_lock_recovery_clears_zombie_and_proceeds`: Pre-seed a zombie `processing` record with `started_at` older than the stale timeout threshold; verify that the runner detects the zombie, marks it `failed`, acquires the lock, and completes successfully.
- `test_pending_to_processing_lifecycle_transition`: Verify that a job record is initially persisted in `JobStatus.PENDING`, transitions to `JobStatus.PROCESSING` upon lock acquisition with `started_at` populated, and transitions to `JobStatus.COMPLETED` upon conclusion.

## Risks & Considerations

- **Dialect Portability**: SQLite and PostgreSQL both support partial unique indexes (`CREATE UNIQUE INDEX ... WHERE status IN ('pending', 'processing')`) and conditional `UPDATE ... WHERE NOT EXISTS`. The atomic SQL implementation must be validated against both SQLite and PostgreSQL.
- **Stale Timeout Tuning**: The stale timeout threshold must be safely higher than the maximum expected pipeline run duration (e.g. 60 minutes) to prevent prematurely aborting legitimate long-running batch exports during peak load.

## Open Questions

- None. All functional requirements, state transitions, locking mechanics, and recovery semantics are well-defined.

