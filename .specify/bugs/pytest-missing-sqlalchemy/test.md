# Bug Verification: Missing SQLAlchemy Dependency During Root Pytest Execution

- **Slug**: pytest-missing-sqlalchemy
- **Tested**: 2026-11-02T10:20:00+01:00
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The missing SQLAlchemy dependency and execution mismatch were verified to be fully resolved. The new npm test scripts (`npm run test:jobs`, `npm run test:python`), the PowerShell test runner (`scripts/test_runner.ps1`), and the documented `uv run --project services/api` commands all reliably execute the test suite against the canonical virtual environment with zero collection errors and zero regressions.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `npm run test:jobs` | pass | Discovers backend environment via uv and passes all 16 tests in `tests/unit/jobs/test_nightly_export_runner.py` in 1.65s without collection errors. |
| New / updated runner | `powershell -ExecutionPolicy Bypass -File .\scripts\test_runner.ps1 tests/unit/jobs/test_nightly_export_runner.py -v` | pass | Verified fallback and explicit virtualenv runner; all 16 unit tests passed in 1.60s. |
| Direct uv runner | `uv run --project services/api pytest tests/unit/jobs/test_nightly_export_runner.py -v` | pass | Executed documented direct uv command from repo root; all 16 tests passed in 1.67s. |
| Root test suite regression | `npm run test:python` | pass | 38 passed across `tests/unit/jobs/`, `tests/integration/jobs/`, `tests/pipelines/`, and `tests/reporting/`. |
| Backend regression suite | `npm run test:backend` | pass | 219 passed, 3 skipped across the entire `services/api` backend test suite. |
| TypeScript type-check | `npm run typecheck` | pass | `tsc --noEmit` exited with 0 compiler errors. |

## Output Excerpts

### `npm run test:jobs`
```text
> trackflow-programming-foundations@1.0.0 test:jobs
> uv run --project services/api pytest tests/unit/jobs/ -v

============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0 -- J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo
configfile: pytest.ini
plugins: anyio-4.14.2, cov-7.1.0
collecting ... collected 16 items

tests/unit/jobs/test_nightly_export_runner.py::test_export_telemetry_csv_with_events PASSED [  6%]
...
tests/unit/jobs/test_nightly_export_runner.py::test_pending_to_processing_lifecycle_transition PASSED [100%]

============================= 16 passed in 1.65s ==============================
```

### `powershell -ExecutionPolicy Bypass -File .\scripts\test_runner.ps1 tests/unit/jobs/test_nightly_export_runner.py -v`
```text
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
rootdir: J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo
configfile: pytest.ini
plugins: anyio-4.14.2, cov-7.1.0
collected 16 items

tests\unit\jobs\test_nightly_export_runner.py ................           [100%]

============================= 16 passed in 1.60s ==============================
```

### `npm run test:backend`
```text
============================= test session starts =============================
rootdir: J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api
configfile: pyproject.toml
plugins: anyio-4.14.2, cov-7.1.0
collecting ... collected 222 items
...
=========== 219 passed, 3 skipped, 4 warnings in 705.91s (0:11:45) ============
```

### `npm run typecheck`
```text
> trackflow-programming-foundations@1.0.0 typecheck
> tsc --noEmit
[Exit Code 0]
```

## Residual Risks

- Running an unadorned `python -m pytest` from a raw shell that does not have `services/api/.venv` activated will still invoke whichever Python interpreter happens to be first on `PATH` (such as the global Python 3.14 installation lacking project packages). Developers must use the documented workflows (`npm run test:*`, `test_runner.ps1`, `uv run --project services/api`, or `activate.ps1`).

## Recommendation

Close the bug — verified end-to-end. All documented commands and test scripts resolve dependencies cleanly and pass 100% of the unit, integration, backend, and type-check suites.

