# Bug Assessment: Guardrail Bypass via Lexical Signal Conflation and Missing Academic/Medical Context Filtering

- **Slug**: guardrail-lexical-intent-decoupling
- **Created**: 2026-11-23
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> Separar señales léxicas de decisión final (allow): Que aparezca shipping claim, pallet o in transit no debería ser suficiente para aprobar una consulta si el tema principal es ajeno a la logística comercial de TrackFlow.
>
> Penalizar o filtrar contextos claramente académicos, científicos, históricos o médicos/veterinarios cuando no hay una acción operativa sobre TrackFlow (rastrear un envío real, consultar tarifas de un servicio, gestionar una incidencia o contrato del negocio).
>
> Evaluar por bloques en tus pruebas: Mide por separado la tasa de bypass en preguntas con colocaciones logísticas camufladas frente a preguntas sin colocaciones. Así verás si el problema está en una regla concreta (como \bpallet\b en la línea 554) o en que el clasificador cede ante frases logísticas dentro de contextos no logísticos.

## Symptom

When a user submits queries set in non-commercial contexts (academic, scientific, historical, or medical/veterinary) that embed surface logistics words or collocations (such as bare `pallet`, `crates`, `shipping claim`, or `in transit`), `InputGuardrailValidator.evaluate_input` conflates the presence of lexical keywords with legitimate commercial intent, immediately returning:
- `action="allow"`
- `decision="allow"`
- `input_category="in_domain"`
- `reason_code="IN_DOMAIN_ALLOWED"`

**Expected behavior:**
Surface lexical cues must be decoupled from the final authorization decision (`allow`). Queries whose primary topic is academic, scientific, historical, or medical/veterinary must be penalized and deflected to `action="deflect"` (`input_category="out_of_domain"`), unless there is an authentic operational action on TrackFlow (e.g. tracking a real order/shipment, quoting shipping rates for a business service, managing an active delivery incident, or consulting a commercial logistics contract).

## Empirical Block Evaluation (Pruebas por Bloques)

A comparative evaluation was executed against `InputGuardrailValidator` comparing two distinct test batteries across identical non-logistics domains (history, veterinary/medicine, cellular biology, organic chemistry):

### Block A: Non-logistics queries WITHOUT disguised logistics cues (Control)
Queries in academic, historical, medical, and scientific fields with zero logistics keywords:
1. *"How do historians analyze ancient Egyptian burial rituals in the Valley of the Kings?"* -> `[DEFLECT]` (`OUT_OF_DOMAIN_DEFLECTION`)
2. *"What is the standard treatment protocol for canine parvovirus in veterinary clinics?"* -> `[DEFLECT]` (`OUT_OF_DOMAIN_DEFLECTION`)
3. *"Explain the chemical synthesis of benzene from acetylene in organic chemistry."* -> `[DEFLECT]` (`OUT_OF_DOMAIN_DEFLECTION`)
4. *"What caused the collapse of the Bronze Age civilizations in the Mediterranean?"* -> `[DEFLECT]` (`OUT_OF_DOMAIN_DEFLECTION`)
5. *"How do mRNA vaccines stimulate the adaptive immune system against spike proteins?"* -> `[DEFLECT]` (`OUT_OF_DOMAIN_DEFLECTION`)
6. *"Can you explain the historical timeline of the French Revolution between 1789 and 1799?"* -> `[DEFLECT]` (`OUT_OF_DOMAIN_DEFLECTION`)
7. *"What surgical techniques are used in veterinary orthopedic surgery for feline fractures?"* -> `[DEFLECT]` (`OUT_OF_DOMAIN_DEFLECTION`)
8. *"How does CRISPR-Cas9 perform targeted gene editing in mammalian stem cells?"* -> `[DEFLECT]` (`OUT_OF_DOMAIN_SCIENCE_AND_ENGINEERING`)
9. *"What archaeological methods determine the carbon date of prehistoric stone tools?"* -> `[DEFLECT]` (`OUT_OF_DOMAIN_SCIENCE_AND_ENGINEERING`)
10. *"What are the pathophysiological mechanisms of type 2 diabetes mellitus in adult patients?"* -> `[DEFLECT]` (`OUT_OF_DOMAIN_DEFLECTION`)

