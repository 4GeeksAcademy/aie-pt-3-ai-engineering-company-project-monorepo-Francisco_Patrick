# Bug Assessment: RFP Generators Ignore Feedback Content and Fabricate Non-KB Rates

- **Slug**: rfp-feedback-and-fabricated-rates
- **Created**: 2026-11-24T11:31:00+01:00
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> The actual generators do not incorporate the feedback; they merely add a static "Revision Note." I generated the "warehouse" section with feedback in iteration 2, yet the content is identical to that of iteration 1 (minus the note). Furthermore, the new test only verifies canonical texts that were already present. Additionally, they continue to invent rates not specified in the briefing—specifically, 5.20/9.60 EUR (or $6.40/$11.80) for "last mile" and 2.40/3.90 EUR per unit for "reverse" logistics. Such rates should either be marked as "Pending confirmation" or be pulled from the Knowledge Base (KB). Please apply the feedback to the content and remove these fabricated rates.

## Symptom

1. **Generators ignore `feedback_for_generator` and only append a static Revision Note**:
   When `WarehouseGeneratorAgent`, `LastMileGeneratorAgent`, or `ReverseLogisticsGeneratorAgent` is invoked on `iteration > 1` with `feedback_for_generator`, the generated body (sections 1–4) is identical to the `iteration = 1` output. The generators merely append a hardcoded `### 5. Revision Note (Attempt X)` block at the bottom without modifying or repairing the draft body in response to the specific compliance, relevance, or readability feedback provided.
2. **Feedback loop test only asserts pre-existing canonical strings**:
   In `tests/pipelines/test_rfp_feedback_loop.py` (`test_real_generators_actively_consume_feedback_on_revision`), the test only calls `generate(..., iteration=2)` and checks for `"Revision Note (Attempt 2)"`, `"90%"`, `"16.00 EUR por m³"`, `"Miguel Torres"`, and `"Pendiente"`—all of which (except the static revision note header) were already present in `iteration=1`. It does not compare `iteration=1` vs. `iteration=2` body content or verify that specific evaluator feedback actually alters the main draft content.
3. **Fabricated rates not grounded in the BRIEFING or Knowledge Base (KB)**:
   - **Last Mile**: `FALLBACK_BRIEFING_STANDARDS["lastmile"]["rates"]` and `LastMileGeneratorAgent.generate` hardcode fabricated parcel rates (`5.20 EUR` / `$6.40 USD` for standard parcel and `9.60 EUR` / `$11.80 USD` for express parcel). None of the KB documents (`trackflow-carrier-coverage.es.md`, `trackflow-sla-delivery.es.md`, `trackflow-BRIEFING.es.md`) publish per-parcel client shipping rates (moreover, `5.20` appears in `docs/supplier-directory/trackflow-BRIEFING.es.md` as an internal carrier rate, which `RULE-CARRIER-RATES` prohibits exposing).
   - **Reverse Logistics**: `FALLBACK_BRIEFING_STANDARDS["reverse"]["rates"]` and `ReverseLogisticsGeneratorAgent.generate` hardcode fabricated per-unit rates (`2.40 EUR` / `$2.80 USD` for return inspection and `3.90 EUR` / `$4.50 USD` for refurbishment/repack). `docs/company-knowledge-base/trackflow-returns-policy.es.md` does not publish per-unit inspection or refurbishment fees (and explicitly states that TrackFlow does not refurbish or resell products on its own account, and that return shipping costs are borne by the client brand unless caused by TrackFlow error).
   - **Warehouse setup fee**: `FALLBACK_BRIEFING_STANDARDS["warehouse"]["rates"]` also includes a hardcoded `onboarding_fee` (`1,350.00 EUR` / `$1,500.00 USD`) not present in `docs/company-knowledge-base/trackflow-storage-pricing.es.md` (which only defines `16 EUR/m³` in Zaragoza, `18 USD/m³` in Los Ángeles, a 30-day free grace period, and a 150% long-term storage fee after 180 days).

## Reproduction

1. **Inspect identical body across iterations**:
   Run `WarehouseGeneratorAgent().generate(rfp_metadata, section_context, iteration=1)` and compare it with `WarehouseGeneratorAgent().generate(rfp_metadata, section_context, feedback_for_generator="[RELEVANCE] Address the following missing Part 1 key aspects in the proposal section: special_handling, pallet_storage_required.", iteration=2)`. Strip the trailing `### 5. Revision Note (Attempt 2)` block from the second output: the remaining text is character-for-character identical to iteration 1.
