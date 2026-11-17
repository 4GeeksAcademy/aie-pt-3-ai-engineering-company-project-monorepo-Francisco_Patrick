# Bug Assessment: Generic Static Refusal Message on Pharmaceutical Refrigeration SLA Inquiry

- **Slug**: pharma-sla-refusal
- **Created**: 2026-11-16
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: low

## Report (verbatim or summarized)

> When user ask to the assitant a consult "What is TrackFlow'\''s temperature-controlled pharmaceutical refrigeration SLA?", the assistant response with: "TrackFlow internal documentation does not contain verified policy regarding this inquiry. For operational assistance on this topic, please consult the operations leadership directly."

## Symptom

When a user queries `"What is TrackFlow's temperature-controlled pharmaceutical refrigeration SLA?"` (or pastes the POSIX-escaped string `"What is TrackFlow'\''s temperature-controlled pharmaceutical refrigeration SLA?"` from `specs/026-rag-knowledge-base/quickstart.md`), the assistant returns the hardcoded generic string `"TrackFlow internal documentation does not contain verified policy regarding this inquiry. For operational assistance on this topic, please consult the operations leadership directly."` instead of a topic-aware refusal message that explicitly clarifies TrackFlow documentation lacks information on **pharmaceutical refrigeration** as specified in `specs/026-rag-knowledge-base/spec.md` (User Story 3, Acceptance Scenario 1, line 85) and `specs/026-rag-knowledge-base/quickstart.md` (Scenario 4, line 152).

*(Note: Returning a refusal with `is_refusal: true` and `sources: []` rather than fabricating an SLA is intentional per FR-008, FR-009, and SC-003 because none of the 4 canonical documents in `docs/company-knowledge-base/` define pharmaceutical or cold-chain refrigeration policies; however, the static refusal template omits the queried topic and `quickstart.md` contains shell-escaped single quotes `'\''` that leak into the query when copied outside bash.)*

## Reproduction

1. Start the FastAPI backend (`cd services/api && uv run uvicorn main:app --reload --port 8000`) or use the Backoffice Knowledge UI at `http://localhost:3001/knowledge`.
2. Submit the query from `specs/026-rag-knowledge-base/quickstart.md` Scenario 4 (lines 142–147):
   ```json
   {
     "query": "What is TrackFlow's temperature-controlled pharmaceutical refrigeration SLA?",
     "top_k": 3
   }
   ```
3. Observe the HTTP 200 JSON payload:
   - `is_refusal` is `true` and `sources` is `[]`.
   - `answer` is the static constant `STANDARD_REFUSAL_MESSAGE`: `"TrackFlow internal documentation does not contain verified policy regarding this inquiry. For operational assistance on this topic, please consult the operations leadership directly."`
   - Compare against `specs/026-rag-knowledge-base/quickstart.md:152` (*"`answer` politely clarifies that TrackFlow documentation lacks information on pharmaceutical refrigeration, with guidance to contact operations leadership"*) and `specs/026-rag-knowledge-base/spec.md:85` (*"indicating that TrackFlow internal knowledge does not contain information on pharmaceutical refrigeration, advising the user to contact the operations team directly"*).

## Suspected Code Paths

- `services/api/application/services/knowledge_service.py:30-34` — Defines the static constant `STANDARD_REFUSAL_MESSAGE` (`"TrackFlow internal documentation does not contain verified policy regarding this inquiry. For operational assistance on this topic, please consult the operations leadership directly."`) with no interpolation of the user's queried topic.
- `services/api/application/services/knowledge_service.py:100-108` — When `qualified_contexts` is empty (`similarity_score < 0.62`), returns `GroundedAnswer` with `answer=STANDARD_REFUSAL_MESSAGE` directly instead of formatting a topic-aware refusal message or delegating empty-context refusal formatting to `LLMGenerationPort`.
- `services/api/infrastructure/adapters/grounded_generation_adapter.py:85-90` — `GroundedGenerationAdapter.generate_grounded_answer()` also returns a hardcoded static string when `contexts` is empty.
- `services/api/infrastructure/adapters/embedding_adapter.py:267-293, 430-439` — Maps `"pharmaceutical"`, `"refrigeration"`, `"cold-chain"`, and `"temperature-controlled"` in `OUT_OF_SCOPE_TRIGGERS` to orthogonal vector dimensions (`192..255`), ensuring all candidate chunks score below the `0.62` threshold (`~0.51` max).
- `specs/026-rag-knowledge-base/quickstart.md:142-153` — Scenario 4 uses bash single-quote escaping (`'What is TrackFlow'\''s ...'`) which introduces literal `'\''` characters when copied into the Backoffice UI or Windows PowerShell, and documents on line 152 that `answer` clarifies the lack of information on pharmaceutical refrigeration.

## Root Cause Hypothesis

