# Bug Verification: Input Guardrail Out-of-Domain Detection & Cue Enforcement

- **Slug**: input-guardrail-domain-scope
- **Tested**: 2026-11-22T00:18:00+01:00
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The bug no longer reproduces: out-of-domain queries (e.g. general trivia, geography, photosynthesis, weather) are blocked deterministically at Layer 1 and redirected to TrackFlow logistics scope rather than leaking into RAG or failing as internal knowledge refusals. All new unit tests and the 84-test regression suite pass cleanly with zero regressions.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `$env:PYTHONPATH="services/api;services/api/tests"; python -c "<eval queries & SupportAgentService turn>"` | pass | `evaluate_input` blocks out-of-domain queries (`OUT_OF_DOMAIN_TASK`), and `SupportAgentService.query` short-circuits to `['intake', 'refusal']` returning standard refusal. |
| New / updated tests | `& "services\api\.venv\Scripts\pytest.exe" services/api/tests/unit/test_agent_guardrails_input.py` | pass | 32 passed in 0.30s. Covers out-of-domain blocking and in-domain/colloquial allowances. |
| Regression suite | `& "services\api\.venv\Scripts\pytest.exe" services/api/tests/unit/test_agent_guardrails_*.py services/api/tests/integration/test_agent_guardrails_observability.py services/api/tests/integration/test_agent_routes.py services/api/tests/unit/test_agent_workflow.py` | pass | 84 passed in 3.52s across guardrail authorization, context isolation, output guardrails, workflow, and API routes. |
| Lint / type-check | `& "services\api\.venv\Scripts\python.exe" -m py_compile services/api/application/services/agent_guardrails.py services/api/tests/unit/test_agent_guardrails_input.py` | pass | Byte-compilation succeeded with zero errors. |

## Output Excerpts

### Post-Fix Reproduction Check
```text
q1 ('what is the capital of France?'): block personal_task OUT_OF_DOMAIN_TASK
q2 ('explain photosynthesis'): block personal_task OUT_OF_DOMAIN_TASK
q3 ('what is the weather in Paris like'): block personal_task OUT_OF_DOMAIN_TASK

SupportAgentService turn:
node_sequence: ['intake', 'refusal']
is_refusal: True
answer: "I cannot help with personal tasks, essays, homework, programming code, or topics unrelated to TrackFlow logistics. My purpose is strictly to assist TrackFlow B2B and B2C customers with shipment tracking, return policies and SLAs (United States and Spain), and delivery incidents (lost packages, failed deliveries, or address issues). How can I help you with a TrackFlow shipment or return today?"
```

### New & Updated Tests
```text
services\api\tests\unit\test_agent_guardrails_input.py ................................ [100%]
======================= 32 passed, 2 warnings in 0.30s =======================
```

### Monorepo Regression Suite
```text
services\api\tests\unit\test_agent_guardrails_input.py ................................ [ 38%]
services\api\tests\unit\test_agent_guardrails_authorization.py ..........               [ 50%]
services\api\tests\unit\test_agent_guardrails_context_isolation.py ....                 [ 54%]
services\api\tests\unit\test_agent_guardrails_output.py ........                        [ 64%]
services\api\tests\integration\test_agent_guardrails_observability.py ......            [ 71%]
services\api\tests\integration\test_agent_routes.py ...........                         [ 84%]
services\api\tests\unit\test_agent_workflow.py .............                            [100%]
======================= 84 passed, 2 warnings in 3.52s =======================
```

## Residual Risks

- Highly domain-adjacent questions that use novel jargon not yet present in `_IN_DOMAIN_TRACKFLOW_CUE` or `_IN_DOMAIN_LOGISTICS_CUES` could trigger a false rejection. However, the bilingual regex covers tracking numbers, couriers (UPS, FedEx, DHL, MRW, SEUR), SLAs, return windows, incidents, inventory SKUs (`TF-xxx`), and conversational confirmations.

## Recommendation

Close the bug — verified end-to-end. Layer 1 intake guardrails enforce the TrackFlow domain boundary deterministically without regressions across the agent workflow and test suites.