2. **Inspect the unit test in `tests/pipelines/test_rfp_feedback_loop.py:122-193`**:
   Observe that `test_real_generators_actively_consume_feedback_on_revision` never generates an iteration 1 baseline or passes a non-compliant/incomplete context that gets repaired in the body during iteration 2.
3. **Inspect hardcoded rates in `data/pipelines/rfp_intake/rfp_generator_agents.py:28-78, 282, 388-392, 494-498`**:
   Compare `FALLBACK_BRIEFING_STANDARDS` against `docs/company-knowledge-base/trackflow-storage-pricing.es.md`, `trackflow-carrier-coverage.es.md`, `trackflow-sla-delivery.es.md`, and `trackflow-returns-policy.es.md`. Observe the fabricated `5.20 EUR` / `9.60 EUR` (`$6.40 USD` / `$11.80 USD`) last-mile rates, `2.40 EUR` / `3.90 EUR` (`$2.80 USD` / `$4.50 USD`) reverse logistics rates, and `1,350.00 EUR` / `$1,500.00 USD` onboarding fee.

## Suspected Code Paths

- `data/pipelines/rfp_intake/rfp_generator_agents.py:22-85` — `FALLBACK_BRIEFING_STANDARDS` defines fabricated rates for `lastmile` (`$6.40 USD`, `$11.80 USD`, `5.20 EUR`, `9.60 EUR`), `reverse` (`$2.80 USD`, `$4.50 USD`, `2.40 EUR`, `3.90 EUR`), and `warehouse` (`onboarding_fee`: `$1,500.00 USD`, `1,350.00 EUR`).
- `data/pipelines/rfp_intake/rfp_generator_agents.py:205-319` — `WarehouseGeneratorAgent.generate` renders a static template regardless of `feedback_for_generator` and only appends a static `### 5. Revision Note` on lines 308–317.
- `data/pipelines/rfp_intake/rfp_generator_agents.py:329-426` — `LastMileGeneratorAgent.generate` renders fabricated parcel rates on lines 390–391 and only appends a static `### 5. Revision Note` on lines 416–424.
- `data/pipelines/rfp_intake/rfp_generator_agents.py:436-533` — `ReverseLogisticsGeneratorAgent.generate` renders fabricated per-unit inspection/repack rates on lines 496–497 and only appends a static `### 5. Revision Note` on lines 522–531.
- `tests/pipelines/test_rfp_feedback_loop.py:122-193` — `test_real_generators_actively_consume_feedback_on_revision` only verifies static canonical strings already present in iteration 1.
- `tests/pipelines/test_compliance_rules.py:47, 50, 96`, `tests/pipelines/test_rfp_compliance_failures.py:28`, `tests/pipelines/test_rfp_iteration_cap.py:64` — Test fixtures referencing the old `5.20 EUR`, `$6.40 USD`, and `2.40 EUR` strings.

## Root Cause Hypothesis

When addressing the previous bug assessment (`rfp-generation-canonical-feedback`), the storage rate (`16.00 EUR/m³` and `$18.00 USD/m³`), canonical `90%` SLA, and Miguel Torres volume discount governance were updated in `FALLBACK_BRIEFING_STANDARDS`, and a static `### 5. Revision Note` block was added when `feedback_for_generator and iteration > 1`. However:
1. The hardcoded rate dictionaries for `lastmile` (`5.20`/`9.60 EUR`, `$6.40`/`$11.80 USD`), `reverse` (`2.40`/`3.90 EUR`, `$2.80`/`$4.50 USD`), and warehouse `onboarding_fee` were left untouched in `FALLBACK_BRIEFING_STANDARDS` instead of being replaced with KB-derived policies or `"Pending confirmation"` (`"Pendiente de confirmación"`).
2. None of the three generator classes parse or apply `feedback_for_generator` to mutate the body sections (Sections 1–4) on `iteration > 1`. As a result, the body text before Section 5 is invariant across iterations.
3. The newly added test `test_real_generators_actively_consume_feedback_on_revision` only asserted the presence of canonical tokens on `iteration=2` without checking that the main draft body actually changed compared to `iteration=1` or responded to the specific feedback directives.

Confidence: **High**.

## Proposed Remediation

**Preferred**:

1. **Remove all fabricated rates and ground pricing strictly in the Knowledge Base or mark as "Pending confirmation"**:
   - **Warehouse (` FALLBACK_BRIEFING_STANDARDS["warehouse"]` & `WarehouseGeneratorAgent`)**:
     - Retain the canonical KB storage rates from `trackflow-storage-pricing.es.md`: `16.00 EUR por m³ al mes (Zaragoza)` and `$18.00 USD por m³ al mes (Los Ángeles)`, 30-day free grace period for new inventory, 150% long-term storage tariff after 180 days without movement, and preferential rates for >50 m³ subject to Miguel Torres approval.
     - Remove the fabricated `onboarding_fee` (`$1,500.00 USD` / `1,350.00 EUR`) or replace it with `"Pending confirmation (Pendiente de confirmación en EUR/USD según alcance de integración)"` unless dynamically extracted from KB snippets.
   - **Last Mile (`FALLBACK_BRIEFING_STANDARDS["lastmile"]` & `LastMileGeneratorAgent`)**:
     - Remove the fabricated `5.20 EUR` / `9.60 EUR` and `$6.40 USD` / `$11.80 USD` parcel rates.
     - Pull any rate/service rules available from KB snippets (`trackflow-carrier-coverage.es.md` and `trackflow-sla-delivery.es.md`: Standard 3–5 business days, Express 24–48h in LA/Zaragoza-Madrid metro areas, International 7–12 business days; carriers UPS/FedEx/DHL in US and MRW/SEUR/DHL + 2 local carriers in Zaragoza) and explicitly mark per-parcel monetary rates (`standard_parcel`, `express_parcel`) as `"Pending confirmation (Pendiente de confirmación de tarifa final en {currency} según peso, destino y urgencia; sin revelar tarifas internas de transportistas)"`.
     - Ensure `{currency}` (`EUR` or `USD`, or a canonical reference format without conflicting currency symbols) is clearly stated in the pricing section and volume discount table so `validate_rule_currency` continues to pass.
   - **Reverse Logistics (`FALLBACK_BRIEFING_STANDARDS["reverse"]` & `ReverseLogisticsGeneratorAgent`)**:
     - Remove the fabricated `2.40 EUR` / `3.90 EUR` and `$2.80 USD` / `$4.50 USD` per-unit rates.
     - Ground the returns cost section in `trackflow-returns-policy.es.md`: return shipping costs are assumed by the client brand (unless caused by a TrackFlow error such as transit damage or wrong delivery), TrackFlow does not refurbish or resell on its own account, and per-unit return inspection / processing tariffs in `{currency}` are marked as `"Pending confirmation (Pendiente de confirmación de tarifa en {currency} según reglas de la marca cliente)"`.

2. **Actively apply `feedback_for_generator` to modify the draft body in `iteration > 1`**:
   - Introduce a shared helper method on `BaseDepartmentGeneratorAgent` (or per-department body transformation logic) that parses `feedback_for_generator` (as well as any non-compliant overrides in `rfp_metadata` / `section_context`) and actively modifies Sections 1–4 of the draft when `feedback_for_generator` is provided:
     - **`RULE-CURRENCY` feedback**: If `rfp_metadata` or `section_context` injected a conflicting currency or symbol in iteration 1 (or if feedback flags `RULE-CURRENCY`), strip/replace any foreign currency mentions in the body and enforce the mandatory currency for `client_country`.
     - **`RULE-SLA` feedback**: If `section_context` had a non-canonical SLA override or missing SLA in iteration 1 (or if feedback flags `RULE-SLA`), update Section 2 in the body to explicitly commit to the canonical `90%` on-time delivery SLA and include the 5% monthly fee compensation clause from `trackflow-sla-delivery.es.md`.
     - **`RULE-RETURNS-TIME` feedback**: If `section_context` requested or injected a `< 48h` return turnaround (e.g., `24 hours` in `key_aspects` or notes) or feedback flags `RULE-RETURNS-TIME`, sanitize any sub-48h promises in Sections 1–3 and replace them in-place with the mandatory `48 to 72 hours` minimum turnaround commitment.
     - **`RULE-DISCOUNT-TIERS` feedback**: Reinforce the Volume Discount Table in Section 3 with explicit Miguel Torres approval requirements for >50 m³ and multi-tier volume discounts.
     - **`RULE-CARRIER-RATES` feedback**: Scrub any leaked carrier rate figures or internal cost mentions from the body and replace with `"Pending confirmation (final client rate in {currency})"`.
     - **`[RELEVANCE]` feedback (missing `key_aspects` or `open_questions_coverage`)**: Parse missing aspect keys from `feedback_for_generator` (e.g. `Address the following missing Part 1 key aspects in the proposal section: <keys>`) or custom feedback instructions and inject dedicated remediation sentences directly into Section 1 (`Space and Stock Plan` / `Carrier Plan` / `Return Window and Inspection Flow`) and Section 4 (`Open Questions`), ensuring the body itself changes substantively.
     - **`[READABILITY]` feedback**: Adjust sentence structure/conciseness in Sections 1–3 when readability feedback requests simplification or expansion.
     - **Freeform evaluator/human feedback**: Incorporate specific directives from `feedback_for_generator` directly into the relevant body sections (Sections 1–3) so that comparing iteration 1 body vs. iteration 2 body (even excluding Section 5) demonstrates concrete content updates.

