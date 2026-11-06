# Bug Assessment: Prefect Ephemeral Server Body min_items Incompatibility in Celery Worker

- **Slug**: worker-prefect-body-min-items
- **Created**: 2026-11-05
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

```text
# Worker failed
## Overview
When execuse `$ curl -i -X POST http://localhost:8000/api/v1/reporting/trigger -H "Content-Type: application/json" -d '{"period_start": "2026-10-01T00:00:00Z", "period_end": "2026-10-31T23:59:59Z"}'` the worker fail.

## Error trace
              ^^^^^^^^^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.11/site-packages/prefect/flow_engine.py", line 2108, in run_flow_sync

    with engine.start():

  File "/usr/local/lib/python3.11/contextlib.py", line 137, in __enter__

    return next(self.gen)

           ^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.11/site-packages/prefect/flow_engine.py", line 1304, in start

    with self.initialize_run():

  File "/usr/local/lib/python3.11/contextlib.py", line 137, in __enter__

    return next(self.gen)

           ^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.11/site-packages/prefect/flow_engine.py", line 1188, in initialize_run

    with SyncClientContext.get_or_create() as client_ctx:

  File "/usr/local/lib/python3.11/contextlib.py", line 137, in __enter__

    return next(self.gen)

           ^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.11/site-packages/prefect/context.py", line 341, in get_or_create

    with cls() as ctx:

         ^^^^^

  File "/usr/local/lib/python3.11/site-packages/prefect/context.py", line 309, in __init__

    client=get_client(sync_client=True, httpx_settings=httpx_settings),

           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.11/site-packages/prefect/client/orchestration/__init__.py", line 250, in get_client

    from prefect.server.api.server import SubprocessASGIServer

  File "/usr/local/lib/python3.11/site-packages/prefect/server/api/server.py", line 111, in <module>

    api.concurrency_limits.router,

    ^^^^^^^^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.11/site-packages/prefect/server/api/__init__.py", line 79, in __getattr__

    module = importlib.import_module(module_name)

             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.11/importlib/__init__.py", line 126, in import_module

    return _bootstrap._gcd_import(name[level:], package, level)

           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.11/site-packages/prefect/server/api/concurrency_limits.py", line 22, in <module>

    from prefect.server.api.concurrency_limits_v2 import MinimalConcurrencyLimitResponse

  File "/usr/local/lib/python3.11/site-packages/prefect/server/api/concurrency_limits_v2.py", line 305, in <module>

    names: List[str] = Body(..., min_items=1),

                       ^^^^^^^^^^^^^^^^^^^^^^

TypeError: Body() got an unexpected keyword argument 'min_items'
```

## Symptom

When executing `POST /api/v1/reporting/trigger`, the API service enqueues the Celery task `reporting.trigger_pipeline` and immediately returns HTTP 202 Accepted. However, when the Celery worker process consumes and executes the task, it fails immediately with `TypeError: Body() got an unexpected keyword argument 'min_items'` during Prefect flow engine initialization, crashing task execution without producing any pipeline results.

## Reproduction

1. Start the backend stack using `docker compose up -d backend worker redis`.
2. Inspect the worker container's installed packages: `fastapi==0.162.0` and `prefect==3.8.8`.
3. In the worker container, execute `docker compose exec worker python -c "from prefect.server.api.concurrency_limits_v2 import MinimalConcurrencyLimitResponse"`.
4. Observe the immediate failure:
   `TypeError: Body() got an unexpected keyword argument 'min_items'`.
5. Trigger a pipeline execution via HTTP:
   `curl -i -X POST http://localhost:8000/api/v1/reporting/trigger -H "Content-Type: application/json" -d '{"period_start": "2026-10-01T00:00:00Z", "period_end": "2026-10-31T23:59:59Z"}'`.
6. Inspect the Celery worker logs (`docker compose logs worker`); observe task failure and traceback identical to the reported error.

## Suspected Code Paths

