# Bug Verification: Guardrail Bypass via Valid Logistics Collocations in Alien Semantic Domains

- **Slug**: guardrail-semantic-intent-bypass
- **Tested**: 2026-11-23T16:21:00+01:00
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The bug no longer reproduces: all five out-of-domain queries combining alien disciplines with valid logistics collocations are cleanly deflected at Layer 1 and Stage 2 with `action="deflect"` and `input_category="out_of_domain"`. All new and existing guardrail regression suites passed with zero failures.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `uv run python -c "..."` (evaluating the 5 cross-disciplinary queries from `assessment.md`) | pass | All 5 cases (archaeology, space/Mars, BSL-4 virology, NATO ordnance, art masterworks) deflected with `OUT_OF_DOMAIN_*` codes |
| New / updated tests | `uv run pytest tests/unit/test_agent_guardrails_input.py -k "guardrail_semantic_intent_bypass or fast_intent_semantic_router or wires_semantic_router" -v` | pass | 7 passed in 0.11s (5 parameterized reproduction cases, semantic router classification, DI wiring) |
| Regression suite | `uv run pytest tests/unit/test_agent_guardrails_input.py tests/unit/test_agent_guardrails_authorization.py tests/unit/test_agent_guardrails_output.py tests/unit/test_agent_guardrails_context_isolation.py tests/unit/test_dependencies.py` | pass | 276 passed in 1.87s across all input, authorization, output, context isolation, and dependency tests |
| Lint / type-check | `uv run ruff check` | not-run | Tooling not installed/configured in `services/api/pyproject.toml` |

## Output Excerpts

### Post-fix Reproduction Execution
```text
[Arch] action=deflect, cat=out_of_domain, code=OUT_OF_DOMAIN_ANTIQUITIES_AND_ARCHAEOLOGY
[Mars] action=deflect, cat=out_of_domain, code=OUT_OF_DOMAIN_SPACE_EXPLORATION
[Biohazard] action=deflect, cat=out_of_domain, code=OUT_OF_DOMAIN_BIOHAZARD_AND_PATHOGENS
[NATO] action=deflect, cat=out_of_domain, code=OUT_OF_DOMAIN_MILITARY_AND_WARFARE
[Art] action=deflect, cat=out_of_domain, code=OUT_OF_DOMAIN_ANTIQUITIES_AND_ARCHAEOLOGY
SUCCESS
```

### New / Updated Unit Tests
```text
tests/unit/test_agent_guardrails_input.py::TestCascadingSemanticGuardrailAndAdversarialDeflection::test_reproduction_cases_guardrail_semantic_intent_bypass_deflected[...] PASSED [ 71%]
tests/unit/test_agent_guardrails_input.py::TestCascadingSemanticGuardrailAndAdversarialDeflection::test_fast_intent_semantic_router_direct_classification PASSED [ 85%]
tests/unit/test_agent_guardrails_input.py::TestCascadingSemanticGuardrailAndAdversarialDeflection::test_input_guardrail_dep_wires_semantic_router PASSED [100%]
================ 7 passed, 245 deselected, 2 warnings in 0.11s ================
```

### Broader Regression Suite
```text
tests\unit\test_agent_guardrails_input.py .............................. [ 10%]
...
tests\unit\test_agent_guardrails_authorization.py ..........             [ 94%]
tests\unit\test_agent_guardrails_output.py ........                      [ 97%]
tests\unit\test_agent_guardrails_context_isolation.py ....               [ 99%]
tests\unit\test_dependencies.py ..                                       [100%]
======================= 276 passed, 2 warnings in 1.87s =======================
```

## Residual Risks

- **Novel cross-domain vocabulary**: Queries utilizing vocabulary from niche fields not yet indexed in `_OUT_OF_DOMAIN_PATTERNS` (e.g., deep-sea oceanography, subatomic particle physics) could theoretically still bypass Stage 1 if they embed TrackFlow logistics collocations, though the Stage 2 `FastIntentSemanticRouter` provides a fallback layer.
- **B2B Cold-Chain False Positives**: Over-broad biosecurity terms could potentially match future specialized pharmaceutical cold-chain medical inquiries if biological keywords are used without standard cold-chain phrasing.

## Recommendation

Close the bug — verified end-to-end. The fix comprehensively resolves the vulnerability without introducing regressions to valid commercial logistics and customer support queries.
