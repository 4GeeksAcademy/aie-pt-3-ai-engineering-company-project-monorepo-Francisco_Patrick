# Bug Fix: Prefect Ephemeral Server Body min_items Incompatibility in Celery Worker

- **Slug**: worker-prefect-body-min-items
- **Fixed**: 2026-11-05
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Constrained FastAPI to `<0.151.0` and upgraded Prefect to `>=3.9.1` in `services/api/requirements.txt` to eliminate a fatal `TypeError: Body() got an unexpected keyword argument 'min_items'` raised when the Celery worker initializes Prefect's ephemeral ASGI client orchestration engine during async pipeline executions.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/requirements.txt` | modified | Constrained `fastapi>=0.100.0,<0.151.0` and bumped `prefect>=3.9.1` to enforce compatibility with FastAPI Body parameter specs. |
| `services/api/tests/test_worker_prefect_compatibility.py` | added test | Added regression suite validating FastAPI < 0.151.0 bounds, concurrency limits v2 import safety, and ephemeral flow execution. |

## Diff Highlights (optional)

```diff
--- a/services/api/requirements.txt
+++ b/services/api/requirements.txt
@@ -1,4 +1,4 @@
-fastapi>=0.100.0
+fastapi>=0.100.0,<0.151.0
...
-prefect>=3.0.0
+prefect>=3.9.1
```

## Tests Added or Updated

- `services/api/tests/test_worker_prefect_compatibility.py::test_requirements_fastapi_and_prefect_version_bounds` — Pins down requirements constraint enforcing FastAPI `< 0.151.0` and Prefect `>= 3.9.1`.
- `services/api/tests/test_worker_prefect_compatibility.py::test_prefect_concurrency_limits_v2_import_compatibility` — Confirms `prefect.server.api.concurrency_limits_v2` imports cleanly without `TypeError` on `Body(..., min_items=1)`.
- `services/api/tests/test_worker_prefect_compatibility.py::test_prefect_ephemeral_client_flow_execution` — Verifies running a Prefect `@flow` initializes and stops ephemeral client server without orchestration crashes.
- `services/api/tests/test_worker_prefect_compatibility.py::test_installed_fastapi_version_is_compatible` — Asserts runtime FastAPI version is strictly `< 0.151.0`.

## Local Verification

- Commands run:
  - `uv run --python 3.11 --with-requirements services/api/requirements.txt python -c "from prefect.server.api.concurrency_limits_v2 import MinimalConcurrencyLimitResponse; print('SUCCESS')"` → `SUCCESS` (reproduction previously produced `TypeError: Body() got an unexpected keyword argument 'min_items'`).
  - `uv run --python 3.11 --with-requirements services/api/requirements.txt pytest services/api/tests/test_worker_prefect_compatibility.py` → 4 passed in 31.67s.
  - `uv run --python 3.11 --with-requirements services/api/requirements.txt pytest services/api/tests/test_celery_tasks.py services/api/tests/test_celery_docker_config.py` → 6 passed in 30.50s.
- Manual checks:
  - Verified dependency resolution using `uv pip compile` against updated `requirements.txt`: successfully resolved 133 packages with `fastapi==0.150.0` and `prefect==3.9.1` with zero conflicts.

## Deviations from Assessment

None. The fix strictly implemented the preferred remediation option defined in `assessment.md`.

## Follow-ups

- Rebuild backend and worker Docker containers with `docker compose build backend worker` when Docker engine is running to update container image layers.