**Block A Bypass Rate: 0/10 (0.0% bypass, 100% deflection)**

---

### Block B: Non-logistics queries WITH disguised logistics cues (Adversarial / Polysemic)
Queries in the same academic, historical, medical, and scientific fields, but incorporating surface logistics tokens (`pallet`, `pallets`, `crates`, `shipping claim`, `in transit`):
1. *"How did ancient Egyptians move heavy stone blocks without using a pallet during pyramid construction?"* -> `[ALLOW]` (`IN_DOMAIN_ALLOWED`) **[BYPASS]**
2. *"In historical archives, what shipping claim documents survive from the 18th century British East India Company?"* -> `[ALLOW]` (`IN_DOMAIN_ALLOWED`) **[BYPASS]**
3. *"When a space probe is in transit to Saturn, what scientific telemetry monitors cosmic radiation?"* -> `[DEFLECT]` (`OUT_OF_DOMAIN_SCIENCE_AND_ENGINEERING`)
4. *"Can a veterinarian diagnose inflammation of the soft pallet in dogs undergoing dental surgery?"* -> `[ALLOW]` (`IN_DOMAIN_ALLOWED`) **[BYPASS]**
5. *"In cell biology, why do centrifuges separate organelles into a dense pallet at the bottom of the tube?"* -> `[ALLOW]` (`IN_DOMAIN_ALLOWED`) **[BYPASS]**
6. *"What archaeological protocols govern an antique shipping claim for sunken Mediterranean shipwrecks?"* -> `[DEFLECT]` (`OUT_OF_DOMAIN_SCIENCE_AND_ENGINEERING`)
7. *"Did Roman merchants build wooden pallets to stack amphorae in the port of Ostia Antica?"* -> `[ALLOW]` (`IN_DOMAIN_ALLOWED`) **[BYPASS]**
8. *"When influenza viral particles are in transit between avian and swine hosts, what genomic mutations occur?"* -> `[DEFLECT]` (`OUT_OF_DOMAIN_SCIENCE_AND_ENGINEERING`)
9. *"How do university historians document the physical inventory of medieval illuminated manuscripts?"* -> `[DEFLECT]` (`OUT_OF_DOMAIN_DEFLECTION`)
10. *"What is the veterinary protocol when pharmaceutical crates containing equine vaccines arrive at an animal shelter?"* -> `[ALLOW]` (`IN_DOMAIN_ALLOWED`) **[BYPASS]**

**Block B Bypass Rate: 6/10 (60.0% bypass)**

### Analysis of the Block Discrepancy
The block evaluation clearly isolates two separate vectors of vulnerability:
1. **Isolated Unanchored Keyword Regex**: The presence of bare `pallet`, `pallets`, `crate`, and `crates` in `_IN_DOMAIN_LOGISTICS_CUES` (line 595) accounts for 5 out of the 6 bypasses (83% of the failures). The parser matches `pallet` even when used for biological pellets/centrifugation, canine oral anatomy ("soft pallet" / palate misspelling), ancient Roman masonry, or veterinary animal shelter crates.
2. **Lexical Conflation with Authorization Decision**: The remaining bypass (`shipping claim` in 18th century archives) demonstrates that even multi-word collocations grant unconditional `allow` access because the classifier equates a lexical match with domain authorization without checking whether the overarching intent is commercial/operational or purely historical/academic.

## Reproduction

