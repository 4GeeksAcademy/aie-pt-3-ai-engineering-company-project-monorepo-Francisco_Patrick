# Bug Verification: Guardrail Keyword-Matching Bypass via In-Domain Terminology

- **Slug**: guardrail-keyword-bypass
- **Tested**: 2026-11-23
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The guardrail keyword-matching bypass no longer reproduces: out-of-domain queries combining logistics terminology with dining, entertainment/fiction, or executive biographical predicates are now deflected deterministically at Layer 1. All new and existing unit and workflow regression suites passed with zero regressions.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | Direct execution of original reported bypass queries via `InputGuardrailValidator.evaluate_input` | pass | Tested `"how tall is the FedEx CEO?"`, `"what is the meaning of the Order of the Phoenix?"`, `"which restaurant is closest to the warehouse?"`, and Spanish translations; all returned `action="deflect"`, `input_category="out_of_domain"`. Positive logistics controls remained `action="allow"`, `input_category="in_domain"`. |
| New / updated tests | `& "services/api/.venv/Scripts/python.exe" -m pytest services/api/tests/unit/test_agent_guardrails_input.py` | pass | 59 passed in 0.42s, covering all out-of-domain deflection cases and in-domain regression controls. |
| Regression suite | `& "services/api/.venv/Scripts/python.exe" -m pytest services/api/tests/unit/test_agent_guardrails_authorization.py services/api/tests/unit/test_agent_guardrails_context_isolation.py services/api/tests/unit/test_agent_guardrails_input.py services/api/tests/unit/test_agent_guardrails_output.py services/api/tests/unit/test_memory_guardrails.py services/api/tests/unit/test_agent_workflow.py` | pass | 109 passed (96 guardrails + 13 workflow) across all guardrail subsystems and LangGraph workflow orchestration nodes. |
| Lint / type-check | `& "services/api/.venv/Scripts/python.exe" -m py_compile services/api/application/services/agent_guardrails.py` + `test_guardrails_type_annotations_evaluate_cleanly` | pass | Python AST bytecode compilation succeeded with zero syntax errors; runtime type annotations validated cleanly. |

## Output Excerpts

### Reproduction Check
```text
[PASS] 'how tall is the FedEx CEO?' -> action=deflect, cat=out_of_domain, code=OUT_OF_DOMAIN_BIOGRAPHY_OR_PERSONAL
[PASS] 'what is the meaning of the Order of the Phoenix?' -> action=deflect, cat=out_of_domain, code=OUT_OF_DOMAIN_ENTERTAINMENT_OR_FICTION
[PASS] 'which restaurant is closest to the warehouse?' -> action=deflect, cat=out_of_domain, code=OUT_OF_DOMAIN_DINING_OR_HOSPITALITY
[PASS] '¿cuánto mide el CEO de FedEx?' -> action=deflect, cat=out_of_domain, code=OUT_OF_DOMAIN_BIOGRAPHY_OR_PERSONAL
[PASS] '¿qué restaurante queda más cerca del almacén?' -> action=deflect, cat=out_of_domain, code=OUT_OF_DOMAIN_DINING_OR_HOSPITALITY
[PASS] 'When was my FedEx order shipped?' -> action=allow, cat=in_domain, code=IN_DOMAIN_ALLOWED
[PASS] 'What is the address of the Los Angeles warehouse?' -> action=allow, cat=in_domain, code=IN_DOMAIN_ALLOWED
[PASS] 'I want to check the status of my order #45821.' -> action=allow, cat=in_domain, code=IN_DOMAIN_ALLOWED
[PASS] 'How does FedEx handle lost packages?' -> action=allow, cat=in_domain, code=IN_DOMAIN_ALLOWED
ALL_REPRODUCTION_CHECKS_PASSED
```

### Pytest Guardrails Suite
```text
======================= 59 passed, 2 warnings in 0.42s ========================
```

### Pytest Full Guardrail & Workflow Regression Suite
```text
======================= 96 passed, 2 warnings in 0.70s ========================
======================= 13 passed, 2 warnings in 0.30s ========================
```

## Residual Risks

- **Novel Semantic Bypass Variants**: While deterministic regex patterns effectively deflect the reported categories (dining/hospitality, entertainment/fiction, executive biography/trivia), queries utilizing highly esoteric out-of-domain topics without matching Tier 3 regexes could theoretically still reach downstream RAG nodes if they match Tier 5 cues. A semantic embedding classifier could complement regex patterns in future hardening phases.
- **Polysemous Domain Cues in Non-Logistics Contexts**: Nouns like `"order"` have been constrained to specific logistics bigrams/collocations (`"order status"`, `"my order"`, `"order #\d+"`), which prevents false passes for `"Order of the Phoenix"`; however, users formulating ungrammatical or idiosyncratic logistics queries (e.g. `"order I made yesterday"`) must ensure they match the supported collocations or fallback cues.

## Recommendation

Close the bug — verified end-to-end. The fix correctly defiects all reported reproduction cases at Layer 1 with appropriate reason codes and neutral deflection messaging, while preserving seamless access for legitimate customer logistics queries.