Confidence: **high**. `KnowledgeService.query()` (`services/api/application/services/knowledge_service.py:100-108`) short-circuits when no retrieved chunks meet the `0.62` similarity threshold (`effective_threshold`) and returns a static constant `STANDARD_REFUSAL_MESSAGE` (`"TrackFlow internal documentation does not contain verified policy regarding this inquiry..."`). Because `STANDARD_REFUSAL_MESSAGE` does not extract or reference the subject of `request.query` (and does not normalize escaped quote artifacts like `'\''`), the response never mentions `"pharmaceutical refrigeration"` as expected by `spec.md:85` and `quickstart.md:152`.

## Proposed Remediation

**Preferred**:
1. Add a deterministic helper `build_refusal_message(query: str) -> str` in `services/api/application/services/knowledge_service.py` (and use it in `GroundedGenerationAdapter.generate_grounded_answer()` when `contexts` is empty) that sanitizes bash-escaped quotes (`'\''` -> `'`), extracts salient out-of-scope or domain topic terms from the inquiry (e.g., `"temperature-controlled pharmaceutical refrigeration SLA"` / `"pharmaceutical refrigeration"`), and returns a polite, topic-specific refusal message while preserving the canonical phrases required by downstream benchmarks (`"TrackFlow internal documentation does not contain verified policy regarding ..."`, `"operations leadership directly"`).
2. Update `specs/026-rag-knowledge-base/quickstart.md:142-153` to provide clean cross-platform request syntax alongside the expected refusal text so users copying the query into the Backoffice UI or PowerShell do not inadvertently send literal `'\''` sequences.

**Alternatives** (optional):
- **Alternative A (Documentation-only alignment)**: If the static `STANDARD_REFUSAL_MESSAGE` is preferred over dynamic topic mention, update `specs/026-rag-knowledge-base/quickstart.md:152` and `specs/026-rag-knowledge-base/spec.md:85` to quote `STANDARD_REFUSAL_MESSAGE` verbatim. *Trade-off*: Less informative to frontline account managers than naming the unverified topic they asked about.
- **Alternative B (Add pharmaceutical refrigeration to knowledge corpus)**: If business requirements changed such that TrackFlow now offers pharmaceutical refrigeration SLAs, add a documented policy section to `docs/company-knowledge-base/trackflow-sla-delivery.en.md`, remove `"pharmaceutical"` / `"refrigeration"` / `"temperature-controlled"` from `OUT_OF_SCOPE_TRIGGERS` in `services/api/infrastructure/adapters/embedding_adapter.py`, and replace `eval-009` in `data/eval/test-queries.json` with a different out-of-scope query. *Trade-off*: Contradicts `spec.md` User Story 3 Scenario 1 and `data/eval/test-queries.json` (`eval-009`), which explicitly define pharmaceutical refrigeration as the out-of-scope negative control.

**Files likely to change**:
- `services/api/application/services/knowledge_service.py`
- `services/api/infrastructure/adapters/grounded_generation_adapter.py`
- `services/api/tests/unit/test_knowledge_service.py`
- `services/api/tests/integration/test_knowledge_routes.py`
- `specs/026-rag-knowledge-base/quickstart.md`

**Tests to add or update**:
- `services/api/tests/unit/test_knowledge_service.py::TestKnowledgeServiceThresholdAndRefusal::test_refuses_query_when_all_candidates_fall_below_0_62_threshold` — Verify that the refusal response sets `is_refusal=True`, `sources=[]`, preserves the standard refusal phrasing, and includes the queried topic (`"pharmaceutical refrigeration"`), including when the query contains bash-escaped `'\''` quotes.
- `services/api/tests/integration/test_knowledge_routes.py::TestKnowledgeRoutesIntegration::test_us3_out_of_scope_query_triggers_refusal` — Assert that `"pharmaceutical refrigeration"` is explicitly mentioned in `data["answer"]` alongside `"does not contain"` and `"operations leadership"`.

## Risks & Considerations

- **Evaluation Benchmark Compatibility (`data/eval/test-queries.json`)**: `eval-009` checks `expected_answer_keywords: ["does not contain", "operations"]` and `is_out_of_scope: true`. The topic-aware refusal message must retain both `"does not contain"` and `"operations"` so `scripts/evaluate_rag_retrieval.py` continues to pass 100%.
- **Prompt Injection / Input Reflection Safety**: When echoing or extracting the topic from `request.query` into the refusal message, strip control characters, HTML/markdown tags, and shell escape artifacts (`'\''`), and bound the extracted topic length so untrusted input cannot inject misleading instructions into the refusal text.

## Open Questions

- [NEEDS CLARIFICATION: Confirm whether the desired fix is (1) making the refusal message explicitly mention the queried topic ("pharmaceutical refrigeration") per `spec.md:85` and `quickstart.md:152` while keeping `is_refusal: true`, or (2) adding a new pharmaceutical refrigeration SLA policy to `docs/company-knowledge-base/trackflow-sla-delivery.en.md` so the assistant answers with a concrete SLA instead of refusing.]