1. In `services/api`, run with Python via `uv run`:
   ```python
   from application.services.agent_guardrails import InputGuardrailValidator

   validator = InputGuardrailValidator()

   # Case 1: Unanchored 'pallet' in ancient history
   res1 = validator.evaluate_input(
       "How did ancient Egyptians move heavy stone blocks without using a pallet during pyramid construction?"
   )
   assert res1.action == "deflect"  # FAILS: returns action="allow", reason_code="IN_DOMAIN_ALLOWED"

   # Case 2: Unanchored 'pallet' in veterinary / anatomical context
   res2 = validator.evaluate_input(
       "Can a veterinarian diagnose inflammation of the soft pallet in dogs undergoing dental surgery?"
   )
   assert res2.action == "deflect"  # FAILS: returns action="allow", reason_code="IN_DOMAIN_ALLOWED"

   # Case 3: 'shipping claim' in historical research
   res3 = validator.evaluate_input(
       "In historical archives, what shipping claim documents survive from the 18th century British East India Company?"
   )
   assert res3.action == "deflect"  # FAILS: returns action="allow", reason_code="IN_DOMAIN_ALLOWED"

   # Case 4: Unanchored 'crates' in veterinary protocol
   res4 = validator.evaluate_input(
       "What is the veterinary protocol when pharmaceutical crates containing equine vaccines arrive at an animal shelter?"
   )
   assert res4.action == "deflect"  # FAILS: returns action="allow", reason_code="IN_DOMAIN_ALLOWED"
   ```

2. Each case inappropriately bypasses the input guardrail and is forwarded to downstream nodes and vector stores.

## Suspected Code Paths

- `services/api/application/services/agent_guardrails.py:595`:
  `r"|\b(?:parcel|parcels|bulto|bultos|pallet|pallets|crate|crates)\b"`
  Matches isolated words `pallet`, `pallets`, `crate`, `crates` without requiring logistics collocations (e.g. `pallet storage`, `pallet shipment`, `wooden shipping pallet`, `crates of cargo`).
- `services/api/application/services/agent_guardrails.py:901-905`:
  ```python
  is_direct_in_domain = bool(
      _IN_DOMAIN_TRACKFLOW_CUE.search(cleaned)
      or has_order_boost
  )
  ```
  Immediately marks `is_direct_in_domain = True` purely from a regex hit in `_IN_DOMAIN_TRACKFLOW_CUE`, granting direct passage to `action="allow"` without checking operational intent or penalizing academic/scientific/medical contexts.
- `services/api/application/services/agent_guardrails.py:380-469` (`_OUT_OF_DOMAIN_PATTERNS`):
  Lacks patterns for veterinary medicine, animal surgery, clinical medicine, general historical archives, and academic research queries that do not mention specific pre-existing keywords like `etruscan` or `exoplanet`.
- `services/api/application/services/agent_guardrails.py:482-499` (`_OPERATIONAL_LOGISTICS_ACTIONS`):
  Currently only used to boost `has_order_pattern`, rather than acting as a gating/corroborating requirement for queries containing high-risk ambiguous words or cross-disciplinary academic markers.

## Root Cause Hypothesis

The root cause is a dual architectural flaw:
1. **Unanchored Single-Token Regex Rules**: The pattern `\b(?:parcel|parcels|bulto|bultos|pallet|pallets|crate|crates)\b` permits bare nouns (`pallet`, `crates`) to fire unconditionally. In Spanish and English, `pallet` and `crates` frequently appear in non-logistics contexts (biology centrifugation pellets, dental/anatomical soft palate, veterinary shelters, museum crates, historical construction).
2. **Coupling of Lexical Signals to Final `allow` Decision**: Surface lexical cues (`shipping claim`, `in transit`, `pallet`) are directly treated as sufficient proof of TrackFlow commercial intent. The guardrail architecture lacks a stage that evaluates whether the query contains an **actionable operational intent** (tracking an active shipment, consulting TrackFlow shipping rates, reporting a concrete delivery incident, requesting an RMA return, or managing a 3PL contract) or belongs to an **academic, scientific, historical, or veterinary/medical context** that must be deflected when devoid of TrackFlow operational actions.

Confidence: High.

## Proposed Remediation

