# Bug Fix: Guardrail Lexical Signal Decoupling & Academic/Medical Context Filtering

- **Slug**: guardrail-lexical-intent-decoupling
- **Fixed**: 2026-11-23
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Decoupled surface lexical cues from final `allow` decisions in `InputGuardrailValidator` and `FastIntentSemanticRouter` by replacing bare single-token regex keywords (`pallet`, `pallets`, `crate`, `crates`) with strict logistics collocations, introducing dedicated out-of-domain patterns for academic/historical and medical/veterinary inquiries, and gating operational overrides on authentic order references and operational actions.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/application/services/agent_guardrails.py` | modified | Added `OUT_OF_DOMAIN_ACADEMIC_AND_HISTORICAL` and `OUT_OF_DOMAIN_MEDICAL_AND_VETERINARY` patterns to `_OUT_OF_DOMAIN_PATTERNS`; required collocations for `pallets` and `crates` in `_IN_DOMAIN_LOGISTICS_CUES`; refined `_OPERATIONAL_LOGISTICS_ACTIONS` to avoid conflating "tracking number" with operational tracking verbs; implemented strict operational action gating in `InputGuardrailValidator.evaluate_input` and `FastIntentSemanticRouter.classify`. |
| `services/api/tests/unit/test_agent_guardrails_input.py` | modified | Added `TestGuardrailLexicalIntentDecoupling` verifying Block A control deflections (0% bypass), Block B adversarial camouflaged deflections (0% bypass), 100% allow rate on legitimate commercial operations, and semantic router alignment. |

## Diff Highlights (optional)

```python
# 1. Collocations required for pallets and crates
r"|\b(?:parcel|parcels|bulto|bultos)\b"
r"|\b(?:(?:shipping|wooden|warehouse|freight|storage|cargo|distribution)\s+(?:pallets?|crates?)|(?:pallets?|crates?)\s+(?:of\s+(?:goods|cargo|freight|shipments?|merchandise|stock|items?)|storage|shipments?|dimensions?|count|weight|stacking|handling)|(?:palets?|cajas?\s+de\s+madera)\s+(?:de\s+carga|en\s+almac[eé]n|para\s+env[ií]o|de\s+almacenamiento|de\s+mercanc[ií]as?))\b"

# 2. Strict operational gating preventing academic/medical deflection bypasses unless an authentic operational action on TrackFlow exists
has_order_pattern = any(pattern.search(cleaned) for pattern in _ORDER_REFERENCE_PATTERNS)
has_strict_operational_action = bool(
    has_order_pattern
    and _OPERATIONAL_LOGISTICS_ACTIONS.search(cleaned)
    and (
        has_prior_context
        or bool(context and context.get("session"))
        or bool(re.search(r"\b(?:ORD|TRK|TF|INC)-\d{3,10}\b", cleaned, re.IGNORECASE))
    )
)
```

## Tests Added or Updated

- `services/api/tests/unit/test_agent_guardrails_input.py::TestGuardrailLexicalIntentDecoupling::test_block_a_control_academic_and_medical_deflected` — Pins down 100% deflection on Block A control queries without logistics cues.
- `services/api/tests/unit/test_agent_guardrails_input.py::TestGuardrailLexicalIntentDecoupling::test_block_b_disguised_logistics_cues_deflected` — Pins down 100% deflection on Block B adversarial queries embedding camouflaged keywords (`pallet`, `pallets`, `crates`, `shipping claim`, `in transit`).
- `services/api/tests/unit/test_agent_guardrails_input.py::TestGuardrailLexicalIntentDecoupling::test_legitimate_commercial_logistics_allowed` — Confirms zero regression on genuine TrackFlow operations (`pallet storage`, `rates per pallet`, `shipping claim for order`, `cold-chain vaccine SLA`).
- `services/api/tests/unit/test_agent_guardrails_input.py::TestGuardrailLexicalIntentDecoupling::test_semantic_router_deflects_disguised_block_b_queries` — Confirms `FastIntentSemanticRouter` Stage 2 deflection on cross-disciplinary queries.

## Local Verification

- Commands run: `cd services/api; uv run pytest tests/unit/test_agent_guardrails_input.py` → 280 passed in 2.29s (100% pass rate).
- Commands run: `cd services/api; uv run pytest tests/unit/test_agent_guardrails_authorization.py tests/unit/test_agent_guardrails_context_isolation.py tests/unit/test_agent_guardrails_input.py tests/unit/test_agent_guardrails_output.py` → 302 passed in 2.28s.
- Manual checks: Verified the 10 Block B adversarial queries directly against `InputGuardrailValidator` and confirmed each resolves to `action="deflect"` (`input_category="out_of_domain"`).

## Deviations from Assessment

None. The implementation followed the preferred remediation plan directly.

## Follow-ups

- Continue monitoring telemetry for potential edge-case customer queries discussing veterinary cargo or exotic pharmaceutical shipments to ensure support policies route appropriately.
