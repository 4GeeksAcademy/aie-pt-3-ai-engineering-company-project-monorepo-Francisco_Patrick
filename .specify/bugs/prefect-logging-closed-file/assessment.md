# Bug Assessment: Prefect Rich Console Logging Error on Closed Stream During Shutdown

- **Slug**: prefect-logging-closed-file
- **Created**: 2026-11-01T23:12:00+01:00
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: low

## Report (verbatim or summarized)

```text
# Manual test error
## Track Error
-- Logging error ---
Traceback (most recent call last):
  File "J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\.venv\Lib\site-packages\prefect\logging\handlers.py", line 410, in emit
    self.console.print(message, soft_wrap=True)
    ~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
  File "J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\.venv\Lib\site-packages\rich\console.py", line 1704, in print      
    with self:
         ^^^^
  File "J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\.venv\Lib\site-packages\rich\console.py", line 864, in __exit__    
    self._exit_buffer()
    ~~~~~~~~~~~~~~~~~^^
  File "J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\.venv\Lib\site-packages\rich\console.py", line 820, in _exit_buffer    self._check_buffer()
    ~~~~~~~~~~~~~~~~~~^^
  File "J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\.venv\Lib\site-packages\rich\console.py", line 2055, in _check_buffer
    self._write_buffer()
    ~~~~~~~~~~~~~~~~~~^^
  File "J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\.venv\Lib\site-packages\rich\console.py", line 2103, in _write_buffer
    write(text)
    ~~~~~^^^^^^
ValueError: I/O operation on closed file.
Call stack:
  File "J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\.venv\Lib\site-packages\prefect\server\api\server.py", line 1212, in stop
    subprocess_server_logger.info(
  File "C:\Users\pjste\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\Lib\logging\__init__.py", line 1520, in info
    self._log(INFO, msg, args, **kwargs)
  File "C:\Users\pjste\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\Lib\logging\__init__.py", line 1665, in _log
    self.handle(record)
  File "C:\Users\pjste\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\Lib\logging\__init__.py", line 1681, in handle
    self.callHandlers(record)
  File "C:\Users\pjste\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\Lib\logging\__init__.py", line 1737, in callHandlers
    hdlr.handle(record)
  File "C:\Users\pjste\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\Lib\logging\__init__.py", line 1027, in handle
    self.emit(record)
  File "J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\.venv\Lib\site-packages\prefect\logging\handlers.py", line 416, in emit
    self.handleError(record)
Message: 'Stopping temporary server on http://127.0.0.1:8924'
Arguments: ()
```

## Symptom

When executing Python tests or subprocess flows with stream capture enabled (e.g. `pytest tests/pipelines/test_pipeline.py`), Python dumps an unhandled logging error traceback with `ValueError: I/O operation on closed file`. While tests pass and core logic succeeds, the error pollutes test output and terminal logs during shutdown.

## Reproduction

1. In the repository root, invoke pytest against the data pipeline unit test suite using the virtual environment interpreter:
   ```powershell
   .\services\api\.venv\Scripts\python.exe -m pytest tests/pipelines/test_pipeline.py
   ```
2. Observe that while the 3 unit tests pass (`3 passed, 2 warnings`), Python's logging subsystem emits an unhandled `--- Logging error ---` traceback originating from `rich/console.py:2103` and `prefect/server/api/server.py:1212` with the message `'Stopping temporary server on http://127.0.0.1:...'`.

## Suspected Code Paths

- [tests/pipelines/test_pipeline.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/tests/pipelines/test_pipeline.py#L182-L230): Invokes `transform_executive_kpis(...)` directly through its Prefect `@task` decorator instead of `transform_executive_kpis.fn(...)`. This triggers Prefect 3.x's task orchestration engine and causes an ephemeral background server to start and stop.
- [data/pipelines/pipeline.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/data/pipelines/pipeline.py#L395): Defines `transform_executive_kpis` as a `@task`.
- [pytest.ini](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/pytest.ini#L1-L5): Lacks configuration to suppress ephemeral logging or configure Prefect test settings in unit test execution.
- `prefect/server/api/server.py:1212` and `prefect/logging/handlers.py:410`: Upstream Prefect and Rich handlers attempting to write to `sys.stdout` after pytest's stream capture mechanism has closed the underlying file descriptor.

## Root Cause Hypothesis

When `pytest` executes tests with stream capture enabled, it replaces `sys.stdout` and `sys.stderr` with internal capture buffers, and closes those buffers immediately upon session completion. In `tests/pipelines/test_pipeline.py`, unit tests invoke `@task`-decorated functions directly (`transform_executive_kpis(...)`) rather than unwrapping their inner function (`.fn(...)`). Because no active flow run or external Prefect server is configured, Prefect 3.x spawns a background ephemeral API server and async runner threads. During Python runtime teardown and thread termination after pytest closes the capture buffers, the ephemeral server's `stop()` method attempts to log `'Stopping temporary server...'` using `rich.console.Console`. Rich's buffer flush calls `write()` on the closed stream, raising `ValueError: I/O operation on closed file`, which triggers Python's fallback `logging.Handler.handleError`. Confidence: high.

## Proposed Remediation

**Preferred**:
1. Update `tests/pipelines/test_pipeline.py` to call `transform_executive_kpis.fn(...)` instead of `transform_executive_kpis(...)`. In accordance with Prefect best practices and FR-007 (pure in-memory unit tests with zero database and zero network dependencies), calling `.fn` directly tests the raw business logic without triggering Prefect orchestration, background threads, or ephemeral server spin-up. This also reduces unit test execution time from ~12 seconds to under 1 second.
2. Configure `pytest.ini` and/or a `tests/conftest.py` fixture with `PREFECT_LOGGING_TO_API_WHEN_MISSING_FLOW=ignore` and Prefect test harness settings to suppress unnecessary API logging warnings during pytest test sessions.

**Alternatives**:
- Run pytest with `--capture=no` (`-s`), leaving `sys.stdout` open throughout exit. This masks the issue but pollutes stdout with verbose console noise during test runs.
- Attach an `atexit` or `pytest_sessionfinish` hook that cleans up or detaches Prefect logging handlers before stream teardown.

**Files likely to change**:
- `tests/pipelines/test_pipeline.py`
- `pytest.ini` (or `tests/conftest.py`)

**Tests to add or update**:
- Run `.\services\api\.venv\Scripts\python.exe -m pytest tests/pipelines/test_pipeline.py` and verify all tests pass with exit code 0, test duration is under 1 second, and no `--- Logging error ---` or `ValueError: I/O operation on closed file` appears in output.

## Risks & Considerations

- Calling `.fn` in unit tests bypasses the Prefect task runner hooks; however, transformation tests in `test_pipeline.py` are explicitly designed as pure in-memory calculation tests (FR-006, FR-007, FR-008, FR-009). The main flow in `data/pipelines/pipeline.py` retains the full `@task` and `@flow` orchestration decorators for production pipeline runs.

## Open Questions

- None. Reproduction and root cause are verified on the active codebase.

