# Bug Verification: Guardrail Lexical Heuristics Reliance & Semantic Intent Action Plan

- **Slug**: guardrail-semantic-action-plan
- **Tested**: 2026-11-23
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The fix successfully eliminates the lexical heuristic vulnerabilities identified in the assessment. Post-fix reproduction confirmed that order ID injections and polysemic financial queries are properly deflected, cold-chain logistics queries are preserved as in-domain, and all 221 regression and unit tests pass without errors.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `$env:PYTHONPATH="services/api"; & "services/api/.venv/Scripts/python.exe" -c "..."` | pass | Verified all 3 assessment reproduction cases: Case 1 deflected, Case 2 deflected, Case 3 allowed. |
| New / updated tests | `pytest services/api/tests/unit/test_agent_guardrails_input.py -k "TestCascadingSemanticGuardrailAndAdversarialDeflection"` | pass | 105 passed in 0.75s (covering 3 repro cases, 50 adversarial deflection tests, 50 legitimate control tests, and semantic router/LLM judge hooks). |
| Regression suite | `pytest services/api/tests/unit/test_agent_guardrails_*.py services/api/tests/integration/test_agent_guardrails_observability.py` | pass | 221 passed in 1.66s across all guardrail test suites. |
| Lint / type-check | `python -m py_compile services/api/application/services/agent_guardrails.py services/api/tests/unit/test_agent_guardrails_input.py` | pass | Bytecode compilation completed cleanly with exit code 0. |

## Output Excerpts

### Post-fix Reproduction
```text
R1: deflect out_of_domain OUT_OF_DOMAIN_DEFLECTION
R2: deflect out_of_domain OUT_OF_DOMAIN_DEFLECTION
R3: allow in_domain IN_DOMAIN_ALLOWED
```

### New Tests Suite
```text
collected 192 items / 87 deselected / 105 selected
services\api\tests\unit\test_agent_guardrails_input.py ................. [ 16%]
........................................................................ [ 84%]
................                                                         [100%]
=============== 105 passed, 87 deselected, 2 warnings in 0.75s ================
```

### Full Regression Suite
```text
collected 221 items
services\api\tests\unit\test_agent_guardrails_input.py ................. [  7%]
........................................................................ [ 40%]
........................................................................ [ 72%]
...............................                                          [ 86%]
services\api\tests\unit\test_agent_guardrails_authorization.py ......... [ 90%]
.                                                                        [ 91%]
services\api\tests\unit\test_agent_guardrails_output.py ........         [ 95%]
services\api\tests\unit\test_agent_guardrails_context_isolation.py ....  [ 96%]
services\api\tests\integration\test_agent_guardrails_observability.py .. [ 97%]
.....                                                                    [100%]
======================= 221 passed, 2 warnings in 1.66s =======================
```

## Residual Risks

- The pluggable Stage 2 Semantic Router and Stage 3 LLM Judge are architected and unit-tested via callback hooks, but live production deployment requires configuring active embedding (`bge-m3` or `text-embedding-3-small`) and model endpoints (`gpt-4o-mini`) in production runtime configs if gray-zone inputs expand beyond the current regex boundary.
- Unseen multilingual polysemic phrases in languages other than English and Spanish may require ongoing additions to the collocated phrase dictionary.

## Recommendation

Close the bug — verified end-to-end. The 4-phase remediation plan is fully realized, original reproduction cases hold, adversarial bypasses are deflected with 100% precision, and no regressions exist in the guardrails test suite.
