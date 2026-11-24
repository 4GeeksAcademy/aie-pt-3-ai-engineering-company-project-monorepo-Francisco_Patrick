# Bug Verification: Guardrail Lexical Signal Decoupling & Academic/Medical Context Filtering

- **Slug**: guardrail-lexical-intent-decoupling
- **Tested**: 2026-11-23
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The bug no longer reproduces: queries containing surface logistics collocations disguised within academic, scientific, historical, or veterinary/medical contexts are now reliably deflected. All 28 dedicated unit tests and the 302-test guardrail regression suite passed with zero regressions.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `cd services/api; uv run python -c "..."` (4 assessment cases) | pass | All 4 reproduction cases deflected with OUT_OF_DOMAIN_ACADEMIC_AND_HISTORICAL or OUT_OF_DOMAIN_MEDICAL_AND_VETERINARY |
| New / updated tests | `cd services/api; uv run pytest tests/unit/test_agent_guardrails_input.py -k TestGuardrailLexicalIntentDecoupling` | pass | 28 passed in 0.27s (Block A control, Block B adversarial, genuine logistics, semantic router) |
| Regression suite | `cd services/api; uv run pytest tests/unit/test_agent_guardrails_input.py tests/unit/test_agent_guardrails_authorization.py tests/unit/test_agent_guardrails_context_isolation.py tests/unit/test_agent_guardrails_output.py` | pass | 302 passed in 2.49s across all guardrail subsystems |
| Lint / type-check | `uv run ruff / uv run mypy` | not-run | Ruff and mypy are not installed or configured in the api virtual environment |

## Output Excerpts

### Post-Fix Reproduction Execution
```text
pallet in ancient history: action=deflect, reason=OUT_OF_DOMAIN_ACADEMIC_AND_HISTORICAL, category=out_of_domain
pallet in veterinary/anatomy: action=deflect, reason=OUT_OF_DOMAIN_MEDICAL_AND_VETERINARY, category=out_of_domain
shipping claim in historical research: action=deflect, reason=OUT_OF_DOMAIN_ACADEMIC_AND_HISTORICAL, category=out_of_domain
crates in veterinary protocol: action=deflect, reason=OUT_OF_DOMAIN_MEDICAL_AND_VETERINARY, category=out_of_domain
ALL 4 REPRODUCTION CASES DEFLECTED SUCCESSFULLY
```

### New Tests (`TestGuardrailLexicalIntentDecoupling`)
```text
tests\unit\test_agent_guardrails_input.py ............................   [100%]
=============== 28 passed, 252 deselected, 2 warnings in 0.27s ================
```

### Full Guardrails Regression Suite
```text
tests\unit\test_agent_guardrails_input.py .............................. [  9%]
........................................................................ [ 33%]
........................................................................ [ 57%]
........................................................................ [ 81%]
..................................                                       [ 92%]
tests\unit\test_agent_guardrails_authorization.py ..........             [ 96%]
tests\unit\test_agent_guardrails_context_isolation.py ....               [ 97%]
tests\unit\test_agent_guardrails_output.py ........                      [100%]
======================= 302 passed, 2 warnings in 2.49s =======================
```

## Residual Risks

- Future domain extensions in TrackFlow that introduce specialized freight categories (e.g., live animal transport or museum artifacts) must define explicit positive operational collocations or order schemas to ensure they are not caught by the broad academic or veterinary out-of-domain patterns.

## Recommendation

Close the bug — verified end-to-end. The lexical cue conflation has been eliminated, polysemic/adversarial non-commercial queries are strictly deflected, and legitimate operational queries remain 100% permitted.