**Preferred**:
1. **Require Collocation for `pallet` and `crate`**:
   - Replace bare `\b(?:pallet|pallets|crate|crates)\b` in `_IN_DOMAIN_LOGISTICS_CUES` with anchored collocations (e.g. `\b(?:shipping|wooden|warehouse|freight|storage|cargo)\s+(?:pallets?|crates?)\b`, `\b(?:pallets?|crates?)\s+(?:of\s+(?:goods|cargo|freight|shipment|merchandise|stock)|storage|shipment|dimensions?|count|weight|stacking)\b`, `\b(?:palets?|cajas?\s+de\s+madera)\s+(?:de\s+carga|en\s+almac[eé]n|para\s+env[ií]o)\b`).
2. **Decouple Lexical Signals from Final Authorization (`allow`)**:
   - Introduce an **Academic / Historical / Medical & Veterinary Exclusion Pattern** in `_OUT_OF_DOMAIN_PATTERNS` (e.g., `OUT_OF_DOMAIN_ACADEMIC_AND_HISTORICAL` and `OUT_OF_DOMAIN_MEDICAL_AND_VETERINARY`) covering clinical medicine, veterinary practice, ancient civilizations, historical archives, archaeological research, and academic dissertations.
   - When an academic, scientific, historical, or medical context is detected, **deflect** the query UNLESS a strict operational action on TrackFlow is present (e.g., matching `_OPERATIONAL_LOGISTICS_ACTIONS` with an active order ID or authenticated session context).
3. **Operational Action Gating**:
   - Treat isolated collocations like `shipping claim` or `in transit` in high-risk contexts as insufficient for `allow` unless accompanied by concrete TrackFlow commercial operations (e.g. "submit a shipping claim for order ORD-1234", "track shipment in transit to Zaragoza").
4. **Update FastIntentSemanticRouter**:
   - Align `FastIntentSemanticRouter` with the decoupled operational requirements so Stage 2 also deflects non-operational academic/historical queries containing logistics collocations.

**Alternatives**:
- *Alternative A*: Require an explicit TrackFlow brand cue (`trackflow`, `ORD-`, `TRK-`) for all freight and cargo queries.
  *Trade-off*: Would reject legitimate generic first-turn customer questions like "What are your storage rates per pallet in Los Angeles?".
- *Alternative B*: Invoke Stage 3 LLM Judge on every query containing ambiguous logistics collocations.
  *Trade-off*: Introduces 100-300ms latency overhead and external dependency on queries that can be resolved deterministically.

**Files likely to change**:
- `services/api/application/services/agent_guardrails.py`
- `services/api/tests/unit/test_agent_guardrails_input.py`

**Tests to add or update**:
- Unit tests in `test_agent_guardrails_input.py` measuring:
  - Block A: Continued 0% bypass on pure academic, scientific, historical, medical/veterinary questions.
  - Block B: Deflection (0% bypass) on academic, scientific, historical, and veterinary queries with camouflaged collocations (`pallet`, `crates`, `shipping claim`, `in transit`).
  - True Positives: Preserving 100% allow rate on legitimate TrackFlow commercial operations (e.g. "Do you provide warehouse pallet storage in Los Angeles?", "Report a shipping claim for damaged shipment ORD-88910", "Where is my package in transit?").

## Risks & Considerations

- **Over-deflection of Legitimate B2B Inquiries**: Real customers ask questions like "What are your storage rates per pallet in Los Angeles?" or "We need to ship pharmaceutical crates under refrigeration". The rule must differentiate between general commercial operations (rates, warehouses, storage, shipping) and academic/historical/veterinary research.
- **Spelling Variations**: Queries may use `palet`, `palets`, `pallet`, `pallets`. Collocations should accommodate both English and Spanish phrasing without matching "palate" (anatomical).

## Open Questions

- Should customer queries about shipping live animals or veterinary supplies be explicitly deflected as an unsupported commodity under TrackFlow's freight terms, or referred to customer support with a specific policy message?
