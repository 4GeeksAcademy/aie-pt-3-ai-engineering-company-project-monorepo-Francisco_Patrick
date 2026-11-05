# Bug Fix: Spec 022 Nightly Telemetry Export Concurrency Locking, Zombie Recovery, and State Transition

- **Slug**: 022-nightly-telemetry-export-errors
- **Fixed**: 2026-11-01T22:38:00+01:00
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Implemented atomic database concurrency locking via partial unique indexing and conditional SQL updates, added automatic stale lock recovery for zombie processes (such as abrupt `kill -9` terminations), established a phased `pending` to `processing` lifecycle transition, provided the standalone cron schedule specification, and finalized export artifacts with PR metadata.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/jobs/models.py` | modified | Added partial unique index `idx_job_runs_active_unique` on `(job_name)` where `status IN ('pending', 'processing')`, defaulted `status` to `JobStatus.PENDING`, made `started_at` nullable (`Optional[datetime] = None`), and ensured idempotent index creation in `init_jobs_db`. |
| `services/jobs/runner.py` | modified | Added `recover_stale_locks(timeout_seconds=3600)` to clear zombie processes stranded in `processing` or `pending`; updated `check_active_lock()` to query active states; refactored `execute()` to insert records in `pending` and atomically transition to `processing` with conditional SQL `UPDATE ... WHERE NOT EXISTS (...)`. |
| `scripts/nightly_export.py` | modified | Added `--stale-timeout` CLI argument (defaulting to 3600 seconds) and wired it into `runner.execute()`. |
| `scripts/crontab` | added | Standalone crontab definition triggering daily at 02:00 UTC (`0 2 * * *`) with log redirection to `/var/log/trackflow/nightly_export.log`. |
| `data/raw/telemetry_sample.csv` | added | Verified point-in-time CSV export artifact with sample multi-facility fulfillment and CX telemetry records. |
| `logs/nightly_export.log` | added | Sample structured log artifact demonstrating zombie lock recovery, state transition, and clean export cycle completion. |
| `data/pipelines/README.md` | modified | Documented crontab schedule, log rotation guidelines, atomic lock semantics, zombie recovery mechanism, and the `cronjob` PR metadata label. |
| `tests/unit/jobs/test_nightly_export_runner.py` | modified | Added tests for simultaneous execution prevention (`test_atomic_locking_prevents_simultaneous_execution`), zombie lock recovery (`test_stale_lock_recovery_clears_zombie_and_proceeds`), and lifecycle transitions (`test_pending_to_processing_lifecycle_transition`). |
| `tests/integration/jobs/test_nightly_export_e2e.py` | modified | Added end-to-end integration test for zombie lock clearance and successful subsequent execution (`test_e2e_zombie_recovery_and_subsequent_execution`). |

## Diff Highlights (optional)

```python
# services/jobs/models.py - Partial Unique Index for Active Concurrency
Index(
    "idx_job_runs_active_unique",
    "job_name",
    unique=True,
    sqlite_where=text("status IN ('pending', 'processing')"),
    postgresql_where=text("status IN ('pending', 'processing')"),
)
```

```python
# services/jobs/runner.py - Atomic Transition from PENDING to PROCESSING
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
        started_at=start_time,
    )
)
```

## Tests Added or Updated

- `tests/unit/jobs/test_nightly_export_runner.py::test_atomic_locking_prevents_simultaneous_execution` — Verifies concurrent runner threads attempting simultaneous execution result in exactly one successful execution and one clean skip with `concurrency_lock_active`.
- `tests/unit/jobs/test_nightly_export_runner.py::test_stale_lock_recovery_clears_zombie_and_proceeds` — Verifies zombie `processing` records older than timeout are recovered to `failed` and allow the current run to proceed.
- `tests/unit/jobs/test_nightly_export_runner.py::test_pending_to_processing_lifecycle_transition` — Pins down the phased lifecycle transition from `pending` (with `started_at = None`) to `processing` (with `started_at` populated) and `completed`.
- `tests/integration/jobs/test_nightly_export_e2e.py::test_e2e_zombie_recovery_and_subsequent_execution` — End-to-end integration test verifying recovery of stranded zombie locks in SQLite/PostgreSQL environment.

## Local Verification

- Commands run:
  - `& "services/api/.venv/Scripts/python.exe" -m pytest tests/unit/jobs/ tests/integration/jobs/` → 21 passed in 1.97s.
  - `& "services/api/.venv/Scripts/python.exe" -m pytest tests/pipelines/` → 11 passed in 82.57s.
- Manual checks:
  - Validated partial unique index creation across SQLite dialect.
  - Verified `scripts/crontab`, `logs/nightly_export.log`, and `data/raw/telemetry_sample.csv` formatting.

## Deviations from Assessment

None. All proposed remediation points, atomic update semantics, zombie recovery logic, standalone crontab schedule, and sample artifacts were implemented exactly as specified.

## Follow-ups

- Ensure logrotate configuration is deployed on production cron hosts for `/var/log/trackflow/nightly_export.log`.
- Attach `cronjob` label to the pull request in GitHub.

