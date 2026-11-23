# Bug Verification: Docker backend Python 3.12 upgrade for scipy compatibility

- **Slug**: docker-backend-python-version-mismatch
- **Tested**: 2026-11-21
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The Docker backend build failure was successfully resolved by upgrading the base image to `python:3.12-slim`. The image builds cleanly, all 3 requirements tests pass, and Python 3.12.16 with SciPy 1.18.1 was verified inside the built container without regressions.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `docker compose build backend` | pass | Image built cleanly without dependency resolution conflict |
| Runtime verification | `docker run --rm mr-stegmann-ai-engineering-company-project-monorepo-backend:latest python -c "import sys, scipy; ..."` | pass | Verified Python 3.12.16 and SciPy 1.18.1 runtime imports inside container |
| New / updated tests | `services/api/.venv/Scripts/python.exe -m pytest services/api/tests/test_docker_backend_requirements.py -v` | pass | 3/3 passed including `test_dockerfile_base_image_python_version` |
| Regression suite | `services/api/.venv/Scripts/python.exe -m pytest services/api/tests/test_docker_backend_requirements.py` | pass | No regressions detected across backend docker requirement assertions |

## Output Excerpts

**Docker Build & Runtime Verification**:
```text
Image mr-stegmann-ai-engineering-company-project-monorepo-backend Built
Python: 3.12.16 (main, Nov  5 2026, 07:58:20) [GCC 14.2.0]
SciPy: 1.18.1
```

**Pytest Test Results**:
```text
services\api\tests\test_docker_backend_requirements.py::test_requirements_contains_langgraph_and_agent_dependencies PASSED [ 33%]
services\api\tests\test_docker_backend_requirements.py::test_support_agent_service_and_langgraph_imports PASSED [ 66%]
services\api\tests\test_docker_backend_requirements.py::test_dockerfile_base_image_python_version PASSED [100%]
======================= 3 passed, 2 warnings in 12.30s ========================
```

## Residual Risks

- None identified for container builds. Local development outside Docker running Python < 3.12 must use virtual environments with Python >= 3.12 to satisfy `scipy>=1.18.1`.

## Recommendation

Close the bug — verified end-to-end. The Docker container builds and runs reliably with Python 3.12 and SciPy 1.18.1.
