# Bug Verification: Guardrail False Negatives on Open Ticket Queries and False Positive Bypass on Carrier History

- **Slug**: guardrail-ticket-domain-scoping
- **Tested**: 2026-11-24
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The post-fix reproduction confirms that all 9 open/pending support ticket queries are now recognized as in-domain (`action="allow"`, `input_category="in_domain"`) and all 6 FedEx corporate history/founding trivia queries are deflected pre-execution (`action="deflect"`, `input_category="out_of_domain"`). The full input and output guardrail test suites (322 unit tests across `test_agent_guardrails_input.py` and `test_agent_guardrails_output.py`, including 100 adversarial polysemic/injection cases and 50 legitimate controls) pass with zero regressions.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `python -c "from application.services.agent_guardrails import InputGuardrailValidator; ..."` | pass | 9/9 open ticket queries allowed (`in_domain`); 6/6 FedEx history/founding queries deflected (`out_of_domain`). |
| New / updated tests | `python -m pytest tests/unit/test_agent_guardrails_input.py -k "TestGuardrailTicketAndCarrierHistoryDomainScoping" -v` | pass | 21/21 parametrized cases passed in 0.21s (11 English/Spanish open/pending ticket queries + 10 carrier corporate history/founding trivia queries). |
| Regression suite | `python -m pytest tests/unit/test_agent_guardrails_input.py tests/unit/test_agent_guardrails_output.py -q` | pass | 322/322 guardrail unit tests passed (301 input guardrail tests + 21 output guardrail tests). Note: 6 pre-existing failures in `test_agent_workflow.py` due to unauthenticated session fixtures introduced in earlier commit `f20c658` were observed and confirmed unrelated to this fix. |
| Lint / type-check | `python -m py_compile application/services/agent_guardrails.py tests/unit/test_agent_guardrails_input.py` | pass | Bytecode compilation clean (`PY_COMPILE_EXIT: 0`); `ruff` / `mypy` are not installed in the local Python environment (`not-run` for external CLI linters). |

## Output Excerpts

```text
REPRODUCTION_VERIFIED: 9/9 ticket queries allowed (in_domain), 6/6 carrier history queries deflected (out_of_domain)

tests/unit/test_agent_guardrails_input.py::TestGuardrailTicketAndCarrierHistoryDomainScoping::test_open_and_pending_support_ticket_queries_are_allowed[can you check open tickets-en] PASSED [  4%]
...
tests/unit/test_agent_guardrails_input.py::TestGuardrailTicketAndCarrierHistoryDomainScoping::test_open_and_pending_support_ticket_queries_are_allowed[ver mis tickets pendientes-es] PASSED [ 52%]
tests/unit/test_agent_guardrails_input.py::TestGuardrailTicketAndCarrierHistoryDomainScoping::test_carrier_history_and_founding_trivia_queries_are_deflected[whats the history of FedEx-en] PASSED [ 57%]
...
tests/unit/test_agent_guardrails_input.py::TestGuardrailTicketAndCarrierHistoryDomainScoping::test_carrier_history_and_founding_trivia_queries_are_deflected[¿quién fundó DHL?-es] PASSED [100%]
=============== 21 passed, 280 deselected, 2 warnings in 0.21s ================

PY_COMPILE_EXIT: 0
```

## Residual Risks

- Bare third-party carrier tokens (`fedex`, `ups`, `dhl`, `mrw`, `seur`, `usps`) remain in `_IN_DOMAIN_LOGISTICS_CUES` to support short carrier inquiries, relying on `_OUT_OF_DOMAIN_PATTERNS` to intercept corporate trivia (history, founding, origins, stock price, market cap, ticker symbol, CEO, net worth). Novel corporate trivia phrasings not matching those out-of-domain patterns could still match the carrier cue if no semantic vector similarity fallback overrides them.
- `test_agent_workflow.py` contains 6 pre-existing test failures expecting legacy unauthenticated order/ticket lookup behavior prior to session authorization checks introduced in commit `f20c658`.

## Recommendation

Close the bug — verified end-to-end across both `InputGuardrailValidator` and `FastIntentSemanticRouter` with post-fix reproduction and 322 passing guardrail unit tests.
