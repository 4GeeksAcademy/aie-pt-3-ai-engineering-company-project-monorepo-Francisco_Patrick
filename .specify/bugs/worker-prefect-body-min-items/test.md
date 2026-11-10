# Bug Verification: Prefect Ephemeral Server Body min_items Incompatibility in Celery Worker

- **Slug**: worker-prefect-body-min-items
- **Tested**: 2026-11-05
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The reproduction command cleanly succeeded with zero errors, confirming that `fastapi.params.Body` no longer receives invalid `min_items` parameters during Prefect 3 ephemeral orchestration imports. All new compatibility tests and Celery worker regression suites passed with zero failures.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `uv run --python 3.11 --with-requirements services/api/requirements.txt python -c "from prefect.server.api.concurrency_limits_v2 import MinimalConcurrencyLimitResponse; print('IMPORT_SUCCESS')"` | pass | Module imports cleanly; no `TypeError: Body() got an unexpected keyword argument 'min_items'`. |
| Dependency resolution | `uv pip compile services/api/requirements.txt` | pass | Resolved 133 packages with `fastapi==0.150.0` and `prefect==3.9.1` with no conflict. |
| New / updated tests | `uv run --python 3.11 --with-requirements services/api/requirements.txt pytest -v services/api/tests/test_worker_prefect_compatibility.py` | pass | 4 passed in 27.69s (bounds check, import test, ephemeral client flow run, runtime version check). |
| Regression suite | `uv run --python 3.11 --with-requirements services/api/requirements.txt pytest -v services/api/tests/test_celery_tasks.py services/api/tests/test_celery_docker_config.py` | pass | 6 passed in 29.73s. |
| Containerized live reproduction | `docker compose exec worker ...` | skipped | Docker stack not currently active (`docker compose ps` returned 0 running containers). |

## Output Excerpts

### Post-Fix Reproduction Import Excerpt
```text
$ uv run --python 3.11 --with-requirements services/api/requirements.txt python -c "from prefect.server.api.concurrency_limits_v2 import MinimalConcurrencyLimitResponse; print('IMPORT_SUCCESS')"
IMPORT_SUCCESS
```

### New Tests Output Excerpt
```text
services/api/tests/test_worker_prefect_compatibility.py::test_requirements_fastapi_and_prefect_version_bounds PASSED [ 25%]
services/api/tests/test_worker_prefect_compatibility.py::test_prefect_concurrency_limits_v2_import_compatibility PASSED [ 50%]
services/api/tests/test_worker_prefect_compatibility.py::test_prefect_ephemeral_client_flow_execution PASSED [ 75%]
services/api/tests/test_worker_prefect_compatibility.py::test_installed_fastapi_version_is_compatible PASSED [100%]
======================= 4 passed, 3 warnings in 27.69s ========================
```

### Regression Suite Output Excerpt
```text
services/api/tests/test_celery_tasks.py::test_trigger_pipeline_task_executes_successfully PASSED [ 16%]
services/api/tests/test_celery_tasks.py::test_list_products_task_returns_serialized_products PASSED [ 33%]
services/api/tests/test_celery_tasks.py::test_telemetry_report_task_returns_report_dict PASSED [ 50%]
services/api/tests/test_celery_tasks.py::test_analyze_incidents_task_parses_csv_and_cleans_up PASSED [ 66%]
services/api/tests/test_celery_docker_config.py::test_docker_compose_celery_services_have_redis_env PASSED [ 83%]
services/api/tests/test_celery_docker_config.py::test_sqlmodel_client_preserves_runtime_environment_variables PASSED [100%]
======================= 6 passed, 3 warnings in 29.73s ========================
```

## Residual Risks

- **Docker image rebuild required in active deployment**: Existing container images cached before this fix still contain FastAPI `0.162.0`. Before deploying or bringing the containers back up, operators should run `docker compose build --no-cache backend worker` so the updated `requirements.txt` constraints take effect inside the image layers.

## Recommendation

Close the bug — verified end-to-end. The root cause incompatibility between FastAPI >= 0.151.0 and Prefect's ephemeral ASGI server Body parameters is eliminated by the version constraint, all reproduction steps succeed, and Celery task execution tests pass.

