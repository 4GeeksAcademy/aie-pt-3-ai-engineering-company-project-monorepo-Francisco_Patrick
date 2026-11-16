# Bug Fix: PowerShell Wildcard Glob Failure When Running Knowledge Base Pytest Suite

- **Slug**: pytest-knowledge-glob-error
- **Fixed**: 2026-11-16
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Replaced the POSIX-only wildcard glob pattern (`tests/unit/test_knowledge*.py tests/integration/test_knowledge*.py`) in `specs/026-rag-knowledge-base/quickstart.md` with explicit, cross-platform relative test file paths (including `tests/integration/test_qdrant_adapter.py`) so that `uv run pytest` executes identically across Windows PowerShell, Command Prompt, and POSIX shells without failing with exit code 4.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `specs/026-rag-knowledge-base/quickstart.md` | modified | Replaced wildcard globs in Section 5 (`Automated Verification Gates`) with all 6 explicit unit and integration test module paths for the RAG & Knowledge Base feature. |

## Diff Highlights (optional)

```diff
 ## 5. Automated Verification Gates
 
 Run all automated quality gates:
 ```bash
-# Backend test suite
+# Backend test suite (cross-platform: Windows PowerShell & POSIX shells)
 cd services/api
-uv run pytest tests/unit/test_knowledge*.py tests/integration/test_knowledge*.py -v
+uv run pytest tests/unit/test_knowledge_chunking.py tests/unit/test_knowledge_config.py tests/unit/test_knowledge_guardrails.py tests/unit/test_knowledge_service.py tests/integration/test_knowledge_routes.py tests/integration/test_qdrant_adapter.py -v
```

## Tests Added or Updated

- Verified all 6 existing RAG & Knowledge Base test modules are discovered and executed by the updated verification gate command (`41 items` total across `test_knowledge_chunking.py`, `test_knowledge_config.py`, `test_knowledge_guardrails.py`, `test_knowledge_service.py`, `test_knowledge_routes.py`, and `test_qdrant_adapter.py`).

## Local Verification

- Commands run: `Set-Location services/api; uv run pytest tests/unit/test_knowledge_chunking.py tests/unit/test_knowledge_config.py tests/unit/test_knowledge_guardrails.py tests/unit/test_knowledge_service.py tests/integration/test_knowledge_routes.py tests/integration/test_qdrant_adapter.py -v` → `41 passed, 3 warnings in 120.71s` (exit code 0).
- Manual checks: Confirmed that running the updated command in Windows PowerShell collects all 41 tests without wildcard glob expansion errors.

## Deviations from Assessment

None.

## Follow-ups

- Run `/speckit-bug-test slug=pytest-knowledge-glob-error` to record the verification report.
