# Bug Fix: Celery Redis Connection Lost in Docker Backend Container

- **Slug**: backend-redis-connection-lost
- **Fixed**: 2026-11-05T16:01:00+01:00
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Configured `load_dotenv` in `services/api/infrastructure/persistence/sqlmodel/client.py` to use `override=False` instead of `override=True`, preserving Docker Compose process environment variables (`REDIS_URL` and `CELERY_RESULT_BACKEND`), and reinforced test coverage to verify non-clobbering behavior and container configuration consistency.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/infrastructure/persistence/sqlmodel/client.py` | modified | Changed `load_dotenv(dotenv_path=_api_env_path, override=True)` to `override=False` so container-injected environment variables are not clobbered by bare-metal defaults |
| `docker-compose.yml` | modified | Configured `REDIS_URL=${REDIS_URL:-redis://redis:6379/0}` and `CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND:-redis://redis:6379/1}` for the `backend` service container |
| `services/api/tests/test_celery_docker_config.py` | added | Added pytest regression tests verifying `docker-compose.yml` service configurations and subprocess verification that importing `client.py` preserves existing environment variables |

## Diff Highlights (optional)

```python
# services/api/infrastructure/persistence/sqlmodel/client.py
 if os.path.exists(_api_env_path):
-    load_dotenv(dotenv_path=_api_env_path, override=True)
+    load_dotenv(dotenv_path=_api_env_path, override=False)
 else:
     load_dotenv()
```

```yaml
# docker-compose.yml
backend:
  environment:
    - PYTHONPATH=/app:/app/services:/app/services/api
+   - REDIS_URL=${REDIS_URL:-redis://redis:6379/0}
+   - CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND:-redis://redis:6379/1}
```

## Tests Added or Updated

- `services/api/tests/test_celery_docker_config.py::test_docker_compose_celery_services_have_redis_env` — Pins down Celery service environment resolution in `docker-compose.yml` to prevent future regressions.
- `services/api/tests/test_celery_docker_config.py::test_sqlmodel_client_preserves_runtime_environment_variables` — Verifies that runtime process environment variables are preserved and not overwritten when `infrastructure.persistence.sqlmodel.client` loads.

## Local Verification

- Commands run:
  - `services/api/.venv/Scripts/python.exe -m pytest services/api/tests/test_celery_docker_config.py` → 2 passed in 11.22s.
  - `services/api/.venv/Scripts/python.exe -m pytest services/api/tests/test_celery_tasks.py services/api/tests/test_tasks_api.py services/api/tests/test_celery_dlq.py` → 14 passed in 74.38s.
- Manual checks:
  - Verified `docker-compose.yml` YAML structure and compose config resolution.
  - Verified `load_dotenv` with `override=False` preserves custom `REDIS_URL` / `CELERY_RESULT_BACKEND` while still loading `.env` defaults when variables are absent.

## Deviations from Assessment

None. The preferred remediation was applied verbatim.

## Follow-ups

- Restart/recreate the backend container (`docker compose restart backend` or `docker compose up -d backend`) when running Docker.
- Run `/speckit-bug-test slug=backend-redis-connection-lost` to perform end-to-end verification.
