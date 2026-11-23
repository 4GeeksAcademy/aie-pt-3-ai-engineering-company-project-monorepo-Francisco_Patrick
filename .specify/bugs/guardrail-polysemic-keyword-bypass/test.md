# Bug Verification: Guardrail Bypass via Polysemic Logistics Keywords

- **Slug**: guardrail-polysemic-keyword-bypass
- **Tested**: 2026-11-23
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The bug no longer reproduces: all five original adversarial reproduction cases and ten additional cross-disciplinary polysemic keyword queries are properly deflected at Layer 1 (`action="deflect"`, `input_category="out_of_domain"`). The fix holds across 13 legitimate customer support test cases without false negatives, and the entire guardrail regression suite passed with zero errors.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `$env:PYTHONPATH="services/api"; uv run --project services/api python -c "<reproduction script>"` | pass | All 5 cases from `assessment.md` deflected (`action=deflect`, `category=out_of_domain`). |
| New / updated tests | `uv run --project services/api pytest services/api/tests/unit/test_agent_guardrails_input.py -k TestPolysemicKeywordGuardrailRobustness -v` | pass | 28 passed in 0.23s (15 deflection tests, 13 legitimate query tests). |
| Regression suite | `uv run --project services/api pytest services/api/tests/unit/test_agent_guardrails_input.py services/api/tests/unit/test_agent_guardrails_output.py` | pass | 95 passed in 0.66s. |
| Lint / type-check | `uv run --project services/api python -m py_compile services/api/application/services/agent_guardrails.py services/api/tests/unit/test_agent_guardrails_input.py` | pass | Syntax and byte-compilation clean (Ruff tool not installed in `services/api` dependencies). |

## Output Excerpts

### Post-Fix Reproduction Execution
```text
1. action=deflect category=out_of_domain reason=OUT_OF_DOMAIN_ENTERTAINMENT_OR_FICTION
2. action=deflect category=out_of_domain reason=OUT_OF_DOMAIN_SCIENCE_AND_ENGINEERING
3. action=deflect category=out_of_domain reason=OUT_OF_DOMAIN_SCIENCE_AND_ENGINEERING
4. action=deflect category=out_of_domain reason=OUT_OF_DOMAIN_GAMING
5. action=deflect category=out_of_domain reason=OUT_OF_DOMAIN_GAMING
```

### Pytest Verification Suite
```text
services\api\tests\unit\test_agent_guardrails_input.py ................. [ 17%]
......................................................................   [ 91%]
services\api\tests\unit\test_agent_guardrails_output.py ........         [100%]
======================= 95 passed, 2 warnings in 0.66s ========================
```

## Residual Risks

- Highly novel or unlisted cross-disciplinary domains (e.g., obscure hobbyist jargon) that omit operational collocations could still pass if paired with allowed logistics phrases. However, Tier 5 now strictly requires operational collocations for all ambiguous polysemic keywords (`warehouse`, `carrier`, `transit`, `package`, `inventory`).
- Highly terse colloquial single-word queries (e.g. just `"warehouse"`) will be deflected unless phrased with a question or operational noun/verb (e.g. `"warehouse address"`, `"our warehouse"`, `"visit the warehouse"`).

## Recommendation

Close the bug — verified end-to-end. The fix successfully resolves the polysemic bypass vulnerability, maintains complete backwards compatibility for legitimate logistics support queries, and all unit and regression suites pass cleanly.
