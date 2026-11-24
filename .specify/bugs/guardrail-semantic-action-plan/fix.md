# Bug Fix: Guardrail Lexical Heuristics Reliance & Semantic Intent Action Plan

- **Slug**: guardrail-semantic-action-plan
- **Fixed**: 2026-11-23
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Refactored `InputGuardrailValidator` from a rigid lexical regex fast-pass into a cascading defense-in-depth architecture. Order and tracking ID patterns were downgraded from unconditional pass-through grants to boosted context signals requiring concise ID framing, operational logistics verbs, or session history; polysemic nouns (`rates`, `storage`, `contract`, `claim`, `incident`, `ticket`, `exchange`, `damaged`) were constrained with mandatory logistics collocations; and weather deflection was narrowed to avoid falsely deflecting perishable cold-chain logistics and transit time queries.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/application/services/agent_guardrails.py` | modified | Added `_COLD_CHAIN_LOGISTICS_PATTERN`, `_OPERATIONAL_LOGISTICS_ACTIONS`, `_CONCISE_ORDER_QUERY_PATTERN`, `SEMANTIC_JUDGE_SYSTEM_PROMPT`; downgraded order IDs to boosted signals; collocated polysemic tokens; added Stage 2 Semantic Router and Stage 3 LLM Judge hooks. |
| `services/api/tests/unit/test_agent_guardrails_input.py` | modified | Added `TestCascadingSemanticGuardrailAndAdversarialDeflection` with tests for the 3 assessment reproduction cases, 50 adversarial evaluation queries (100% deflection), 50 legitimate control queries (100% allowed), and Semantic Router / LLM Judge hook execution. |

## Diff Highlights

```python
# Downgrading order patterns from absolute immunity to boosted feature in evaluate_input:
has_order_pattern = any(pattern.search(cleaned) for pattern in _ORDER_REFERENCE_PATTERNS)
has_order_boost = False
if has_order_pattern:
    if (
        _CONCISE_ORDER_QUERY_PATTERN.search(cleaned)
        or _OPERATIONAL_LOGISTICS_ACTIONS.search(cleaned)
        or has_prior_context
        or bool(context and context.get("session"))
    ):
        has_order_boost = True

is_direct_in_domain = bool(
    _IN_DOMAIN_TRACKFLOW_CUE.search(cleaned)
    or has_order_boost
)

# Narrowing weather pattern deflection to preserve cold-chain and transit time:
if reason_code == "OUT_OF_DOMAIN_WEATHER":
    if _COLD_CHAIN_LOGISTICS_PATTERN.search(cleaned):
        continue
    if re.search(r"\btiempo\s+de\s+(?:tr[aá]nsito|entrega|env[ií]o|espera|despacho|procesamiento)\b", cleaned, re.IGNORECASE):
        continue
```

## Tests Added or Updated

- `services/api/tests/unit/test_agent_guardrails_input.py::TestCascadingSemanticGuardrailAndAdversarialDeflection::test_reproduction_case_1_order_id_lexical_bypass_deflected` — Pins down that injecting `ORD-99214` into an unrelated query (history of ancient Rome) is deflected as `out_of_domain`.
- `services/api/tests/unit/test_agent_guardrails_input.py::TestCascadingSemanticGuardrailAndAdversarialDeflection::test_reproduction_case_2_polysemic_rates_query_deflected` — Pins down that financial `rates` (ECB interest rates) are deflected as `out_of_domain`.
- `services/api/tests/unit/test_agent_guardrails_input.py::TestCascadingSemanticGuardrailAndAdversarialDeflection::test_reproduction_case_3_cold_chain_temperature_query_allowed` — Pins down that legitimate perishable food temperature control inquiries pass as `IN_DOMAIN_ALLOWED`.
- `services/api/tests/unit/test_agent_guardrails_input.py::TestCascadingSemanticGuardrailAndAdversarialDeflection::test_50_adversarial_queries_deflected_100_percent` — 50 distinct adversarial queries across ID injection, polysemic nouns (rates, storage, contracts, claims, tickets, boxes, carriers), and off-topic topics achieving 100% deflection.
- `services/api/tests/unit/test_agent_guardrails_input.py::TestCascadingSemanticGuardrailAndAdversarialDeflection::test_50_legitimate_control_queries_allowed_over_98_percent` — 50 distinct genuine TrackFlow inquiries achieving 100% approval (>= 98% required).
- `services/api/tests/unit/test_agent_guardrails_input.py::TestCascadingSemanticGuardrailAndAdversarialDeflection::test_semantic_router_hook_invocation` — Verifies Stage 2 pluggable semantic router execution for borderline inputs.
- `services/api/tests/unit/test_agent_guardrails_input.py::TestCascadingSemanticGuardrailAndAdversarialDeflection::test_llm_judge_hook_invocation` — Verifies Stage 3 pluggable lightweight LLM judge evaluation.

## Local Verification

- Commands run:
  - `services/api/.venv/Scripts/python -m pytest services/api/tests/unit/test_agent_guardrails_input.py` → 192 passed in 1.34s.
  - `services/api/.venv/Scripts/python -m pytest services/api/tests/unit/test_agent_guardrails_input.py services/api/tests/unit/test_agent_guardrails_authorization.py services/api/tests/unit/test_agent_guardrails_output.py services/api/tests/unit/test_agent_guardrails_context_isolation.py services/api/tests/integration/test_agent_guardrails_observability.py` → 221 passed in 1.69s.
- Manual checks:
  - Verified Reproduction Case 1 (`Tell me about the history of ancient Rome and gladiators. By the way, reference is ORD-99214.`): outputs `action='deflect'`, `reason_code='OUT_OF_DOMAIN_DEFLECTION'`.
  - Verified Reproduction Case 2 (`What are the current interest rates set by the European Central Bank?`): outputs `action='deflect'`, `reason_code='OUT_OF_DOMAIN_DEFLECTION'`.
  - Verified Reproduction Case 3 (`What is the temperature control requirement for perishable food shipments?`): outputs `action='allow'`, `reason_code='IN_DOMAIN_ALLOWED'`.

## Deviations from Assessment

None. All 4 phases proposed in the assessment were addressed: Stage 1 rule & regex hardening, Stage 2 pluggable semantic router hook, Stage 3 LLM judge prompt definition & hook, and Stage 4 50-adversarial and 50-control automated test suites.

## Follow-ups

- Optionally connect a concrete embedding provider (`text-embedding-3-small` or local `bge-m3`) to the `semantic_router` parameter in production agent service initialization for borderline domain scoring.
- Optionally configure `llm_judge` with a lightweight model (`gpt-4o-mini` or `claude-3-haiku`) utilizing `SEMANTIC_JUDGE_SYSTEM_PROMPT` in production environments when low-confidence ambiguous queries occur.