3. **Strengthen unit tests in `tests/pipelines/test_rfp_feedback_loop.py` and `tests/pipelines/test_rfp_generators.py`**:
   - Update `test_real_generators_actively_consume_feedback_on_revision` to:
     1. Generate `draft_iter_1` (`iteration=1`) and `draft_iter_2` (`iteration=2` with `feedback_for_generator`).
     2. Strip any `Revision Note` section and assert that `body_iter_2 != body_iter_1` and that the specific feedback items (e.g., repairing a non-compliant override or addressing missing relevance aspects/feedback details) are present inside the main body of `draft_iter_2`.
     3. Test end-to-end recovery with a real generator in `RFPResponseGenerationPipeline` where iteration 1 fails evaluation (e.g. due to a non-compliant `section_context` override such as a 24h return request or missing aspect) and iteration 2 passes because the real generator modifies the body using `feedback_for_generator`.
   - Add assertions in `tests/pipelines/test_rfp_generators.py` verifying that none of the fabricated rates (`5.20`, `9.60`, `6.40`, `11.80`, `2.40`, `3.90`, `2.80`, `4.50`, `1,350.00`, `1,500.00`) appear in any generated draft, and that unconfirmed rates are explicitly marked as `"Pending confirmation"` / `"Pendiente de confirmación"`.

**Files likely to change**:
- `data/pipelines/rfp_intake/rfp_generator_agents.py`
- `tests/pipelines/test_rfp_feedback_loop.py`
- `tests/pipelines/test_rfp_generators.py`
- `tests/pipelines/test_rfp_compliance_failures.py` (if fixture text needs cleanup, though negative test fixtures may intentionally use arbitrary prices)

**Tests to add or update**:
- `tests/pipelines/test_rfp_feedback_loop.py::test_real_generators_actively_consume_feedback_on_revision` — compare iteration 1 vs. iteration 2 body content (excluding the revision note) across `WarehouseGeneratorAgent`, `LastMileGeneratorAgent`, and `ReverseLogisticsGeneratorAgent`, verifying that feedback actually changes the draft body and fixes compliance/relevance gaps.
- `tests/pipelines/test_rfp_generators.py` — assert absence of fabricated rates (`5.20`, `9.60`, `6.40`, `11.80`, `2.40`, `3.90`, `2.80`, `4.50`) and presence of `"Pending confirmation"` / `"Pendiente de confirmación"` for unpublished last-mile and reverse logistics rates.

## Risks & Considerations

- **`RULE-CURRENCY` regex sensitivity (`compliance_rules.py:104-115`)**:
  `validate_rule_currency` checks for `\bUSD\b`, `\$\s*\d`, `\bEUR\b`, or `€\s*\d`. For `lastmile` and `reverse`, once numeric fabricated rates like `$6.40 USD` or `5.20 EUR` are removed in favor of `"Pending confirmation"`, the draft still contains `\bUSD\b` or `\bEUR\b` (in the header, rates section, and discount table), which satisfies `re.search(r"\bUSD\b", text)` / `re.search(r"\bEUR\b", text)`. Care must be taken not to include both `EUR` and `USD` in the same draft (e.g., avoid writing `"Pendiente en EUR/USD"` literally; use `f"Pending confirmation in {currency}"`).
- **Readability score stability (`evaluate_readability`)**:
  `textstat.flesch_reading_ease` must remain between `30.0` and `95.0` with at least `25` words after removing fabricated rates and after applying feedback mutations in iteration 2.

## Open Questions

- None. The Knowledge Base files (`trackflow-storage-pricing.es.md`, `trackflow-carrier-coverage.es.md`, `trackflow-sla-delivery.es.md`, `trackflow-returns-policy.es.md`) and `trackflow-BRIEFING.es.md` clearly define which rates exist in the KB (only storage `16 EUR/m³` in Zaragoza and `18 USD/m³` in Los Ángeles) and which rates must be marked as `"Pending confirmation"` unless pulled from the KB.
