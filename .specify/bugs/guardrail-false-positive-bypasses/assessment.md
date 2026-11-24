# Bug Assessment: Guardrail False Positive Bypass Remediation & Intent Disambiguation

- **Slug**: guardrail-false-positive-bypasses
- **Created**: 2026-11-23
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

The bypass rate dropped from **84% to 24%** (from 42 down to 12 failures out of 50 queries), with 38 queries intercepted (`OUT_OF_DOMAIN_DEFLECTION`). However, 12 bypasses (`IN_DOMAIN_ALLOWED`) remain, clustering into three failure patterns:

1. **Logistics-Formatted IDs & References (`TRK-33901`, `#552194`, `ticket #120993`, `TF-44128` -> #47, #48, #49, #50):**
   - Incomplete neutralization of ID fast-paths across prefixes (`TRK-`, `TF-`, `#`) or excessive weight assigned to reference signals.
2. **Logistics Collocations Used in Literal or Cross-Disciplinary Senses (`in transit`, `the package`, `this box`, `cold-chain`, `physical inventory` -> #2, #5, #7, #9, #14, #18):**
   - Scientific, aerospace, acoustic, or metaphorical usages ("audio packets are in transit", "probe is in transit to Jupiter", "inside the package espacial", "this box acústica", "cold-chain preservation") match regex/embeddings without requiring actionable commercial freight/shipping intent.
3. **Positive Bias on Polysemous Terms (`lost nuances` -> #27, `this workshop` -> #35):**
   - Isolated terms like `lost` or `this workshop` trigger domain cues.

## Symptom

Queries from non-logistics disciplines (e.g. aerospace, archaeology, marine biology, acoustics, art history) that contain spoofed tracking/ticket reference prefixes (`TRK-`, `TF-`, `#`) or literal/metaphorical collocations (`in transit`, `the package`, `this box`, `cold-chain`, `lost`, `this workshop`) are erroneously approved as `IN_DOMAIN_ALLOWED` (action `allow`), failing to deflect to `OUT_OF_DOMAIN_DEFLECTION`.

## Reproduction

1. **Reproduction Case 1: Spoofed ID pattern in non-logistics inquiry**
   ```python
   from application.services.agent_guardrails import InputGuardrailValidator

   guard = InputGuardrailValidator()
   query = "In matter of claim TRK-33901: What archaeological protocols govern damaged Roman pottery?"
   res = guard.evaluate_input(query)
   # Observed: res.action == "allow", res.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res.action == "deflect", res.reason_code in ("OUT_OF_DOMAIN_DEFLECTION", "OUT_OF_DOMAIN_SEMANTIC_ROUTER", "OUT_OF_DOMAIN_LLM_JUDGE")
   ```

2. **Reproduction Case 2: Cross-disciplinary physical/metaphorical collocation**
   ```python
   query = "What orbital maneuver reduces fuel while a probe is in transit to Jupiter?"
   res = guard.evaluate_input(query)  # Matches `in transit` in _IN_DOMAIN_LOGISTICS_CUES
   # Observed: res.action == "allow", res.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res.action == "deflect"
   ```

3. **Reproduction Case 3: Polysemous keyword match without operational context**
   ```python
   query = "Can you analyze the lost nuances in translation for this 14th century poem?"
   res = guard.evaluate_input(query)  # Matches bare `lost` in _IN_DOMAIN_LOGISTICS_CUES
   # Observed: res.action == "allow", res.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res.action == "deflect"
   ```

## Suspected Code Paths

- [agent_guardrails.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/application/services/agent_guardrails.py#L420-L460): `_ORDER_REFERENCE_PATTERNS`, `_OPERATIONAL_LOGISTICS_ACTIONS`, and `_CONCISE_ORDER_QUERY_PATTERN` define reference detection and boost triggers. Overly broad action lists (e.g. bare `lost`, `incident`) or regex combinations allow spoofed IDs through when paired with non-commercial questions.
- [agent_guardrails.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/application/services/agent_guardrails.py#L494-L565): `_IN_DOMAIN_LOGISTICS_CUES` includes unconstrained terms such as `\b(?:lost|perdido|...)\b`, loose collocations for `in transit`, `this box`, `the package`, `cold-chain`, and `workshop` without strict commercial logistics scoping.
- [agent_guardrails.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/application/services/agent_guardrails.py#L807-L875): `InputGuardrailValidator.evaluate_input` determines `has_order_boost` and `is_direct_in_domain`. It allows queries to bypass deflection if lexical cues match, before routing ambiguous queries to Stage 2 / Stage 3.
- [agent_guardrails.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/application/services/agent_guardrails.py#L454-L478): `SEMANTIC_JUDGE_SYSTEM_PROMPT` lacks explicit cross-disciplinary negative few-shot examples and strict domain disambiguation rules for the Stage 3 LLM judge.

## Root Cause Hypothesis

1. **ID Fast-Path Leakage**: The heuristic `has_order_boost` activates on `_OPERATIONAL_LOGISTICS_ACTIONS` which includes broad words like `lost`, `claim`, `incident`, and `status`. Consequently, queries like `"In matter of claim TRK-33901: What archaeological protocols govern damaged Roman pottery?"` trigger `has_order_boost = True` because of the co-occurrence of `claim` + `TRK-33901`, even though the core subject is archaeology.
2. **Polysemy & Loose Collocations**: `_IN_DOMAIN_LOGISTICS_CUES` matches standalone words like `lost` (line 532) and loose phrases like `in transit` (line 512), `cold-chain` (line 547), and `this box` (line 518) without requiring commercial logistics freight context (e.g. carrier, shipment, TrackFlow, parcel delivery, warehouse inventory).
3. **Absence of Strict Cross-Disciplinary Disambiguation in Stage 3 Prompt**: When inputs reach the semantic judge, the prompt lacks explicit instructions and negative few-shot examples directing the judge to discard tracking numbers and logistics terms embedded in academic, scientific, artistic, or legal contexts.

## Proposed Remediation

**Preferred**:
1. **Neutralize ID / Reference Fast-Paths**:
   - Refactor ID pattern boosting in Stage 1: An ID pattern (`ORD-`, `TRK-`, `TF-`, `#\d+`, `ticket #`) must never grant immediate `IN_DOMAIN_ALLOWED` unless the query is strictly a concise single-turn ID submission (e.g. `^#?ORD-12345$`) or is paired with an unambiguous commercial logistics action in an active authenticated session.
   - Separate broad polysemous words (`lost`, `claim`, `incident`) from `_OPERATIONAL_LOGISTICS_ACTIONS`.
2. **Refine Collocation & Polysemy Matching**:
   - Remove standalone `lost` / `perdido` from `_IN_DOMAIN_LOGISTICS_CUES` (require collocation with `package`, `shipment`, `parcel`, `order`, `delivery`, `paquete`, `envío`, `pedido`).
   - Restrict `in transit` / `en tránsito` to commercial cargo/shipment collocations or verify absence of cross-disciplinary markers (astronomy, acoustics, networking).
   - Purge `workshop` or restrict strictly to repair/service context if applicable.
   - Collocate `this box` / `the package` to require logistics modifiers or verbs.
3. **Upgrade `SEMANTIC_JUDGE_SYSTEM_PROMPT`**:
   - Incorporate the proposed strict classification rules and negative few-shot examples (space probes, Roman pottery, humpback whales, aerospace payloads).
   - Enforce JSON output format with `intent`, `domain_detected`, and `reason`.
4. **Expand Regression Test Battery**:
   - Add the 12 bypass cases and full 100-query adversarial suite into `services/api/tests/unit/test_agent_guardrails_input.py`.
   - Maintain the 50 legitimate control query test suite to verify false-negative rate stays <= 2%.

**Files likely to change**:
- `services/api/application/services/agent_guardrails.py`
- `services/api/tests/unit/test_agent_guardrails_input.py`

**Tests to add or update**:
- Add unit tests for the 12 identified bypass queries to guarantee deflection (`OUT_OF_DOMAIN_DEFLECTION` / `OUT_OF_DOMAIN_LLM_JUDGE`).
- Add tests verifying legitimate control queries containing overlapping vocabulary (`cold-chain`, `package damaged in transit under TRK-33901`, `warehouse physical inventory discrepancy`) remain allowed (`IN_DOMAIN_ALLOWED`).

## Risks & Considerations

- **False Negative Regression**: Over-tightening regexes for `in transit` or `package` could deflect legitimate customer support questions. Must continuously run the 50 legitimate control queries in CI to safeguard the <= 2% threshold.
- **Latency Impact**: Pushing borderline queries out of deterministic Stage 1 into Stage 2/Stage 3 increases evaluation latency for those specific inputs, but maintains sub-30ms performance for clearly in-domain and clearly out-of-domain traffic.

## Open Questions

- None. The 12 bypass categories and the 4-phase remediation plan are clearly defined.
