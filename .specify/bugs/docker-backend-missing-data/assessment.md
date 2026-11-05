# Bug Assessment: Docker Backend Startup Failure Due to Missing Data Module

- **Slug**: docker-backend-missing-data
- **Created**: 2026-11-02T10:45:00Z
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: critical

## Report (verbatim or summarized)

The user reported the following build and startup error when executing Docker Compose:
```text
# dOCKER COMPOSE BUILD FAILED
## What Happend
The build failed for trackflow-backend: dependency backend failed to start
## Track Error
Traceback (most recent call last):

  File "/usr/local/lib/python3.11/multiprocessing/process.py", line 314, in _bootstrap
    self.run()
  File "/usr/local/lib/python3.11/multiprocessing/process.py", line 108, in run
    self._target(*self._args, **self._kwargs)
  File "/usr/local/lib/python3.11/site-packages/uvicorn/_subprocess.py", line 80, in subprocess_started
    target(sockets=sockets)
  File "/usr/local/lib/python3.11/site-packages/uvicorn/server.py", line 86, in run
    return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/uvicorn/_compat.py", line 30, in asyncio_run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/asyncio/runners.py", line 118, in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/asyncio/base_events.py", line 654, in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/uvicorn/server.py", line 90, in serve
    await self._serve(sockets)
  File "/usr/local/lib/python3.11/site-packages/uvicorn/server.py", line 97, in _serve
    config.load()
  File "/usr/local/lib/python3.11/site-packages/uvicorn/config.py", line 511, in load
    self.loaded_app = self.load_app()
                      ^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/uvicorn/config.py", line 434, in load_app
    return import_from_string(self.app)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/uvicorn/importer.py", line 22, in import_from_string
    raise exc from None
  File "/usr/local/lib/python3.11/site-packages/uvicorn/importer.py", line 19, in import_from_string
    module = importlib.import_module(module_str)
```

Inspection of the running `trackflow-backend` container logs revealed the underlying import failure:
```text
  File "/app/services/api/main.py", line 38, in <module>
    from services.reporting.presentation import routes as reporting  # noqa: E402
  File "/app/services/reporting/presentation/routes.py", line 15, in <module>
    from data.pipelines.reporting_interface import (
ModuleNotFoundError: No module named 'data'
```

## Symptom

Executing `docker compose up --build` fails to initialize the TrackFlow container stack. The `trackflow-backend` service crashes during Uvicorn app initialization with `ModuleNotFoundError: No module named 'data'`. Because the server fails to listen on port 8000, container healthchecks fail continuously, leaving `trackflow-backend` in an `unhealthy` state. Consequently, the dependent `trackflow-ui` service is prevented from starting (`dependency backend failed to start`).

Expected behavior: `trackflow-backend` successfully imports all modules, starts Uvicorn on `0.0.0.0:8000`, passes its healthcheck at `http://127.0.0.1:8000/docs`, and allows `trackflow-ui` to start.

## Reproduction

1. Run Docker Compose build and start:
   ```powershell
   docker compose up --build
   ```
2. The `backend` image builds using [services/Dockerfile](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/Dockerfile).
3. The container `trackflow-backend` starts and invokes:
   ```bash
   uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
   ```
