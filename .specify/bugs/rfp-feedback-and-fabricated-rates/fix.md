# Bug Fix: RFP Generators Ignore Feedback Content and Fabricate Non-KB Rates

- **Slug**: rfp-feedback-and-fabricated-rates
- **Fixed**: 2026-11-24T11:40:00+01:00
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Removed all fabricated non-KB rates (`5.20`/`9.60 EUR` and `$6.40`/`$11.80 USD` for Last Mile, `2.40`/`3.90 EUR` and `$2.80`/`$4.50 USD` for Reverse Logistics, and `1,350.00 EUR`/`$1,500.00 USD` warehouse onboarding fees) in favor of KB-grounded storage rates (`16.00 EUR/m³` in Zaragoza, `$18.00 USD/m³` in Los Ángeles) and `"Pending confirmation"` (`"Pendiente de confirmación"`) for unpublished tariffs. Updated `WarehouseGeneratorAgent`, `LastMileGeneratorAgent`, and `ReverseLogisticsGeneratorAgent` to parse `feedback_for_generator` and actively mutate Sections 1–4 of the draft body on `iteration > 1` (including in-place sanitization of foreign currencies and sub-48h return turnaround promises).

## Changes

| File | Change | Notes |
|------|--------|-------|
| `data/pipelines/rfp_intake/rfp_generator_agents.py` | modified | Replaced fabricated rates in `FALLBACK_BRIEFING_STANDARDS` with `"Pending confirmation"`, added `_extract_kb_rate_or_pending`, `_build_body_feedback_directive`, `_sanitize_foreign_currency_in_text`, and `_sanitize_sub_48h_returns_in_text` so `iteration > 1` actively mutates Sections 1–4 in response to `feedback_for_generator`. |
| `tests/pipelines/test_rfp_feedback_loop.py` | modified | Updated `test_real_generators_actively_consume_feedback_on_revision` to strip `### 5. Revision Note` and assert `body_iter_2 != body_iter_1`, verify body-level compliance/relevance repairs across all three agents, and test end-to-end pipeline recovery using the real `ReverseLogisticsGeneratorAgent`. |
| `tests/pipelines/test_rfp_generators.py` | modified | Added `FABRICATED_RATES` absence assertions across all three generator tests and verified presence of `"Pending confirmation"` / `"Pendiente de confirmación"`. |

## Diff Highlights

```python
# data/pipelines/rfp_intake/rfp_generator_agents.py
"lastmile": {
    "department_name": "Last Mile and Carrier Management",
    "responsible_person": "Carlos Vega",
    "on_time_sla_pct": "90%",
    "rates": {
        "USD": {
            "standard_parcel": "Pending confirmation (Pendiente de confirmación en USD)",
            "express_parcel": "Pending confirmation (Pendiente de confirmación en USD)",
        },
        "EUR": {
            "standard_parcel": "Pending confirmation (Pendiente de confirmación en EUR)",
            "express_parcel": "Pending confirmation (Pendiente de confirmación en EUR)",
        },
    },
    ...
}
```

```python
# Active body modification on iteration > 1 in BaseDepartmentGeneratorAgent
body_mods = self._build_body_feedback_directive(
    feedback_for_generator if iteration > 1 else None,
    currency,
    key_aspects,
)
# Mutates Section 1, Section 2, Section 3, and Section 4 directly and sanitizes
# non-compliant currency or sub-48h turnaround tokens in the draft body.
```

## Tests Added or Updated

- `tests/pipelines/test_rfp_feedback_loop.py::test_real_generators_actively_consume_feedback_on_revision` — compares `iteration=1` vs. `iteration=2` main body content (excluding `### 5. Revision Note`) for `WarehouseGeneratorAgent`, `LastMileGeneratorAgent`, and `ReverseLogisticsGeneratorAgent`, and verifies `RFPResponseGenerationPipeline.run_department_loop` recovers from an iteration 1 `RULE-RETURNS-TIME` failure to an iteration 2 pass using the real `ReverseLogisticsGeneratorAgent`.
- `tests/pipelines/test_rfp_generators.py::test_warehouse_generator_modaviva_spain_eur_draft` — asserts absence of all fabricated rates (`5.20`, `9.60`, `6.40`, `11.80`, `2.40`, `3.90`, `2.80`, `4.50`, `1,350.00`, `1,500.00`) and presence of `"Pending confirmation"` / `"Pendiente de confirmación"`.
- `tests/pipelines/test_rfp_generators.py::test_lastmile_generator_luna_cosmetics_us_usd_draft` — asserts absence of fabricated parcel rates and presence of `"Pending confirmation"` / `"Pendiente de confirmación"`.
- `tests/pipelines/test_rfp_generators.py::test_reverse_generator_enforces_48h_minimum_turnaround` — asserts absence of fabricated per-unit return rates and presence of `"Pending confirmation"` / `"Pendiente de confirmación"`.

## Local Verification

- Commands run: `.\services\api\.venv\Scripts\pytest.exe tests/pipelines/test_compliance_rules.py tests/pipelines/test_rfp_compliance_failures.py tests/pipelines/test_rfp_evaluators.py tests/pipelines/test_rfp_feedback_loop.py tests/pipelines/test_rfp_generators.py tests/pipelines/test_rfp_handoff_packaging.py tests/pipelines/test_rfp_iteration_cap.py tests/pipelines/test_rfp_response_generation.py -v` → `40 passed in 11.84s`
- Manual checks: Verified that stripping `### 5. Revision Note` from iteration 2 drafts across all three generators yields substantive body diffs compared to iteration 1, and confirmed Flesch Reading Ease scores remain within `30.0–95.0`.

## Deviations from Assessment

None.

## Follow-ups

- Run `/speckit-bug-test slug=rfp-feedback-and-fabricated-rates` to record the verification report.