- [services/api/requirements.txt](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/requirements.txt#L1-L15) — Defines unpinned/loosely constrained dependencies (`fastapi>=0.100.0` and `prefect>=3.0.0`). When container builds run with `uv pip install`, `uv` installs the latest FastAPI (`0.162.0`), which removed legacy Pydantic v1 validation arguments (`min_items`) from `fastapi.params.Body`.
- [services/api/infrastructure/queue/tasks.py:51-74](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/infrastructure/queue/tasks.py#L51-L74) — Task handler `reporting.trigger_pipeline` synchronously calls `trigger_pipeline_run(...)`.
- [data/pipelines/reporting_interface.py:124-128](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/data/pipelines/reporting_interface.py#L124-L128) — Invokes `executive_performance_pipeline_flow(...)` decorated with `@flow`.
- `prefect/flow_engine.py:2108` and `prefect/client/orchestration/__init__.py:250` (inside container site-packages) — Prefect flow engine startup initializes an ephemeral ASGI server (`SubprocessASGIServer`) when running without an external Prefect server, importing `prefect.server.api.server`.
- `prefect/server/api/concurrency_limits_v2.py:305` (inside container site-packages) — Calls `names: List[str] = Body(..., min_items=1)`. In FastAPI >= 0.151.0, `min_items` is completely removed from `Body()` in favor of `min_length` or Pydantic annotations, raising `TypeError`.

## Root Cause Hypothesis

FastAPI removed deprecated collection length arguments like `min_items` from `fastapi.params.Body()` in recent releases (`fastapi >= 0.151.0`). In `services/api/requirements.txt`, `fastapi>=0.100.0` and `prefect>=3.0.0` were specified without upper bounds. When building the Docker images using `uv pip install`, `fastapi==0.162.0` was installed alongside `prefect==3.8.8`. When Celery executes `reporting.trigger_pipeline`, the Prefect 3.x flow engine starts an ephemeral orchestration client, which dynamically imports `prefect.server.api.concurrency_limits_v2`. Line 305 of this module attempts to invoke `fastapi.Body(..., min_items=1)`, which causes Python to raise `TypeError: Body() got an unexpected keyword argument 'min_items'`, failing the task immediately. Confidence: high.

## Proposed Remediation

**Preferred**:
1. Update `services/api/requirements.txt` to constrain FastAPI to `<0.151.0` (or upgrade Prefect to `>=3.9.1`, which natively pins `fastapi<0.151,>=0.139.0`):
   ```text
   fastapi>=0.100.0,<0.151.0
   prefect>=3.9.1
   ```
2. Reinstall/rebuild dependencies inside the Docker containers (`docker compose build backend worker` or `uv pip install --system` in running containers) to align FastAPI to a compatible release (`<= 0.150.0`).

**Alternatives** (optional):
- Pin only `fastapi>=0.100.0,<0.151.0` in `requirements.txt` without bumping `prefect`. This guarantees immediate compatibility with `prefect==3.8.8` without risking any behavioral changes in newer Prefect releases.
- Pin only `prefect>=3.9.1`, letting `prefect`'s dependency constraints naturally restrict `fastapi` below `0.151.0`.

**Files likely to change**:
- `services/api/requirements.txt`

**Tests to add or update**:
- Add a compatibility test in `services/api/tests/` that imports `prefect.server.api.concurrency_limits_v2` and verifies `fastapi.params.Body` compatibility.
- Execute an integration test running `trigger_pipeline_task` through Celery worker to verify clean execution and completion without orchestration crashes.

## Risks & Considerations

- **FastAPI Feature Compatibility**: Downgrading FastAPI from `0.162.0` to `<0.151.0` (such as `0.150.0`) must not break any existing FastAPI routes or dependencies. Monorepo routes use standard FastAPI primitives compatible with `>=0.100.0`.
- **Docker Image Layer Cache**: Because Docker layer caching may retain site-packages, containers must be rebuilt or dependencies updated explicitly with `--no-cache` or `uv pip install`.

## Open Questions

- None. The root cause is directly verified via container inspection and upstream dependency constraints.

