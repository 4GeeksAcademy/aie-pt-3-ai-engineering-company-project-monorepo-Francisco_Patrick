# Bug Assessment: Celery Redis Connection Lost in Docker Backend Container

- **Slug**: backend-redis-connection-lost
- **Created**: 2026-11-05T15:55:00+01:00
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

The user reported an asynchronous task offloading failure when executing Step 1 of Scenario 1 from `specs/023-queue-async-tasks/quickstart.md`:

```text
# Connection to Redis lost
## Overview
During the quickstart validation scenarios, at launch:
#### Step 1: Submit Heavy Request
curl -i -X POST http://localhost:8000/api/v1/reporting/trigger \
  -H "Content-Type: application/json" \
  -d '{"period_start": "2026-10-01T00:00:00Z", "period_end": "2026-10-31T23:59:59Z"}'

the service returns a error, and try to redo the task without succeed.

## Error Traze
ERROR:celery.backends.redis:Connection to Redis lost: Retry (0/20) now.
ERROR:celery.backends.redis:Connection to Redis lost: Retry (1/20) in 1.00 second.
...
ERROR:celery.backends.redis:Connection to Redis lost: Retry (19/20) in 1.00 second.
CRITICAL:celery.backends.asynchronous:
Retry limit exceeded while trying to reconnect to the Celery result store backend. The Celery application must be restarted.
ERROR:services.reporting.presentation.routes:Unexpected error triggering pipeline: 
Retry limit exceeded while trying to reconnect to the Celery result store backend. The Celery application must be restarted.
```

Subsequent verification in `.specify/bugs/backend-redis-connection-lost/test.md` confirmed that even with `docker-compose.yml` updated to inject `REDIS_URL` and `CELERY_RESULT_BACKEND`, the backend container continued failing with the identical retry trace because runtime application imports forcefully overwrote `os.environ` back to `localhost:6379`.

## Symptom

When sending `POST /api/v1/reporting/trigger` to the FastAPI backend running in Docker (`trackflow-backend`), the service blocks for approximately 20 seconds while Celery repeatedly logs `Connection to Redis lost: Retry (x/20) in 1.00 second.` attempting to reach `redis://localhost:6379/1`. Celery exhausts its 20 retries and returns HTTP 500 (`Unexpected error triggering pipeline: Retry limit exceeded while trying to reconnect to the Celery result store backend.`).

Expected behavior:
The endpoint should respond in `< 200ms` with HTTP `202 Accepted` returning a valid `task_id` and `poll_url`, with the background task successfully enqueued onto `redis://redis:6379/0` and processed asynchronously by `trackflow-worker`.

## Reproduction

