# Bug Assessment: Docker backend image build fails due to Python 3.11 incompatibility with scipy 1.18.1

- **Slug**: docker-backend-python-version-mismatch
- **Created**: 2026-11-21
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

```text
docker compose build backend
...
#12 [5/9] RUN uv pip install --system --no-cache -r ./services/requirements.txt
#12 0.153 Using Python 3.11.18 environment at: /usr/local
#12 1.223 error: No solution found when resolving dependencies
#12 1.223   cause: Because the current Python version (3.11.18) does not satisfy Python>=3.12 and scipy==1.18.1 depends on Python>=3.12, we can conclude that scipy==1.18.1 cannot be used.
#12 1.223          And because only scipy<=1.18.1 is available and you require scipy>=1.18.1, we can conclude that your requirements are unsatisfiable.
#12 ERROR: process "/bin/sh -c uv pip install --system --no-cache -r ./services/requirements.txt" did not complete successfully: exit code: 1
failed to solve: process "/bin/sh -c uv pip install --system --no-cache -r ./services/requirements.txt" did not complete successfully: exit code: 1
```

## Symptom

Running `docker compose build backend` fails during step 5/9 (`RUN uv pip install --system --no-cache -r ./services/requirements.txt`) with an unsatisfiable dependency resolution error. `scipy==1.18.1` requires `Python>=3.12`, but the Dockerfile specifies `FROM python:3.11-slim` (Python 3.11.18). Consequently, the backend container cannot be built or started.

## Reproduction

1. Run `docker compose build backend` (or `docker build -f services/Dockerfile .`).
2. Observe dependency installation failure at `RUN uv pip install --system --no-cache -r ./services/requirements.txt`.
3. Notice that `uv` aborts because `scipy==1.18.1` requires `Python>=3.12` whereas `/usr/local` has Python 3.11.18.

## Suspected Code Paths

- `services/Dockerfile:1` — Specifies base image `FROM python:3.11-slim`, which provides Python 3.11.18.
- `services/api/requirements.txt:29` — Pins `scipy>=1.18.1`, which is incompatible with Python 3.11.
- `services/api/pyproject.toml:9,26` — Declares `requires-python = ">=3.14"` and `scipy>=1.18.1`, demonstrating that project-level dependencies are configured for Python >= 3.12 / 3.14.

## Root Cause Hypothesis

`services/Dockerfile` uses `python:3.11-slim` as its base image. Following recent updates to `services/api/requirements.txt` to synchronize backend dependencies with `services/api/pyproject.toml`, `scipy>=1.18.1` was added. Because `scipy 1.18.1` requires `Python >= 3.12`, `uv` in the Debian slim container cannot resolve a compatible package version under Python 3.11, breaking image compilation.

Confidence: high.

## Proposed Remediation

**Preferred**:
Upgrade the base image in `services/Dockerfile` from `python:3.11-slim` to `python:3.12-slim` (or `python:3.12`). This satisfies `scipy>=1.18.1` (`Python>=3.12`) and brings the container Python runtime closer to the monorepo's modern Python environment (`pyproject.toml` `requires-python = ">=3.14"`).

**Alternatives**:
- If Python 3.11 must be preserved in Docker for specific system library dependencies, relax the constraint in `services/api/requirements.txt` to allow a Python 3.11-compatible version (e.g., `scipy>=1.11.0,<1.18.0` or environment markers `scipy>=1.11.0; python_version < "3.12"`). However, updating the base image to `python:3.12-slim` is cleaner and avoids version fragmentation between local environments and Docker containers.

**Files likely to change**:
- `services/Dockerfile`
- `services/api/tests/test_docker_backend_requirements.py`

**Tests to add or update**:
- Run `docker compose build backend` to verify the Docker image builds successfully.
- Verify container startup or import checks in the resulting container image.

## Risks & Considerations

- Upgrading to `python:3.12-slim` must ensure all other dependencies in `requirements.txt` (such as `psycopg2-binary`, `qdrant-client`, `prefect`, `celery`) install and build without missing C-extension or wheel issues on Debian bookworm.
- `services/api/pyproject.toml` specifies `requires-python = ">=3.14"`; verify whether all runtime modules execute smoothly under Python 3.12.

## Open Questions

- None. The conflict between `python:3.11-slim` and `scipy>=1.18.1` (`Python>=3.12`) is explicit in the build logs.
