# Bug Assessment: Missing SQLAlchemy Dependency During Root Pytest Execution

- **Slug**: pytest-missing-sqlalchemy
- **Created**: 2026-11-02T08:55:00Z
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: medium

## Report (verbatim or summarized)

The user ran the following command from the repository root:
```powershell
PS J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo> python -m pytest tests/unit/jobs/test_nightly_export_runner.py -v
======================================================================= test session starts ========================================================================
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\pjste\AppData\Local\Python\pythoncore-3.14-64\python.exe
cachedir: .pytest_cache
rootdir: J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo
configfile: pytest.ini
plugins: anyio-4.14.2
collected 0 items / 1 error

============================================================================== ERRORS ==============================================================================
__________________________________________________ ERROR collecting tests/unit/jobs/test_nightly_export_runner.py __________________________________________________ 
ImportError while importing test module 'J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\tests\unit\jobs\test_nightly_export_runner.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
tests\unit\jobs\test_nightly_export_runner.py:10: in <module>
    from sqlalchemy import create_engine
E   ModuleNotFoundError: No module named 'sqlalchemy'
===================================================================== short test summary info ====================================================================== 
ERROR tests/unit/jobs/test_nightly_export_runner.py
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! 
========================================================================= 1 error in 0.23s =========================================================================
```

## Symptom

Executing `python -m pytest tests/unit/jobs/test_nightly_export_runner.py -v` from the monorepo root fails during test module collection with `ModuleNotFoundError: No module named 'sqlalchemy'` at line 10 in [tests/unit/jobs/test_nightly_export_runner.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/tests/unit/jobs/test_nightly_export_runner.py#L10).

Expected behavior: Pytest discovers test fixtures and runs all 16 test cases successfully without collection or missing module errors.

## Reproduction

1. Open a terminal session at the monorepo root without activating the backend virtual environment.
2. Execute:
   ```powershell
   python -m pytest tests/unit/jobs/test_nightly_export_runner.py -v
   ```
3. Pytest executes using the system/global Python interpreter (`C:\Users\pjste\AppData\Local\Python\pythoncore-3.14-64\python.exe`).
4. During test collection of [tests/unit/jobs/test_nightly_export_runner.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/tests/unit/jobs/test_nightly_export_runner.py#L10), Python attempts `from sqlalchemy import create_engine`.
5. Pytest halts with `ModuleNotFoundError: No module named 'sqlalchemy'`.

## Suspected Code Paths

- [tests/unit/jobs/test_nightly_export_runner.py:10-11](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/tests/unit/jobs/test_nightly_export_runner.py#L10-L11): Imports `from sqlalchemy import create_engine` and `from sqlmodel import Session, select`, requiring `sqlalchemy` and `sqlmodel` to be present in the active Python environment.
- [pytest.ini:1-6](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/pytest.ini#L1-L6): Configures `testpaths = tests` and `pythonpath = .` at the monorepo root, encouraging execution of pytest from root without specifying or binding the active virtual environment.
- [services/api/requirements.txt:10-11](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/requirements.txt#L10-L11): Declares `sqlmodel>=0.0.22` and `sqlalchemy>=2.0.0`, but this file is located inside `services/api/` rather than the repository root.
- [TESTING.md:13-25](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/TESTING.md#L13-L25): Instructs users to change directory to `services/api` and run `uv run pytest`, but does not document running root-level `tests/unit/jobs/` tests or activating `.venv` when executing pytest directly from root.

## Root Cause Hypothesis

**Confidence: High**

The root cause is an environment resolution mismatch between the monorepo's root-level test layout and the isolated virtual environment in `services/api`:
1. The test file [tests/unit/jobs/test_nightly_export_runner.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/tests/unit/jobs/test_nightly_export_runner.py) resides under the top-level `tests/` directory, and [pytest.ini](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/pytest.ini) is located at the monorepo root.
2. The project's Python dependencies (`sqlalchemy`, `sqlmodel`, `prefect`, `pandas`, `pydantic`, etc.) are installed only within `services/api/.venv` (or managed via `uv` inside `services/api`).
3. Running `python -m pytest` from root without activating `services/api/.venv` causes Windows PowerShell to resolve `python` to the global interpreter (`C:\Users\pjste\AppData\Local\Python\pythoncore-3.14-64\python.exe`), where `sqlalchemy` is not installed.
4. When executed with the virtual environment interpreter (`.\services\api\.venv\Scripts\python.exe -m pytest tests/unit/jobs/test_nightly_export_runner.py -v`) or via `cd services/api; uv run pytest ../../tests/unit/jobs/test_nightly_export_runner.py -v`, all 16 tests pass without error.

## Proposed Remediation

**Preferred**:
1. Add a root-level test runner npm/PowerShell script or Makefile/just recipe (e.g. `npm run test:jobs` or `npm run test:backend` or a convenience script `scripts/test_runner.ps1`) that invokes pytest using `services/api/.venv/Scripts/python.exe` or `uv --directory services/api run pytest`.
2. Update [TESTING.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/TESTING.md) to document how to execute root-level tests in `tests/unit/jobs/`:
   - Either by activating the virtualenv (`.\services\api\.venv\Scripts\activate.ps1`),
   - Or by targeting the virtualenv binary directly (`.\services\api\.venv\Scripts\python.exe -m pytest tests/unit/jobs/test_nightly_export_runner.py -v`),
   - Or by running through `uv`: `uv --directory services/api run pytest ../../tests/unit/jobs/test_nightly_export_runner.py -v`.
3. Provide a root-level `pyproject.toml` or root `requirements.txt` / uv workspace configuration so that running tools from monorepo root resolves the dependencies cleanly.

**Alternatives**:
- *Symlink / forward root requirements*: Create a root `requirements.txt` linking to or including `services/api/requirements.txt` and provide a root `.venv`.
- *Documentation only*: Keep existing project structure unchanged and document required activation in [TESTING.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/TESTING.md) and [README.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/README.md).

**Files likely to change**:
- [TESTING.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/TESTING.md)
- [package.json](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/package.json) (optional test script entry)
- Root `pyproject.toml` or workspace setup (optional)

**Tests to add or update**:
- Verify all 16 tests in [tests/unit/jobs/test_nightly_export_runner.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/tests/unit/jobs/test_nightly_export_runner.py) pass when executed through the documented command.

## Risks & Considerations

- **Virtual Environment Drift**: If developers create independent virtual environments at the root and inside `services/api`, package versions might diverge. Using `services/api/.venv` as the canonical virtual environment or configuring `uv` workspace root prevents this divergence.
- **Cross-platform Compatibility**: Command paths (`services/api/.venv/Scripts/python.exe` on Windows vs `services/api/.venv/bin/python` on Linux/macOS) must be handled gracefully in scripts or documentation.

## Open Questions

- Does the team want a single root `pyproject.toml` (uv workspace) encompassing both `services/api` and root `tests/`, or should developers always invoke tests through `uv --directory services/api run pytest`?

