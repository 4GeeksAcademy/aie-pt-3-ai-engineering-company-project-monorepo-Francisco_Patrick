# Bug Verification: Celery Redis Connection Lost in Docker Backend Container

- **Slug**: backend-redis-connection-lost
- **Tested**: 2026-11-05T16:05:45+01:00
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The reproduction step from `assessment.md` no longer reproduces: `POST /api/v1/reporting/trigger` returned HTTP 202 immediately and dispatched the task without connection retries or 500 errors. Runtime container environment variables (`REDIS_URL` and `CELERY_RESULT_BACKEND`) are successfully preserved when importing `infrastructure.persistence.sqlmodel.client`, and all Celery regression suites pass.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `Invoke-RestMethod -Uri "http://localhost:8000/api/v1/reporting/trigger" -Method Post -ContentType "application/json" -Body '{"period_start": "2026-10-01T00:00:00Z", "period_end": "2026-10-31T23:59:59Z"}'` | pass | HTTP 202 Accepted; returns task ID immediately with zero retry warnings or connection errors |
| Container runtime environment verification | `docker exec trackflow-backend python -c "import os, infrastructure.persistence.sqlmodel.client; print('CELERY_RESULT_BACKEND:', os.environ.get('CELERY_RESULT_BACKEND'))"` | pass | Outputs `redis://redis:6379/1`, proving `override=False` prevents clobbering by `services/api/.env` |
| Compose environment resolution | `docker compose config` | pass | Resolves `REDIS_URL: redis://redis:6379/0` and `CELERY_RESULT_BACKEND: redis://redis:6379/1` for `backend` |
| New / updated tests | `services/api/.venv/Scripts/python.exe -m pytest services/api/tests/test_celery_docker_config.py` | pass | 2 passed in 11.35s |
| Regression suite | `services/api/.venv/Scripts/python.exe -m pytest services/api/tests/test_celery_tasks.py services/api/tests/test_tasks_api.py services/api/tests/test_celery_dlq.py` | pass | 14 passed in 76.10s |

## Output Excerpts

### Post-Fix Reproduction Success
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/reporting/trigger" -Method Post -ContentType "application/json" -Body '{"period_start": "2026-10-01T00:00:00Z", "period_end": "2026-10-31T23:59:59Z"}'

task_id    : 06c1060f-7693-40a5-8c0c-d93a6d8c653b
status     : pending
message    : Reporting pipeline execution enqueued.
poll_url   : /api/v1/tasks/06c1060f-7693-40a5-8c0c-d93a6d8c653b
created_at : 2026-11-05T15:05:12.663359Z
```

### Container Runtime Environment Validation
```bash
$ docker exec trackflow-backend python -c "import os, infrastructure.persistence.sqlmodel.client; print('CELERY_RESULT_BACKEND:', os.environ.get('CELERY_RESULT_BACKEND'))"
[INFO] Database connection succeeded (host: aws-1-eu-west-1.pooler.supabase.com, port: 6543).
CELERY_RESULT_BACKEND: redis://redis:6379/1
```

### Backend Container Request Log
```text
INFO:     172.19.0.1:48842 - "POST /api/v1/reporting/trigger HTTP/1.1" 202 Accepted
```

### Pytest Suites
```text
services/api/tests/test_celery_docker_config.py .. [100%]
2 passed, 3 warnings in 11.35s

services/api/tests/test_celery_tasks.py ....       [ 28%]
services/api/tests/test_tasks_api.py .....         [ 64%]
services/api/tests/test_celery_dlq.py .....        [100%]
14 passed, 3 warnings in 76.10s (0:01:16)
```

## Residual Risks

- Bare-metal host development requires Redis running locally on `localhost:6379` unless `REDIS_URL` is exported in the shell, as defined in `services/api/.env`.
- An unrelated runtime warning in Prefect (`TypeError: Body() got an unexpected keyword argument 'min_items'`) was observed during task payload parsing within the worker container; this should be tracked under a separate task/issue if upgrading Prefect/FastAPI dependencies.

## Recommendation

Close the bug — verified end-to-end. Both the Docker Compose service definitions and the SQLModel `load_dotenv(override=False)` fix preserve container environment variables and completely eliminate the Celery Redis connection loss.
