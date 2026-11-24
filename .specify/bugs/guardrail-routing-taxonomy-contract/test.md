# Bug Verification: Guardrail Routing & Fallback Taxonomy Contract

- **Slug**: guardrail-routing-taxonomy-contract
- **Tested**: 2026-11-23
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The bug no longer reproduces: benign out-of-domain queries route cleanly to `action="deflect"`, `input_category="out_of_domain"` with neutral deflection messages instead of returning personal task refusals. All new and existing guardrail tests passed with zero regressions.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `$env:PYTHONPATH="services/api"; python -c "from application.services.agent_guardrails import InputGuardrailValidator; ... evaluate_input('weather in Los Angeles')"` | pass | Returns `action="deflect"`, `decision="deflect"`, `input_category="out_of_domain"`, and polite deflection message without C04 refusal. |
| New / updated tests | `python -m pytest services/api/tests/unit/test_agent_guardrails_input.py services/api/tests/integration/test_agent_guardrails_observability.py -v` | pass | 56 passed (49 unit, 7 integration). Tested 5-tier precedence, multi-turn elliptical continuation, contract taxonomy, and observability logging. |
| Regression suite | `python -m pytest services/api/tests/unit/test_agent_guardrails_authorization.py services/api/tests/unit/test_agent_guardrails_context_isolation.py services/api/tests/unit/test_agent_guardrails_output.py services/api/tests/unit/test_agent_workflow.py services/api/tests/unit/test_intent_classification.py services/api/tests/unit/test_memory_guardrails.py` | pass | 108 passed across authorization, context isolation, output guardrails, workflow orchestration, intent classification, and memory guardrails. |
| Lint / type-check | `python -m py_compile services/api/domain/agent/entities.py services/api/domain/agent/ports.py services/api/application/services/agent_guardrails.py services/api/application/services/guardrail_observability.py services/api/application/services/agent_workflow.py` | pass | Bytecode compilation succeeded with zero syntax or typing errors. (Note: mypy static analyzer executable is not installed in the local virtual environment). |

## Output Excerpts

```text
# Reproduction check
Reproduction check: deflect deflect out_of_domain essay in msg: False

# Unit & Integration Tests
services/api/tests/unit/test_agent_guardrails_input.py
======================= 49 passed, 2 warnings in 0.45s ========================
services/api/tests/integration/test_agent_guardrails_observability.py
======================== 7 passed, 2 warnings in 0.28s ========================

# Regression Test Suite
======================= 108 passed, 2 warnings in 1.03s =======================
```

## Residual Risks

- None identified for in-scope guardrail classification and taxonomy contracts.
- Downstream microservices consuming raw event payloads directly should ensure their schema validators accept the extended `deflected` and `clarified` dispositions.

## Recommendation

Close the bug — verified end-to-end.
