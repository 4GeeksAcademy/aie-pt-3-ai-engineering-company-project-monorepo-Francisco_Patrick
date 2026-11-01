# Bug Verification: Spec 022 Nightly Telemetry Export Concurrency Locking, Zombie Recovery, and State Transition

- **Slug**: 022-nightly-telemetry-export-errors
- **Tested**: 2026-11-01T22:40:00+01:00
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The atomic concurrency locking, zombie process stale lock recovery, and phased `pending` -> `processing` -> `completed` state transitions were exercised and validated. The race condition and deadlock symptoms no longer reproduce, all targeted and regression tests passed with zero failures, and auxiliary artifacts (crontab, logs, CSV sample) were validated.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix): Concurrent Execution Race Condition | `& "services/api/.venv/Scripts/python.exe" -m pytest tests/unit/jobs/test_nightly_export_runner.py -k "test_atomic_locking_prevents_simultaneous_execution"` | pass | Barrier-synchronized parallel threads attempt lock acquisition; exactly 1 acquires lock and finishes, the other cleanly skips. |
| Reproduction (post-fix): Zombie Lock Deadlock (`kill -9`) | `& "services/api/.venv/Scripts/python.exe" -m pytest tests/unit/jobs/test_nightly_export_runner.py -k "test_stale_lock_recovery_clears_zombie_and_proceeds"` | pass | Stranded `processing` record with expired timeout is recovered to `failed`, allowing subsequent run to execute successfully. |
| Reproduction (post-fix): Pending to Processing Lifecycle | `& "services/api/.venv/Scripts/python.exe" -m pytest tests/unit/jobs/test_nightly_export_runner.py -k "test_pending_to_processing_lifecycle_transition"` | pass | Validated that job run records are initially persisted with `status='pending'` (`started_at=None`) before atomic promotion to `processing`. |
| New / updated tests | `& "services/api/.venv/Scripts/python.exe" -m pytest -v tests/unit/jobs/test_nightly_export_runner.py tests/integration/jobs/test_nightly_export_e2e.py` | pass | All 21 unit and end-to-end integration tests passed without errors. |
| Regression suite | `& "services/api/.venv/Scripts/python.exe" -m pytest tests/unit/jobs/ tests/integration/jobs/` | pass | 21 passed in 2.12s across runner, locking, idempotency, backfill, and e2e pipelines. |
| CLI dry-run and argument validation | `& "services/api/.venv/Scripts/python.exe" scripts/nightly_export.py --date 2026-10-24 --dry-run` | pass | CLI cleanly initialized, parsed `--stale-timeout`, resolved target date, and performed lock inspection. |
| Crontab specification and artifacts | Manual inspection of `scripts/crontab`, `logs/nightly_export.log`, and `data/raw/telemetry_sample.csv` | pass | All deliverables exist and conform to specification. |
| Lint / type-check | `& "services/api/.venv/Scripts/python.exe" -m mypy services/jobs/` | not-run | Mypy is not bundled in the local virtual environment. |

## Output Excerpts

**Targeted Bug Verification Tests:**
```text
tests/unit/jobs/test_nightly_export_runner.py::test_atomic_locking_prevents_simultaneous_execution PASSED [ 33%]
tests/unit/jobs/test_nightly_export_runner.py::test_stale_lock_recovery_clears_zombie_and_proceeds PASSED [ 66%]
tests/unit/jobs/test_nightly_export_runner.py::test_pending_to_processing_lifecycle_transition PASSED [100%]
====================== 3 passed, 13 deselected in 0.95s =======================
```

**End-to-End Integration Suite:**
```text
tests/integration/jobs/test_nightly_export_e2e.py::test_us1_end_to_end_export_and_completion PASSED [ 20%]
tests/integration/jobs/test_nightly_export_e2e.py::test_us2_concurrency_locking_prevents_duplicate_run PASSED [ 40%]
tests/integration/jobs/test_nightly_export_e2e.py::test_us3_idempotency_and_historical_backfill PASSED [ 60%]
tests/integration/jobs/test_nightly_export_e2e.py::test_us4_failure_recovery_and_lock_clearance PASSED [ 80%]
tests/integration/jobs/test_nightly_export_e2e.py::test_e2e_zombie_recovery_and_subsequent_execution PASSED [100%]
============================== 5 passed in 1.04s ==============================
```

**Full Unit & Integration Regression Suite:**
```text
collected 21 items
tests\unit\jobs\test_nightly_export_runner.py ................           [ 76%]
tests\integration\jobs\test_nightly_export_e2e.py .....                  [100%]
============================= 21 passed in 2.12s ==============================
```

## Residual Risks

- **Production Clock Skew**: Stale lock recovery evaluates `started_at <= now - timeout_seconds`. If container hosts or database servers experience significant NTP drift exceeding multiple minutes, recovery calculation could trigger marginally earlier or later than intended (mitigated by setting a generous default timeout of 3600 seconds).
- **Long-Running Batch Overruns**: If an exceptionally large data volume requires more than 1 hour to export, operators must configure `--stale-timeout` to exceed the expected maximum runtime to avoid premature zombie reclamation.

## Recommendation

Close the bug — verified end-to-end. The atomic locking mechanism eliminates TOCTOU race conditions, stale locks left by unexpected process terminations (`kill -9`) are cleanly recovered, and the staged `pending` -> `processing` state transition is fully verified.

