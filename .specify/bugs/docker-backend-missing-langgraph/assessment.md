# Bug Assessment: Docker backend container fails with missing langgraph module

- **Slug**: docker-backend-missing-langgraph
- **Created**: 2026-11-21
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

```text
docker compose up --build failed building trackflow-backend with a trace error:
trackflow-backend  | Process SpawnProcess-1:
trackflow-backend  | Traceback (most recent call last):
trackflow-backend  |   File "/usr/local/lib/python3.11/multiprocessing/process.py", line 314, in _bootstrap
trackflow-backend  |     self.run()
trackflow-backend  |   File "/usr/local/lib/python3.11/multiprocessing/process.py", line 108, in run
trackflow-backend  |     self._target(*self._args, **self._kwargs)
trackflow-backend  |   File "/usr/local/lib/python3.11/site-packages/uvicorn/_subprocess.py", line 80, in subprocess_started
trackflow-backend  |     target(sockets=sockets)
trackflow-backend  |   File "/usr/local/lib/python3.11/site-packages/uvicorn/server.py", line 86, in run
trackflow-backend  |     return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())
trackflow-backend  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
trackflow-backend  |   File "/usr/local/lib/python3.11/site-packages/uvicorn/_compat.py", line 30, in asyncio_run   
trackflow-backend  |     return runner.run(main)
trackflow-backend  |            ^^^^^^^^^^^^^^^^
trackflow-backend  |   File "/usr/local/lib/python3.11/asyncio/runners.py", line 118, in run
trackflow-backend  |     return self._loop.run_until_complete(task)
trackflow-backend  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
trackflow-backend  |   File "/usr/local/lib/python3.11/asyncio/base_events.py", line 654, in run_until_complete     
trackflow-backend  |     return future.result()
trackflow-backend  |            ^^^^^^^^^^^^^^^
trackflow-backend  |   File "/usr/local/lib/python3.11/site-packages/uvicorn/server.py", line 90, in serve
trackflow-backend  |     await self._serve(sockets)
trackflow-backend  |   File "/usr/local/lib/python3.11/site-packages/uvicorn/server.py", line 97, in _serve
trackflow-backend  |     config.load()
trackflow-backend  |   File "/usr/local/lib/python3.11/site-packages/uvicorn/config.py", line 511, in load
trackflow-backend  |     self.loaded_app = self.load_app()
trackflow-backend  |                       ^^^^^^^^^^^^^^^
trackflow-backend  |   File "/usr/local/lib/python3.11/site-packages/uvicorn/config.py", line 434, in load_app      
trackflow-backend  |     return import_from_string(self.app)
trackflow-backend  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
trackflow-backend  |   File "/usr/local/lib/python3.11/site-packages/uvicorn/importer.py", line 22, in import_from_string
trackflow-backend  |     raise exc from None
trackflow-backend  |   File "/usr/local/lib/python3.11/site-packages/uvicorn/importer.py", line 19, in import_from_string
trackflow-backend  |     module = importlib.import_module(module_str)
trackflow-backend  |              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
trackflow-backend  |   File "/usr/local/lib/python3.11/importlib/__init__.py", line 126, in import_module
trackflow-backend  |     return _bootstrap._gcd_import(name[level:], package, level)
trackflow-backend  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
trackflow-backend  |   File "<frozen importlib._bootstrap>", line 1204, in _gcd_import
trackflow-backend  |   File "<frozen importlib._bootstrap>", line 1176, in _find_and_load
trackflow-backend  |   File "<frozen importlib._bootstrap>", line 1147, in _find_and_load_unlocked
trackflow-backend  |   File "<frozen importlib._bootstrap>", line 690, in _load_unlocked
trackflow-backend  |   File "<frozen importlib._bootstrap_external>", line 940, in exec_module
trackflow-backend  |   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed
trackflow-backend  |   File "/app/services/api/main.py", line 28, in <module>
trackflow-backend  |     from presentation.api.v1 import (  # noqa: E402
trackflow-backend  |   File "/app/services/api/presentation/api/v1/agent.py", line 25, in <module>
trackflow-backend  |     from presentation.dependencies import (
trackflow-backend  |   File "/app/services/api/presentation/dependencies.py", line 34, in <module>
trackflow-backend  |     from application.services.support_agent_service import SupportAgentService
trackflow-backend  |   File "/app/services/api/application/services/support_agent_service.py", line 17, in <module> 
trackflow-backend  |     from langgraph.checkpoint.base import BaseCheckpointSaver
trackflow-backend  | ModuleNotFoundError: No module named 'langgraph'
```

