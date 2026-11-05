# Bug Fix: Missing SQLAlchemy Dependency During Root Pytest Execution

- **Slug**: pytest-missing-sqlalchemy
- **Fixed**: 2026-11-02T10:05:00Z
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Resolved the environment execution mismatch where root-level pytest invocation failed with `ModuleNotFoundError: No module named 'sqlalchemy'` by adding monorepo test scripts to `package.json`, creating a PowerShell test runner (`scripts/test_runner.ps1`), and documenting proper execution paths in `TESTING.md`.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `package.json` | modified | Added `test:jobs`, `test:backend`, and `test:python` npm scripts delegating to `uv run --project services/api pytest`. |
| `scripts/test_runner.ps1` | added | Convenience PowerShell runner executing pytest against the canonical virtual environment (`services/api/.venv`) via `uv` or directly. |
| `TESTING.md` | modified | Documented monorepo root & job runner testing workflows, covering `npm run`, `uv run --project`, `test_runner.ps1`, and virtual environment activation. |

## Diff Highlights (optional)

```json
// package.json
   "scripts": {
     "build": "tsc -p tsconfig.json",
-    "typecheck": "tsc --noEmit"
+    "typecheck": "tsc --noEmit",
+    "test:jobs": "uv run --project services/api pytest tests/unit/jobs/ -v",
+    "test:backend": "uv run --project services/api pytest services/api/tests/ -v",
+    "test:python": "uv run --project services/api pytest tests/ -v"
   },
```

```markdown
<!-- TESTING.md -->
### 1.2 Monorepo Root & Job Runner Tests (`pytest`)

Root-level tests located in `tests/` (such as `tests/unit/jobs/test_nightly_export_runner.py` or `tests/integration/jobs/`) require backend dependencies (`sqlalchemy`, `sqlmodel`, `prefect`, `pandas`). Because dependencies are installed within `services/api/.venv`, running `python -m pytest` from a root shell without activating the virtual environment will fail with `ModuleNotFoundError: No module named 'sqlalchemy'`.

To run tests from the monorepo root:
...
```

## Tests Added or Updated

- `tests/unit/jobs/test_nightly_export_runner.py` (all 16 tests) — verified to pass cleanly when invoked from the repository root via `npm run test:jobs`, `uv run --project services/api pytest tests/unit/jobs/test_nightly_export_runner.py -v`, and `.\scripts\test_runner.ps1 tests/unit/jobs/test_nightly_export_runner.py -v`.

## Local Verification

- Commands run:
  - `npm run test:jobs` → 16 passed in 1.81s (exit code 0).
  - `powershell -ExecutionPolicy Bypass -File .\scripts\test_runner.ps1 tests/unit/jobs/test_nightly_export_runner.py -v` → 16 passed in 1.86s (exit code 0).
  - `uv run --project services/api pytest tests/unit/jobs/test_nightly_export_runner.py -v` → 16 passed in 1.72s (exit code 0).
  - `npm run typecheck` → 0 TypeScript compiler errors (exit code 0).
- Manual checks:
  - Verified `scripts/test_runner.ps1` properly falls back to `services/api/.venv/Scripts/python.exe` if `uv` is unavailable.
  - Confirmed documentation links and options in `TESTING.md`.

## Deviations from Assessment

None. The preferred remediation plan from `assessment.md` was applied cleanly.

## Follow-ups

- Consider adding a root `pyproject.toml` or `uv` workspace definition if additional Python subprojects are added to the monorepo in the future.

