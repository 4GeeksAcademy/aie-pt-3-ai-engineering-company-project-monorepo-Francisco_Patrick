# Bug Fix: Docker backend container fails with missing langgraph module

- **Slug**: docker-backend-missing-langgraph
- **Fixed**: 2026-11-21
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Synchronized `services/api/requirements.txt` with `services/api/pyproject.toml` by adding missing dependencies (`langgraph`, `langgraph-checkpoint`, `langchain-mcp-adapters`, `fastmcp`, `mcpauth`, `pyjwt`, `scikit-learn`, `scipy`, `matplotlib`, `burner-redis`, `amplitude-analytics`) so Docker image builds include all runtime dependencies required during API startup.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/requirements.txt` | modified | Added `langgraph>=1.2.22`, `langgraph-checkpoint>=4.3.2`, `langchain-mcp-adapters>=0.3.2`, `fastmcp>=3.4.11`, `mcpauth>=0.1.1`, `pyjwt>=2.15.1`, `scikit-learn>=1.9.1`, `scipy>=1.18.1`, `matplotlib>=3.11.2`, `burner-redis>=0.1.7`, `amplitude-analytics>=1.3.0` |
| `services/api/tests/test_docker_backend_requirements.py` | added test | Verified `requirements.txt` includes required agent and core packages, and verified `langgraph`, `BaseCheckpointSaver`, and `SupportAgentService` import cleanly |

## Diff Highlights

```diff
--- a/services/api/requirements.txt
+++ b/services/api/requirements.txt
@@ -19,5 +19,14 @@ redis>=5.0.0
 flower>=2.0.0
 qdrant-client>=1.13.0
 fastembed>=0.5.0
+scikit-learn>=1.9.1
+scipy>=1.18.1
+matplotlib>=3.11.2
+burner-redis>=0.1.7
+amplitude-analytics>=1.3.0
+langgraph>=1.2.22
+langgraph-checkpoint>=4.3.2
+langchain-mcp-adapters>=0.3.2
+fastmcp>=3.4.11
+mcpauth>=0.1.1
+pyjwt>=2.15.1
```

## Tests Added or Updated

- `services/api/tests/test_docker_backend_requirements.py::test_requirements_contains_langgraph_and_agent_dependencies` — Verifies `services/api/requirements.txt` contains `langgraph` and associated dependencies matching `pyproject.toml` specifications.
- `services/api/tests/test_docker_backend_requirements.py::test_support_agent_service_and_langgraph_imports` — Pins down importability of `langgraph`, `BaseCheckpointSaver`, `langchain_mcp_adapters`, and `SupportAgentService` to ensure backend Uvicorn startup succeeds without `ModuleNotFoundError`.

## Local Verification

- Commands run: `uv run --project services/api pytest services/api/tests/test_docker_backend_requirements.py -v` → 2 passed in 9.66s.
- Commands run: `uv run --project services/api pytest services/api/tests/test_worker_prefect_compatibility.py` → 4 passed in 34.57s.
- Manual checks: Verified `services/api/requirements.txt` contains exact version bounds aligning with `services/api/pyproject.toml`.

## Deviations from Assessment

None. The remediation directly implemented the preferred option from `assessment.md`.

## Follow-ups

- Consider updating CI/CD pipelines to run dependency parity checks between `pyproject.toml` and `requirements.txt`.
