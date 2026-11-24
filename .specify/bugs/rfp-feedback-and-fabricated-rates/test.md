# Bug Verification: RFP Generators Ignore Feedback Content and Fabricate Non-KB Rates

- **Slug**: rfp-feedback-and-fabricated-rates
- **Tested**: 2026-11-24T11:44:30+01:00
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The bug no longer reproduces: all three RFP department generators (`WarehouseGeneratorAgent`, `LastMileGeneratorAgent`, and `ReverseLogisticsGeneratorAgent`) now actively parse `feedback_for_generator` and mutate the main draft body (Sections 1–4) on `iteration > 1`, and all fabricated non-KB tariffs (`5.20`/`9.60 EUR`, `$6.40`/`$11.80 USD`, `2.40`/`3.90 EUR`, `$2.80`/`$4.50 USD`, and `1,350.00 EUR`/`$1,500.00 USD`) have been replaced with Knowledge Base rates (`16.00 EUR/m³` in Zaragoza, `$18.00 USD/m³` in Los Ángeles) or `"Pending confirmation"` (`"Pendiente de confirmación"`). All 40 RFP pipeline regression tests pass without regressions.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | Python verification script comparing `iteration=1` vs. `iteration=2` main draft body (excluding `### 5. Revision Note`) and scanning all three generated sections for fabricated rates | pass | `REPRO_VERIFIED_OK`: `d1 != d2` confirmed with missing key aspects injected into Section 1 body; zero fabricated rates in `warehouse`, `lastmile`, or `reverse` drafts. |
| New / updated tests | `.\services\api\.venv\Scripts\pytest.exe tests/pipelines/test_rfp_feedback_loop.py tests/pipelines/test_rfp_generators.py -v` | pass | `6 passed in 5.04s` (including body diff assertions and real `ReverseLogisticsGeneratorAgent` pipeline recovery). |
| Regression suite | `.\services\api\.venv\Scripts\pytest.exe tests/pipelines/test_compliance_rules.py tests/pipelines/test_rfp_compliance_failures.py tests/pipelines/test_rfp_evaluators.py tests/pipelines/test_rfp_feedback_loop.py tests/pipelines/test_rfp_generators.py tests/pipelines/test_rfp_handoff_packaging.py tests/pipelines/test_rfp_iteration_cap.py tests/pipelines/test_rfp_response_generation.py -v` | pass | `40 passed` across all RFP intake and response generation test modules (70 passed across `tests/pipelines/` overall). |
| Lint / type-check | `.\services\api\.venv\Scripts\python.exe -m py_compile data/pipelines/rfp_intake/rfp_generator_agents.py tests/pipelines/test_rfp_feedback_loop.py tests/pipelines/test_rfp_generators.py` | pass | `PY_COMPILE_EXIT=0` (clean syntax and bytecode compilation across all modified files). |

## Output Excerpts

```text
TEST_MD_ABSENT
REPRO_VERIFIED_OK
============================= test session starts =============================
collecting ... collected 6 items

tests/pipelines/test_rfp_feedback_loop.py::test_feedback_loop_revises_failing_draft_and_passes_on_iteration_2 PASSED [ 16%]
tests/pipelines/test_rfp_feedback_loop.py::test_real_generators_actively_consume_feedback_on_revision PASSED [ 33%]
tests/pipelines/test_rfp_generators.py::test_warehouse_generator_modaviva_spain_eur_draft PASSED [ 50%]
tests/pipelines/test_rfp_generators.py::test_lastmile_generator_luna_cosmetics_us_usd_draft PASSED [ 66%]
tests/pipelines/test_rfp_generators.py::test_reverse_generator_enforces_48h_minimum_turnaround PASSED [ 83%]
tests/pipelines/test_rfp_generators.py::test_factory_get_department_generator_agent PASSED [100%]

============================== 6 passed in 5.04s ==============================
PY_COMPILE_EXIT=0
```

## Residual Risks

- `_extract_kb_rate_or_pending` relies on regex matching against retrieved Knowledge Base chunks when `VectorStorePort` is active; if new tariff formats are added to the KB markdown documents in the future, the regex pattern or structured metadata extraction may need to be expanded (currently degrades safely to `"Pending confirmation"` or the canonical KB storage rate).

## Recommendation

Close the bug — verified end-to-end. Both the body-level feedback consumption across revision iterations and the removal of fabricated non-KB rates are confirmed by direct reproduction and the full 40-test RFP pipeline suite.
