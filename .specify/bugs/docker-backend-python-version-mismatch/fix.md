# Bug Fix: Upgrade Docker backend base image to python:3.12-slim to satisfy scipy dependency

- **Slug**: docker-backend-python-version-mismatch
- **Fixed**: 2026-11-21
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Upgraded the Docker backend base image from `python:3.11-slim` to `python:3.12-slim` in `services/Dockerfile`. This resolves the dependency resolution conflict during image build where `scipy>=1.18.1` requires `Python>=3.12`.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/Dockerfile` | modified | Updated base image declaration to `FROM python:3.12-slim` |
| `services/api/tests/test_docker_backend_requirements.py` | modified | Added `test_dockerfile_base_image_python_version` to pin Python >= 3.12 base image |

## Diff Highlights (optional)

```dockerfile
-FROM python:3.11-slim
+FROM python:3.12-slim
```

## Tests Added or Updated

- `services/api/tests/test_docker_backend_requirements.py::test_dockerfile_base_image_python_version` — Asserts that `services/Dockerfile` uses `python:3.12` base image to prevent regressions where Python 3.11 is reintroduced against Python >= 3.12 package requirements.

## Local Verification

- Commands run:
  - `services/api/.venv/Scripts/python.exe -m pytest services/api/tests/test_docker_backend_requirements.py` → 3 passed in 13.13s
  - `docker compose build backend` → Build succeeded; 205 packages resolved and installed cleanly in Python 3.12.16 Debian container environment
- Manual checks: Verified `scipy==1.18.1` installed properly without resolver conflicts during the Docker layer execution.

## Deviations from Assessment

None.

## Follow-ups

- None required. Container image build and local tests are green.
