# Bug Fix: Guardrail Routing & Fallback Taxonomy Contract

- **Slug**: guardrail-routing-taxonomy-contract
- **Fixed**: 2026-11-23
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Extended the guardrail decision taxonomy and data contract with explicit `deflect` and `clarify` actions, added `out_of_domain` and `needs_context` categories, implemented a 5-tier guardrail evaluation hierarchy with neutral deflection responses, and added multi-turn conversational continuity support for clarification continuations.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/domain/agent/entities.py` | modified | Added `deflect` and `clarify` to `GuardrailAction`, `deflected` and `clarified` to `GuardrailDisposition`, `out_of_domain` and `needs_context` to `GuardrailInputCategory`, and added synced `decision` property to `GuardrailEvaluationResult`. |
| `services/api/domain/agent/ports.py` | modified | Added `conversation_history` and `context` parameters to `InputGuardrailPort.evaluate_input`. |
| `services/api/application/services/agent_guardrails.py` | modified | Implemented 5-tier precedence hierarchy, added bilingual neutral deflection messages (`OUT_OF_DOMAIN_DEFLECTION_EN`, `OUT_OF_DOMAIN_DEFLECTION_ES`), clarification messages (`CLARIFY_SUPPORT_PROMPT_EN`, `CLARIFY_SUPPORT_PROMPT_ES`), and `_has_prior_support_or_clarification_context` helper for multi-turn elliptical queries. |
| `services/api/application/services/guardrail_observability.py` | modified | Updated `record_evaluation` and summary metric counters to record `deflected` and `clarified` dispositions alongside `blocked` and `redirected`. |
| `services/api/application/services/agent_workflow.py` | modified | Passed `conversation_history` into input guardrail evaluation and handled `deflect` and `clarify` actions cleanly in intake routing and generation suppression. |
| `services/api/tests/unit/test_agent_guardrails_input.py` | modified | Updated tests to assert `clarify` for generic support queries, `deflect` for benign out-of-domain queries, and added test suite `TestMultiTurnContinuityAndContractTaxonomy`. |
| `services/api/tests/integration/test_agent_guardrails_observability.py` | modified | Added integration test `test_deflect_and_clarify_dispositions_and_observability` verifying end-to-end agent query execution and observability metric counts. |

## Diff Highlights (optional)

```python
# domain/agent/entities.py
GuardrailAction = Literal["allow", "redirect", "block", "deflect", "clarify"]
GuardrailDisposition = Literal["blocked", "redirected", "deflected", "clarified"]
GuardrailInputCategory = Literal[
    "in_domain",
    "casual_trivia",
    "personal_task",
    "jailbreak_attempt",
    "unauthorized_order",
    "policy_mismatch",
    "restricted_data_leak",
    "external_injection",
    "malformed_output",
    "out_of_domain",
    "needs_context",
]
```

```python
# application/services/agent_guardrails.py (InputGuardrailValidator)
# 1. Tier 1: Anti-Jailbreak -> block + jailbreak_attempt
# 2. Tier 2: Restricted Personal Tasks -> block + personal_task
# 3. Tier 3: Benign Out-of-Domain -> deflect + out_of_domain + neutral deflection message
# 4. Tier 4: Ambiguous Support Inquiries -> clarify + needs_context + prompt for tracking/order details
# Permitted Casual Small Talk -> redirect + casual_trivia + mandatory redirect
# 5. Tier 5: Operational In-Domain -> allow + in_domain (with multi-turn context continuation support)
# Fallback Out-of-Domain -> deflect + out_of_domain + neutral deflection message
```

## Tests Added or Updated

- `services/api/tests/unit/test_agent_guardrails_input.py::test_generic_support_queries_prompt_for_clarification` — verifies generic support inquiries return `action="clarify"`, `input_category="needs_context"`, and prompt for details without C04 refusal.
- `services/api/tests/unit/test_agent_guardrails_input.py::test_out_of_domain_queries_are_deflected_with_neutral_message` — verifies weather/geography queries return `action="deflect"`, `input_category="out_of_domain"`, and polite neutral deflection messages without C04 essay refusals.
- `services/api/tests/unit/test_agent_guardrails_input.py::TestMultiTurnContinuityAndContractTaxonomy::test_contract_taxonomy_and_decision_property` — verifies typed decision enum contracts and dictionary serialization.
- `services/api/tests/unit/test_agent_guardrails_input.py::TestMultiTurnContinuityAndContractTaxonomy::test_multiturn_clarification_continuity_allows_elliptical_followup` — pins down AC-6 multi-turn continuity from `clarify` to elliptical follow-up.
- `services/api/tests/unit/test_agent_guardrails_input.py::TestMultiTurnContinuityAndContractTaxonomy::test_multiturn_clarification_continuity_with_location_cue` — pins down elliptical location answers under active support dialogue.
- `services/api/tests/unit/test_agent_guardrails_input.py::TestMultiTurnContinuityAndContractTaxonomy::test_multiturn_preserves_security_and_out_of_domain_precedence` — pins down strict precedence of jailbreak blocks, personal task blocks, and out-of-domain deflections even in multi-turn dialogues.
- `services/api/tests/integration/test_agent_guardrails_observability.py::TestEndToEndGuardrailsAndMemoryCoordination::test_deflect_and_clarify_dispositions_and_observability` — verifies `deflected` and `clarified` end-to-end recording in `GuardrailObservabilityService`.

## Local Verification

- Commands run:
  - `services/api/.venv/Scripts/python.exe -m pytest services/api/tests/unit/test_agent_guardrails_input.py services/api/tests/integration/test_agent_guardrails_observability.py -v` → 56 passed in 0.64s.
  - `services/api/.venv/Scripts/python.exe -m pytest services/api/tests/unit/test_agent_guardrails_authorization.py services/api/tests/unit/test_agent_guardrails_context_isolation.py services/api/tests/unit/test_agent_guardrails_output.py services/api/tests/unit/test_agent_workflow.py services/api/tests/unit/test_intent_classification.py services/api/tests/unit/test_memory_guardrails.py` → 108 passed in 0.98s.
- Manual checks: Verified `res.decision` and `res.action` backward compatibility and `to_dict()` outputs.

## Deviations from Assessment

None. The implementation followed the preferred remediation plan directly.

## Follow-ups

- Run `/speckit-bug-test slug=guardrail-routing-taxonomy-contract` to perform complete bug test validation and record test verification results.
