# Bug Fix: Prefect Rich Console Logging Error on Closed Stream During Shutdown

- **Slug**: prefect-logging-closed-file
- **Fixed**: 2026-11-01T23:17:00+01:00
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Updated pipeline unit tests to invoke `transform_executive_kpis.fn(...)` directly instead of triggering Prefect orchestration, and added test harness configurations in `pytest.ini` and `tests/conftest.py` to suppress missing-flow API logging warnings. This eliminates background ephemeral server spin-up and teardown race conditions that caused `ValueError: I/O operation on closed file`.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `tests/pipelines/test_pipeline.py` | modified | Switched direct task invocation to `.fn(...)` on lines 182 and 229 |
| `pytest.ini` | modified | Added `filterwarnings` rule ignoring `Logger 'prefect.task_runs'` API warnings |
| `tests/conftest.py` | added | Set `PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW=ignore` in test environments |

## Diff Highlights (optional)

```python
# tests/pipelines/test_pipeline.py
-    snapshots = transform_executive_kpis(
+    snapshots = transform_executive_kpis.fn(
         raw_data=empty_unstructured_dict,
         period_start=datetime(2026, 10, 12, tzinfo=timezone.utc),
         period_end=datetime(2026, 10, 18, tzinfo=timezone.utc),
     )
```

```ini
# pytest.ini
 filterwarnings =
+    ignore:Logger 'prefect.task_runs' attempted to send logs to the API:UserWarning
```

```python
# tests/conftest.py
+import os
+os.environ.setdefault("PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW", "ignore")
```

## Tests Added or Updated

- `tests/pipelines/test_pipeline.py::test_transformation_malformed_and_missing_payloads` — Verifies pure in-memory transformation handling of malformed and empty datasets without orchestrating Prefect engine or spawning ephemeral servers.
- `tests/pipelines/test_pipeline.py::test_transformation_exact_mathematical_precision` — Verifies mathematical calculations against ground truth formulas in pure memory isolation.

## Local Verification

- Commands run:
  - `.\services\api\.venv\Scripts\python.exe -m pytest tests/pipelines/test_pipeline.py` → 3 passed in 3.51s, 0 warnings, 0 logging errors, exit code 0 (previously 11.73s with 2 warnings and `ValueError: I/O operation on closed file`).
  - `.\services\api\.venv\Scripts\python.exe -m pytest tests/unit/` → 16 passed in 1.71s, exit code 0.
- Manual checks: Verified that pytest terminal output terminates cleanly without unhandled logging stack traces or file stream exceptions.

## Deviations from Assessment

None. The remediation directly implemented the preferred solution documented in the assessment.

## Follow-ups

- Ensure future test suites that test Prefect tasks or flows use `.fn` for pure logic tests or Prefect's `prefect_test_harness` fixture for full flow orchestration tests.