1. Start the container stack as instructed in [specs/023-queue-async-tasks/quickstart.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/023-queue-async-tasks/quickstart.md#L9-L18):
   ```bash
   docker compose up -d redis backend worker flower
   ```
2. Trigger the reporting pipeline via curl:
   ```bash
   curl -i -X POST http://localhost:8000/api/v1/reporting/trigger \
     -H "Content-Type: application/json" \
     -d '{"period_start": "2026-10-01T00:00:00Z", "period_end": "2026-10-31T23:59:59Z"}'
   ```
3. Observe `trackflow-backend` container logs:
   - Celery's Redis backend attempts to connect to `localhost:6379/1` instead of `redis:6379/1`.
   - The connection fails and retries 20 times (1-second intervals).
   - In the meantime, the healthcheck `GET /docs` succeeds (`INFO: 127.0.0.1:... - "GET /docs HTTP/1.1" 200 OK`).
   - The endpoint fails with HTTP 500 after retry exhaustion.
4. Verify runtime environment mutation inside container:
   ```bash
   docker exec -it trackflow-backend python -c "import os, infrastructure.persistence.sqlmodel.client; print(os.environ.get('CELERY_RESULT_BACKEND'))"
   ```
   Outputs `redis://localhost:6379/1` despite container startup environment being `redis://redis:6379/1`.

## Suspected Code Paths

- [services/api/infrastructure/persistence/sqlmodel/client.py:16-22](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/infrastructure/persistence/sqlmodel/client.py#L16-L22) — Executes `load_dotenv(dotenv_path=_api_env_path, override=True)` at top-level module import. When imported during application startup, it forcefully overwrites `os.environ["REDIS_URL"]` and `os.environ["CELERY_RESULT_BACKEND"]` with the bare-metal host defaults (`redis://localhost:6379/*`) declared in `services/api/.env`.
- [services/api/main.py:27](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/main.py#L27) — Imports `from infrastructure.persistence.sqlmodel.client import init_db` before any routers or task registries load, immediately triggering the environment clobbering.
- [docker-compose.yml:44-50](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/docker-compose.yml#L44-L50) — Configures `backend` container environment. Although `REDIS_URL=${REDIS_URL:-redis://redis:6379/0}` and `CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND:-redis://redis:6379/1}` are passed to Docker, `override=True` inside Python overwrites them.
- [services/api/.env:18-19](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/.env#L18-L19) — Hardcodes `REDIS_URL=redis://localhost:6379/0` and `CELERY_RESULT_BACKEND=redis://localhost:6379/1` for bare-metal host development.
- [services/api/infrastructure/queue/celery_app.py:16-35](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/infrastructure/queue/celery_app.py#L16-L35) — Reads `REDIS_URL` and `CELERY_RESULT_BACKEND` from `os.getenv()`, which now resolves to `localhost` inside the container.
- [services/reporting/presentation/routes.py:81-104](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/reporting/presentation/routes.py#L81-L104) — Calls `trigger_pipeline_task.delay()`, invoking Celery's result backend reconnection loop to `localhost:6379/1` and raising an HTTP 500 error after 20 retries.

## Root Cause Hypothesis

**Confidence: High**

The failure is caused by a dual-origin environment configuration and dotenv clobbering defect:

1. **Docker Compose Missing Overrides**: In [docker-compose.yml](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/docker-compose.yml), the `backend` service originally omitted explicit `REDIS_URL` and `CELERY_RESULT_BACKEND` definitions, unlike `worker` and `flower`.
2. **Runtime Environment Mutation via `override=True`**: Crucially, [services/api/infrastructure/persistence/sqlmodel/client.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/infrastructure/persistence/sqlmodel/client.py#L20) unconditionally executes `load_dotenv(dotenv_path=_api_env_path, override=True)` on module import. Because `main.py` imports `init_db` from `client.py` during API startup, Python mutates its own process environment at runtime, overwriting any environment variables passed in by Docker Compose with the bare-metal values (`redis://localhost:6379/*`) in `services/api/.env`.

Inside the container bridge network (`trackflow-net`), `localhost` resolves to the `trackflow-backend` container itself, where no Redis server runs. When `POST /api/v1/reporting/trigger` calls `trigger_pipeline_task.delay()`, Celery attempts to contact `redis://localhost:6379/1`, retries 20 times over 20 seconds, and exhausts its retry limit with `CRITICAL:celery.backends.asynchronous: Retry limit exceeded while trying to reconnect to the Celery result store backend`.

## Proposed Remediation

**Preferred**:
1. In [services/api/infrastructure/persistence/sqlmodel/client.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/infrastructure/persistence/sqlmodel/client.py#L20):
   Change `load_dotenv(dotenv_path=_api_env_path, override=True)` to `load_dotenv(dotenv_path=_api_env_path, override=False)`.
   - Adheres to the 12-factor application standard: process environment variables injected by the runtime orchestrator (Docker Compose, Kubernetes, shell) must take precedence over file-based `.env` defaults.
   - For host-based development where environment variables are not preset, `load_dotenv(override=False)` populates the defaults from `services/api/.env` as expected.
   - For Docker containers, variables defined in `docker-compose.yml` (`REDIS_URL=redis://redis:6379/0`, `CELERY_RESULT_BACKEND=redis://redis:6379/1`) remain intact and are not clobbered.
2. In [docker-compose.yml](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/docker-compose.yml#L46-L47):
   Ensure `backend.environment` keeps `REDIS_URL=${REDIS_URL:-redis://redis:6379/0}` and `CELERY_RESULT_BACKEND=${CELERY_RESULT_BACKEND:-redis://redis:6379/1}`.
3. In [services/api/tests/test_celery_docker_config.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/tests/test_celery_docker_config.py):
   Add a regression test verifying that importing `infrastructure.persistence.sqlmodel.client` does not overwrite pre-existing `REDIS_URL` or `CELERY_RESULT_BACKEND` environment variables.

**Alternatives**:
- *Conditionally skip Redis URL keys during `load_dotenv`*: Overcomplicates dotenv loading with custom file parsing. Using the canonical `override=False` behavior is standard across Python applications.
- *Modify `services/api/.env` to point to `redis://redis:6379/*`*: Would break host-based bare-metal local development (Section 1.2 in quickstart.md) where Redis is accessed via `localhost:6379`.

**Files likely to change**:
- `services/api/infrastructure/persistence/sqlmodel/client.py`
- `docker-compose.yml`
- `services/api/tests/test_celery_docker_config.py`

**Tests to add or update**:
- Unit regression test in `services/api/tests/test_celery_docker_config.py` confirming `client.py` respects existing environment variables without overriding.
- Quickstart Scenario 1 end-to-end verification (`POST /api/v1/reporting/trigger`) yielding HTTP 202 in `< 200ms`.

## Risks & Considerations

- **Database Port Fallback Invariance**: In the earlier bug `sqlmodel-db-port-fallback`, `override=True` was used because the root `.env` had stale database parameters (`port=5432`) while `services/api/.env` had `port=6543`. Root `.env` and `services/api/.env` have since been unified with `port=6543` and `aws-1-eu-west-1.pooler.supabase.com`. With `override=False`, both files specify `6543`, preventing any regression to port 5432.
- **Container Restart**: After applying changes to `client.py` (which is bind-mounted via `./services:/app/services`), `trackflow-backend` should be restarted (`docker compose restart backend`) for Python modules to re-evaluate without cached state.

## Open Questions

- None. The root cause and runtime verification steps have been conclusively documented.
