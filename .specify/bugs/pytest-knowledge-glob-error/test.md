# Bug Verification: PowerShell Wildcard Glob Failure When Running Knowledge Base Pytest Suite

- **Slug**: pytest-knowledge-glob-error
- **Tested**: 2026-11-16
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

Executing the updated Section 5 verification command from `specs/026-rag-knowledge-base/quickstart.md` in a Windows PowerShell session no longer fails with `ERROR: file or directory not found: tests/unit/test_knowledge*.py` (exit code 4). All 6 RAG & Knowledge Base unit and integration test modules (`41 items` total, including `tests/integration/test_qdrant_adapter.py`) are collected and pass with exit code `0`, with zero regressions.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `Set-Location services/api; uv run pytest tests/unit/test_knowledge_chunking.py tests/unit/test_knowledge_config.py tests/unit/test_knowledge_guardrails.py tests/unit/test_knowledge_service.py tests/integration/test_knowledge_routes.py tests/integration/test_qdrant_adapter.py -v` | pass | Collected all 41 items in Windows PowerShell and exited 0 (`41 passed in 122.19s`). |
| New / updated tests | `uv run pytest tests/unit/test_knowledge_chunking.py tests/unit/test_knowledge_config.py tests/unit/test_knowledge_guardrails.py tests/unit/test_knowledge_service.py tests/integration/test_knowledge_routes.py tests/integration/test_qdrant_adapter.py -v` | pass | All 4 unit test modules (22 tests) and 2 integration test modules (19 tests, including `test_qdrant_adapter.py`) passed. |
| Regression suite | `uv run pytest tests/unit/test_knowledge_chunking.py tests/unit/test_knowledge_config.py tests/unit/test_knowledge_guardrails.py tests/unit/test_knowledge_service.py tests/integration/test_knowledge_routes.py tests/integration/test_qdrant_adapter.py -v` | pass | Full 026-rag-knowledge-base backend verification suite passed without regressions. |
| Lint / type-check | `npm run typecheck` | pass | `tsc --noEmit` completed with 0 errors (exit code 0). |

## Output Excerpts

```text
============================= test session starts =============================
platform win32 -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0 -- J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api
configfile: pyproject.toml
plugins: anyio-4.14.2, cov-7.1.0
collecting ... collected 41 items

tests/unit/test_knowledge_chunking.py::TestMarkdownSemanticChunker::test_load_and_chunk_all_four_canonical_documents PASSED [  2%]
...
tests/integration/test_qdrant_adapter.py::TestQdrantVectorStoreAdapterIntegration::test_forbidden_403_error_includes_actionable_hint_and_masks_secret PASSED [100%]

================= 41 passed, 3 warnings in 122.19s (0:02:02) ==================
```

```text
> trackflow-programming-foundations@1.0.0 typecheck
> tsc --noEmit
```

## Residual Risks

- If new test files are added to the `026-rag-knowledge-base` feature in the future, they should either be appended to the explicit file list in `specs/026-rag-knowledge-base/quickstart.md` or run via directory/keyword targeting (`uv run pytest tests/unit tests/integration -k "knowledge or qdrant" -v`).

## Recommendation

Close the bug — verified end-to-end in Windows PowerShell with all 41 unit and integration tests passing.
