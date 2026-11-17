# Bug Fix: Topic-Aware Refusal Message on Pharmaceutical Refrigeration SLA Inquiry

- **Slug**: pharma-sla-refusal
- **Fixed**: 2026-11-16
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Added a deterministic, sanitized `build_refusal_message(query: str) -> str` helper in `KnowledgeService` (and reused it in `GroundedGenerationAdapter.generate_grounded_answer()`) so out-of-scope inquiries return a topic-aware refusal message referencing the queried subject (e.g., `"temperature-controlled pharmaceutical refrigeration SLA"`) while normalizing shell-escaped single quotes (`'\''` -> `'`) and preserving benchmark-required refusal phrases. Also updated `specs/026-rag-knowledge-base/quickstart.md` Scenario 4 to provide clean cross-platform JSON request syntax alongside the expected refusal text.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/application/services/knowledge_service.py` | modified | Added `build_refusal_message(query)` with quote normalization, control-character/HTML stripping, length bounding, and topic interpolation; updated `KnowledgeService.query()` to use `build_refusal_message(request.query)` when `qualified_contexts` is empty. |
| `services/api/infrastructure/adapters/grounded_generation_adapter.py` | modified | Updated `GroundedGenerationAdapter.generate_grounded_answer()` to return `build_refusal_message(query)` when `contexts` is empty. |
| `services/api/tests/unit/test_knowledge_service.py` | modified | Updated `test_refuses_query_when_all_candidates_fall_below_0_62_threshold` to assert topic-aware refusal phrasing (`"pharmaceutical refrigeration"`), POSIX quote escape normalization (`'\''`), and empty-query fallback (`STANDARD_REFUSAL_MESSAGE`). |
| `services/api/tests/integration/test_knowledge_routes.py` | modified | Updated `test_us3_out_of_scope_query_triggers_refusal` to assert `"pharmaceutical refrigeration"` and `"operations leadership"` appear alongside `"does not contain"` in `data["answer"]`. |
| `specs/026-rag-knowledge-base/quickstart.md` | modified | Updated Scenario 4 (lines 140–158) with cross-platform `curl` / JSON request syntax without bash `'\''` escape artifacts and documented the exact topic-aware refusal message. |

## Diff Highlights (optional)

```python
# services/api/application/services/knowledge_service.py
def build_refusal_message(query: str) -> str:
    if not query or not query.strip():
        return STANDARD_REFUSAL_MESSAGE

    sanitized = query.replace("'\\''", "'").replace('\\"', '"')
    sanitized = re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", sanitized)
    sanitized = re.sub(r"<[^>]*>", " ", sanitized)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()

    topic = _LEADING_QUERY_BOILERPLATE_RE.sub("", sanitized)
    topic = topic.strip(" ?.!,;:\"'`()[]{}")
    topic = re.sub(r"[^\w\s\-'/]", " ", topic)
    topic = re.sub(r"\s+", " ", topic).strip(" -'/")
    ...
    return (
        f"TrackFlow internal documentation does not contain verified policy regarding "
        f"{topic}. For operational assistance on this topic, please consult the "
        f"operations leadership directly."
    )
```

## Tests Added or Updated

- `services/api/tests/unit/test_knowledge_service.py::TestKnowledgeServiceThresholdAndRefusal::test_refuses_query_when_all_candidates_fall_below_0_62_threshold` — Pins down that sub-threshold queries return `is_refusal=True`, `sources=[]`, include `"pharmaceutical refrigeration"` and `"operations leadership directly"` in `answer`, strip bash-escaped `'\''` sequences, and fall back to `STANDARD_REFUSAL_MESSAGE` when the query is empty.
- `services/api/tests/integration/test_knowledge_routes.py::TestKnowledgeRoutesIntegration::test_us3_out_of_scope_query_triggers_refusal` — Pins down that `POST /api/v1/knowledge/query` for the out-of-scope pharmaceutical refrigeration inquiry returns `is_refusal=True`, `sources=[]`, and explicitly mentions `"pharmaceutical refrigeration"`, `"does not contain"`, and `"operations leadership"` in `data["answer"]`.

## Local Verification

- Commands run:
  - `cd services/api && uv run pytest tests/unit/test_knowledge_service.py tests/integration/test_knowledge_routes.py tests/unit/test_knowledge_chunking.py tests/unit/test_knowledge_config.py tests/unit/test_knowledge_guardrails.py tests/integration/test_qdrant_adapter.py -v` → **41 passed**
  - `cd services/api && uv run python ../../scripts/evaluate_rag_retrieval.py --eval-file ../../data/eval/test-queries.json` → **Benchmark PASSED** (Recall@1: 100.0%, Recall@3: 100.0%, MRR: 1.0000, Out-of-Scope Refusal Rate: 100.0% [1/1]).
- Manual checks: Verified that both `"What is TrackFlow's temperature-controlled pharmaceutical refrigeration SLA?"` and the POSIX-escaped `"What is TrackFlow'\''s temperature-controlled pharmaceutical refrigeration SLA?"` produce `"TrackFlow internal documentation does not contain verified policy regarding temperature-controlled pharmaceutical refrigeration SLA. For operational assistance on this topic, please consult the operations leadership directly."`

## Deviations from Assessment

None.

## Follow-ups

- Run `/speckit-bug-test slug=pharma-sla-refusal` to record the formal verification report.
