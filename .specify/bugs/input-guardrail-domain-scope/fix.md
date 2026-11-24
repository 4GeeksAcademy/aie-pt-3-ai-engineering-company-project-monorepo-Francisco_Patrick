# Bug Fix: Input Guardrail Out-of-Domain Detection & Cue Enforcement

- **Slug**: input-guardrail-domain-scope
- **Fixed**: 2026-11-22
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Implemented comprehensive bilingual in-domain logistics pattern validation (`_IN_DOMAIN_LOGISTICS_CUES` and `_IN_DOMAIN_TRACKFLOW_CUE`) and updated `InputGuardrailValidator.evaluate_input` to block unclassified out-of-domain queries at Layer 1 with `action="block"`, `failure_category="content"`, `input_category="personal_task"`, and `reason_code="OUT_OF_DOMAIN_TASK"`, redirecting users back to TrackFlow's logistics scope.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/application/services/agent_guardrails.py` | modified | Defined comprehensive `_IN_DOMAIN_LOGISTICS_CUES` pattern covering shipments, tracking, returns, SLAs, incidents, inventory, and confirmation turns; relocated `_ORDER_REFERENCE_PATTERNS`; updated `evaluate_input` to validate domain cues and block out-of-domain inquiries. |
| `services/api/tests/unit/test_agent_guardrails_input.py` | modified | Added `test_out_of_domain_queries_are_blocked_and_redirected` covering trivia/general knowledge queries in English and Spanish; expanded `test_in_domain_queries_are_allowed` with colloquial and dialogue turns. |

## Diff Highlights (optional)

```python
# Layer 1 In-Domain Evaluation & Out-of-Domain Block
is_in_domain = bool(
    _IN_DOMAIN_TRACKFLOW_CUE.search(cleaned)
    or any(pattern.search(cleaned) for pattern in _ORDER_REFERENCE_PATTERNS)
)
if is_in_domain:
    return GuardrailEvaluationResult(
        layer="input_guard",
        action="allow",
        failure_category="none",
        input_category="in_domain",
        reason_code="IN_DOMAIN_ALLOWED",
        message=None,
    )

return GuardrailEvaluationResult(
    layer="input_guard",
    action="block",
    failure_category="content",
    input_category="personal_task",
    reason_code="OUT_OF_DOMAIN_TASK",
    message=PERSONAL_TASK_REFUSAL_ES if use_es else PERSONAL_TASK_REFUSAL_EN,
)
```

## Tests Added or Updated

- `services/api/tests/unit/test_agent_guardrails_input.py::TestPersonalTaskRefusalAndCasualTriviaRedirection::test_out_of_domain_queries_are_blocked_and_redirected` — Pins down that out-of-domain questions ("what is the capital of France?", "explain photosynthesis", "what is the weather in Paris like", "¿cuál es la capital de Francia?", "cuéntame un chiste") are blocked at Layer 1 with `action="block"`, `failure_category="content"`, `input_category="personal_task"`, and `reason_code="OUT_OF_DOMAIN_TASK"`.
- `services/api/tests/unit/test_agent_guardrails_input.py::TestPersonalTaskRefusalAndCasualTriviaRedirection::test_in_domain_queries_are_allowed` — Verified that colloquial tracking, return, damaged package inquiries, and confirmation turns ("Yes", "No") continue to be allowed with `action="allow"` and `input_category="in_domain"`.

## Local Verification

- Commands run:
  - `& "services\api\.venv\Scripts\pytest.exe" services/api/tests/unit/test_agent_guardrails_input.py` → 32 passed in 0.25s
  - `& "services\api\.venv\Scripts\pytest.exe" services/api/tests/unit/test_agent_guardrails_*.py services/api/tests/integration/test_agent_guardrails_observability.py` → 60 passed in 0.71s
  - `& "services\api\.venv\Scripts\pytest.exe" services/api/tests/integration/test_agent_memory_lifecycle.py services/api/tests/integration/test_agent_routes.py services/api/tests/unit/test_agent_workflow.py` → 73 passed in 3.83s
- Manual checks: Verified that empty/whitespace queries cleanly pass intake validation directly to `STANDARD_REFUSAL_MESSAGE` without false out-of-domain triggers.

## Deviations from Assessment

None. The fix strictly implemented the preferred remediation described in the assessment.

## Follow-ups

- Run `/speckit-bug-test slug=input-guardrail-domain-scope` to perform end-to-end bug verification against all acceptance criteria.