## Symptom

When launching the stack via `docker compose up --build`, the `trackflow-backend` container crashes during startup with `ModuleNotFoundError: No module named 'langgraph'` while initializing `services/api/application/services/support_agent_service.py`. The container enters a crash loop / unready state, causing dependent healthchecks and services to fail.

## Reproduction

1. Run `docker compose build backend` (or `docker compose up --build`).
2. Start the container or observe the container startup logs for `trackflow-backend`.
3. Notice that `uvicorn api.main:app` fails during module loading at `from langgraph.checkpoint.base import BaseCheckpointSaver` with `ModuleNotFoundError: No module named 'langgraph'`.

## Suspected Code Paths

- `services/Dockerfile:9-12` — Copies `services/api/requirements.txt` into container and executes `uv pip install --system --no-cache -r ./services/requirements.txt`.
- `services/api/requirements.txt:1-23` — Manifest used by Docker build; missing `langgraph`, `langgraph-checkpoint`, `langchain-mcp-adapters`, `fastmcp`, `mcpauth`, `pyjwt`, and other newly introduced packages.
- `services/api/pyproject.toml:36-42` — Project file where `langgraph>=1.2.22`, `langgraph-checkpoint>=4.3.2`, `langchain-mcp-adapters>=0.3.2`, etc. are defined, demonstrating an out-of-sync state between `pyproject.toml` and `requirements.txt`.
- `services/api/application/services/support_agent_service.py:17-19` — The application module attempting to import `langgraph` components upon API startup.

## Root Cause Hypothesis

The backend Docker image build specification (`services/Dockerfile`) installs its Python dependencies exclusively from `services/api/requirements.txt`. When feature 027 (Support Agent LangGraph) and related MCP/auth functionality were implemented, `langgraph`, `langgraph-checkpoint`, `langchain-mcp-adapters`, and related libraries were added to `services/api/pyproject.toml` and locked in `services/api/uv.lock`, but `services/api/requirements.txt` was never updated to include them. Consequently, the Docker image is built without `langgraph`, leading to an immediate `ModuleNotFoundError` when Uvicorn imports `services/api/main.py` -> `presentation.api.v1.agent` -> `SupportAgentService`.

Confidence: high.

## Proposed Remediation

**Preferred**:
Synchronize `services/api/requirements.txt` with `services/api/pyproject.toml` by appending the missing dependencies required by the backend API:
- `langgraph>=1.2.22`
- `langgraph-checkpoint>=4.3.2`
- `langchain-mcp-adapters>=0.3.2`
- `fastmcp>=3.4.11`
- `mcpauth>=0.1.1`
- `pyjwt>=2.15.1`
- `scikit-learn>=1.9.1`
- `scipy>=1.18.1`
- `matplotlib>=3.11.2`
- `burner-redis>=0.1.7`
- `amplitude-analytics>=1.3.0`

**Alternatives**:
- Modify `services/Dockerfile` to install dependencies directly from `services/api/pyproject.toml` via `uv pip install --system -r <(uv pip compile pyproject.toml)` or copy `pyproject.toml` and run `uv pip install --system .`. However, keeping `services/api/requirements.txt` complete preserves existing CI and Docker caching conventions without modifying Dockerfile build context expectations.

**Files likely to change**:
- `services/api/requirements.txt`

**Tests to add or update**:
- Verify importability in container or virtual environment: `python -c "import langgraph; from langgraph.checkpoint.base import BaseCheckpointSaver; from presentation.api.v1 import agent"`
- Re-run `docker compose build backend` to ensure successful dependency resolution and container launch.

## Risks & Considerations

- Dependency versions in `services/api/requirements.txt` should align with `services/api/pyproject.toml` and `uv.lock` to avoid version drift between local uv development environments and the Docker container.
- Transitive dependencies pulled in by `langgraph` must resolve smoothly in the Debian slim / Python 3.11 container environment.

## Open Questions

- None. The root cause is directly identifiable from the stack trace and codebase inspection.
