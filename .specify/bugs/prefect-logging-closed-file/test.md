# Bug Verification: Prefect Rich Console Logging Error on Closed Stream During Shutdown

- **Slug**: prefect-logging-closed-file
- **Tested**: 2026-11-01T23:45:00+01:00
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: partial

## Summary

The fix successfully resolved the immediate reproduction case in `tests/pipelines/test_pipeline.py`, eliminating the ephemeral background server spin-up and allowing the test module to pass cleanly in 3.24s with zero logging errors. However, regression testing across flow test suites (`tests/pipelines/test_pipeline_etl.py`, `tests/pipelines/test_pipeline_resilience.py`) reveals that any test executing full Prefect flows still triggers the identical `ValueError: I/O operation on closed file` traceback on pytest session teardown.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `.\services\api\.venv\Scripts\python.exe -m pytest tests/pipelines/test_pipeline.py` | pass | 3 passed in 3.24s, 0 warnings, 0 logging errors (previously 11.73s with 2 warnings and error). |
| Unit test suite | `.\services\api\.venv\Scripts\python.exe -m pytest tests/unit/` | pass | 16 passed in 1.72s with 0 errors. |
| Regression suite (pipeline ETL) | `.\services\api\.venv\Scripts\python.exe -m pytest tests/pipelines/test_pipeline_etl.py` | fail | 4 passed in 19.52s, but unhandled `--- Logging error ---` with `ValueError: I/O operation on closed file` still emitted on shutdown. |
| Regression suite (resilience) | `.\services\api\.venv\Scripts\python.exe -m pytest tests/pipelines/test_pipeline_resilience.py` | fail | 4 passed in 63.36s, but identical `ValueError: I/O operation on closed file` emitted on shutdown. |
| Regression suite (full `tests/`) | `.\services\api\.venv\Scripts\python.exe -m pytest tests/` | fail | All 38 tests passed in 83.22s, but session exit dumped unhandled logging error traceback. |
| Syntax validation | `.\services\api\.venv\Scripts\python.exe -m py_compile tests/pipelines/test_pipeline.py tests/conftest.py` | pass | Valid syntax across modified files. |

## Output Excerpts

### Reproduction Post-Fix (`tests/pipelines/test_pipeline.py`) - CLEAN PASS
```text
collected 3 items

tests\pipelines\test_pipeline.py ...                                     [100%]

============================== 3 passed in 3.24s ==============================
```

### Flow Regression Test Suite (`tests/pipelines/test_pipeline_etl.py`) - PERSISTING SYMPTOM
```text
============================= 4 passed in 19.52s ==============================
--- Logging error ---
Traceback (most recent call last):
  File "...\prefect\logging\handlers.py", line 410, in emit
    self.console.print(message, soft_wrap=True)
  ...
  File "...\rich\console.py", line 2103, in _write_buffer
    write(text)
ValueError: I/O operation on closed file.
Call stack:
  File "...\prefect\server\api\server.py", line 1212, in stop
    subprocess_server_logger.info(
  ...
Message: 'Stopping temporary server on http://127.0.0.1:8664'
```

## Residual Risks

- **Root teardown race condition unresolved**: Bypassing Prefect orchestration using `.fn(...)` resolved the error exclusively for pure unit tests in `test_pipeline.py`. However, any test requiring end-to-end flow execution will spawn an ephemeral Prefect API server whose asynchronous shutdown hook attempts to write to pytest's closed stdout stream.
- **CI/CD log pollution**: While all functional assertions pass with exit code 0, CI/CD pipelines will capture noisy Python logging error traces on exit whenever flow tests run.

## Recommendation

Hold — result is **partial**. While unit test execution for `test_pipeline.py` is verified and fixed, the underlying stream teardown conflict persists whenever Prefect flows are executed under pytest stream capture. Recommend re-assessing or running `/speckit-bug-fix` to implement a global pytest session fixture (e.g. in `tests/conftest.py`) using `prefect_test_harness` or a `pytest_sessionfinish` / `atexit` handler that flushes/detaches Prefect and Rich log handlers or shuts down the temporary server prior to pytest closing stdout.