4. Uvicorn dynamically imports `api.main`, executing line 38 of [services/api/main.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/main.py#L38):
   ```python
   from services.reporting.presentation import routes as reporting
   ```
5. [services/reporting/presentation/routes.py:15](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/reporting/presentation/routes.py#L15) executes:
   ```python
   from data.pipelines.reporting_interface import (
   ```
6. The container's filesystem contains `/app/services` and `/app/shared`, but `/app/data` is not present because it was neither copied during image build nor mounted via Docker Compose volumes.
7. Python raises `ModuleNotFoundError: No module named 'data'`.
8. The Uvicorn child process exits, healthchecks time out, and Docker Compose aborts with:
   ```text
   dependency backend failed to start: container trackflow-backend is unhealthy
   ```

## Suspected Code Paths

- [services/Dockerfile:14-17](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/Dockerfile#L14-L17): Copies only `shared/` and `services/` into the Docker build image, omitting `data/`.
- [docker-compose.yml:39-44](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/docker-compose.yml#L39-L44): Mounts `./services:/app/services` and `./shared:/app/shared`, omitting `./data:/app/data`.
- [services/reporting/presentation/routes.py:15-20](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/reporting/presentation/routes.py#L15-L20): Directly imports `data.pipelines.reporting_interface`.
- [services/jobs/models.py:13](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/jobs/models.py#L13) & [services/jobs/runner.py:19](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/jobs/runner.py#L19): Also import `from data.pipelines.models import get_engine`, reinforcing the runtime dependency on the top-level `data` module.
- [data/__init__.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/data/__init__.py): Root `data` directory lacks an `__init__.py` file, relying on implicit namespace packaging.

## Root Cause Hypothesis

**Confidence: High**

When the executive reporting routes and background pipelines were merged into the monorepo, `services/api/main.py` mounted the reporting routes from `services.reporting.presentation.routes`, which directly imports `data.pipelines.reporting_interface`.

On developer host machines, tests and local scripts typically run with the repository root on `sys.path`, so `from data.pipelines...` resolves cleanly. Inside the Docker environment, however:
1. [services/Dockerfile](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/Dockerfile) only copies `shared/` and `services/` into `/app`.
2. [docker-compose.yml](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/docker-compose.yml) only volume-mounts `./services` and `./shared` into `/app`.
3. The directory `/app/data` is entirely absent inside the container.

Because `ENV PYTHONPATH=/app:/app/services` looks in `/app`, the missing `/app/data` directory causes an immediate `ModuleNotFoundError: No module named 'data'` upon importing `api.main`.

## Proposed Remediation

**Preferred**:
1. Update [services/Dockerfile](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/Dockerfile) to copy `data/` into `/app/data/`:
   ```dockerfile
   # Copy shared modules, data pipelines, and services source code
   COPY shared/ ./shared/
   COPY data/ ./data/
   COPY services/ ./services/
   ```
2. Update [docker-compose.yml](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/docker-compose.yml) under `services.backend.volumes` to bind mount `./data` into `/app/data`:
   ```yaml
       volumes:
         - ./services:/app/services
         - ./shared:/app/shared
         - ./data:/app/data
         - /app/services/api/__pycache__
   ```
3. Add an empty [data/__init__.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/data/__init__.py) file so that `data` is recognized as an explicit Python package across all environments.

**Alternatives**:
- *Package `data` as an editable monorepo package*: Create a `pyproject.toml` inside `data/` and install it via `pip install -e /app/data`. *Trade-off*: More robust packaging boundaries, but introduces additional setup complexity.
- *Lazy-load reporting routes or pipeline imports*: Defer the import of `data.pipelines.reporting_interface` until endpoint invocation. *Trade-off*: Violates fail-fast principle; masks the missing dependency until runtime API requests hit `/api/v1/reporting/*`.

**Files likely to change**:
- `services/Dockerfile`
- `docker-compose.yml`
- `data/__init__.py`

**Tests to add or update**:
- Run `docker compose build backend` and `docker compose up -d backend` to verify the backend container successfully initializes and becomes `healthy`.
- Execute a healthcheck verification command (`docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/docs').status)"`) returning status code 200.
- Verify `docker compose up -d ui` starts without dependency failures.

## Risks & Considerations

- **Docker Build Context & Ignore Rules**: Check `.dockerignore` to ensure `data/` is not inadvertently ignored during build.
- **Cache Volumes**: If raw data is ingested or modified inside `/app/data/raw/` at runtime, mounting `./data:/app/data` will persist changes to the host workspace, which is the desired behavior for development.

## Open Questions

- None. The root cause is directly verified by Docker logs and container state.

