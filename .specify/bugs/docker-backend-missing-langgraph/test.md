# Bug Verification: Docker backend container fails with missing langgraph module

- **Slug**: docker-backend-missing-langgraph
- **Tested**: 2026-11-21
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: failed

## Summary

While local pytest verification in Python 3.14 passed, the Docker container build check failed. The fix added `scipy>=1.18.1` to `services/api/requirements.txt`, which is incompatible with the Docker container's `python:3.11-slim` base image (`scipy==1.18.1` requires `Python>=3.12`), causing `docker compose build backend` to abort during dependency installation.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `docker compose build backend` | fail | Step 5/9 failed: `scipy==1.18.1` requires `Python>=3.12`, but container base image is `python:3.11-slim` (Python 3.11.18). |
| New / updated tests | `uv run --project services/api pytest services/api/tests/test_docker_backend_requirements.py -v` | pass | 2 passed in 9.10s (tested against host Python 3.14 environment). |
| Regression suite | `uv run --project services/api pytest services/api/tests/test_worker_prefect_compatibility.py` | pass | 4 passed in 29.56s (tested against host Python 3.14 environment). |
| Lint / type-check | `uv run --project services/api python -c "import langgraph; from langgraph.checkpoint.base import BaseCheckpointSaver"` | pass | Imports succeed in host Python environment. |

## Output Excerpts

### Docker Compose Build (`docker compose build backend`)
```text
#12 [5/9] RUN uv pip install --system --no-cache -r ./services/requirements.txt
#12 0.153 Using Python 3.11.18 environment at: /usr/local
#12 1.223 error: No solution found when resolving dependencies
#12 1.223   cause: Because the current Python version (3.11.18) does not satisfy Python>=3.12 and scipy==1.18.1 depends on Python>=3.12, we can conclude that scipy==1.18.1 cannot be used.
#12 1.223          And because only scipy<=1.18.1 is available and you require scipy>=1.18.1, we can conclude that your requirements are unsatisfiable.
#12 ERROR: process "/bin/sh -c uv pip install --system --no-cache -r ./services/requirements.txt" did not complete successfully: exit code: 1
failed to solve: process "/bin/sh -c uv pip install --system --no-cache -r ./services/requirements.txt" did not complete successfully: exit code: 1
```

### New Tests (`test_docker_backend_requirements.py`)
```text
services\api\tests\test_docker_backend_requirements.py::test_requirements_contains_langgraph_and_agent_dependencies PASSED [ 50%]
services\api\tests\test_docker_backend_requirements.py::test_support_agent_service_and_langgraph_imports PASSED [100%]
======================== 2 passed, 2 warnings in 9.10s ========================
```

## Residual Risks

- `services/api/pyproject.toml` requires Python `>=3.14`, while `services/Dockerfile` uses `python:3.11-slim`.
- Installing packages directly mirrored from `pyproject.toml` with strict `>=` bounds (`scipy>=1.18.1`, `pandas>=3.0.6`) can break builds on older Python runtime environments like Python 3.11 unless the Docker base image or the requirement bounds are adjusted.

## Recommendation

Reopen — the container build is broken by the fix. Rerun `/speckit-bug-assess` to account for the Python version mismatch between `services/Dockerfile` (`python:3.11-slim`) and `services/api/pyproject.toml` (`requires-python = ">=3.14"` / `scipy>=1.18.1`). Remediation must either update the Dockerfile base image to a compatible Python version or adjust requirement constraints in `services/api/requirements.txt` for Python 3.11.
