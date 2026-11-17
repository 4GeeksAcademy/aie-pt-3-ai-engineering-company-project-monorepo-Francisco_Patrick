# Bug Verification: Topic-Aware Refusal Message on Pharmaceutical Refrigeration SLA Inquiry

- **Slug**: pharma-sla-refusal
- **Tested**: 2026-11-16
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The original symptom no longer reproduces: submitting `"What is TrackFlow's temperature-controlled pharmaceutical refrigeration SLA?"` (or its POSIX-escaped variant `"What is TrackFlow'\''s temperature-controlled pharmaceutical refrigeration SLA?"`) to `POST /api/v1/knowledge/query` now returns `is_refusal: true`, `sources: []`, and the topic-aware refusal message `"TrackFlow internal documentation does not contain verified policy regarding temperature-controlled pharmaceutical refrigeration SLA. For operational assistance on this topic, please consult the operations leadership directly."` All 41 Knowledge Base unit and integration tests and the 10-query RAG evaluation benchmark pass with zero regressions.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `uv run pytest tests/integration/test_knowledge_routes.py -k test_us3_out_of_scope_query_triggers_refusal -v` | pass | Exercises `POST /api/v1/knowledge/query` with the pharmaceutical refrigeration SLA query; verifies `is_refusal=True`, `sources=[]`, and `"pharmaceutical refrigeration"` in `answer`. |
| New / updated tests | `uv run pytest tests/unit/test_knowledge_service.py tests/integration/test_knowledge_routes.py -v` | pass | 15 passed in 45.99s, including POSIX `'\''` quote normalization and topic-aware refusal assertions. |
| Regression suite | `uv run pytest tests/unit/test_knowledge_chunking.py tests/unit/test_knowledge_config.py tests/unit/test_knowledge_guardrails.py tests/unit/test_knowledge_service.py tests/integration/test_knowledge_routes.py tests/integration/test_qdrant_adapter.py -v && uv run python ../../scripts/evaluate_rag_retrieval.py --eval-file ../../data/eval/test-queries.json` | pass | 41 pytest tests passed; RAG benchmark passed with Recall@1: 100.0% (9/9), Recall@3: 100.0% (9/9), MRR: 1.0000, Out-of-Scope Refusal Rate: 100.0% (1/1). |
| Lint / type-check | `uv run python -m py_compile application/services/knowledge_service.py infrastructure/adapters/grounded_generation_adapter.py tests/unit/test_knowledge_service.py tests/integration/test_knowledge_routes.py` | pass | Zero syntax/bytecode compilation errors (`ruff` not installed in `.venv`). |

## Output Excerpts

```text
tests/unit/test_knowledge_service.py::TestKnowledgeServiceThresholdAndRefusal::test_refuses_query_when_all_candidates_fall_below_0_62_threshold PASSED [  6%]
tests/unit/test_knowledge_service.py::TestKnowledgeServiceThresholdAndRefusal::test_filters_out_sub_threshold_candidates_while_keeping_qualified_ones PASSED [ 13%]
...
tests/integration/test_knowledge_routes.py::TestKnowledgeRoutesIntegration::test_us3_out_of_scope_query_triggers_refusal PASSED [ 73%]
======================= 15 passed, 3 warnings in 45.99s =======================
```

```text
[eval-009] PASS (REFUSED) | latency=1.4ms | query='What is TrackFlow's temperature-controlled pharmaceutic...'
------------------------------------------------------------------------
In-Scope Queries Evaluated : 9
Recall@1                   : 100.0% (9/9)
Recall@3 (Target >= 80.0%) : 100.0% (9/9)
Mean Reciprocal Rank (MRR) : 1.0000
Out-of-Scope Refusal Rate  : 100.0% (1/1)
Average Latency            : 109.89 ms
========================================================================
Benchmark PASSED: All KPIs exceeded target thresholds.
```

## Residual Risks

- Highly unstructured or non-English out-of-scope queries that do not match the English leading-question regex still include their sanitized subject phrase (bounded to 80 characters) in the refusal message, or fall back to `STANDARD_REFUSAL_MESSAGE` if shorter than 3 characters.

## Recommendation

Close the bug — verified end-to-end across unit tests, FastAPI route integration tests, and the RAG retrieval/refusal benchmark suite.
