# Bug Assessment: Guardrail Bypass via Polysemic Logistics Keywords in Out-of-Domain Queries

- **Slug**: guardrail-polysemic-keyword-bypass
- **Created**: 2026-11-23
- **Source**: Empirical guardrail effectiveness evaluation (15 out-of-the-box adversarial prompts)
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> In empirical robustness testing using 15 out-of-the-box queries designed to test guardrail effectiveness with permitted domain keywords (e.g., "warehouse", "carrier", "transit", "inventory", "package"), 9 out of 15 queries (60%) bypassed the input guardrail (`InputGuardrailValidator`) with `action="allow"` and `input_category="in_domain"`.
> 
> Queries concerning television series ("Warehouse 13"), pop art history ("Andy Warhol's warehouse / The Factory"), astrophysics ("transit of an exoplanet"), military history ("carrier pigeons in WWI"), board games ("Catan resource inventory"), architecture ("Bauhaus warehouse design"), video games ("Death Stranding package weight limits"), telecommunications ("RF carrier wave modulation"), and quantum mechanics ("entangled particles in transit") were incorrectly categorized as valid TrackFlow customer support inquiries because standalone keywords were matched unconditionally in Tier 5 without requiring logistical phrase collocations or semantic support intent.

## Symptom

When a user submits an out-of-domain query that contains polysemic or cross-disciplinary keywords that also exist in TrackFlow's domain vocabulary (such as `"warehouse"`, `"carrier"`, `"transit"`, `"tránsito"`, `"inventario"`, `"package"`, `"paquete"`), `InputGuardrailValidator.evaluate_input` classifies the request as `action="allow"`, `decision="allow"`, `input_category="in_domain"`, and `reason_code="IN_DOMAIN_ALLOWED"`.

**Expected behavior:** Non-logistics queries must be deflected at Layer 1 with `action="deflect"`, `input_category="out_of_domain"`, and `reason_code="OUT_OF_DOMAIN_DEFLECTION"` (or a specific domain subcategory), returning the neutral TrackFlow logistics deflection message and preventing unnecessary LLM inference and RAG retrieval.

## Reproduction

1. In the `services/api` directory, execute Python via `uv run`:
   ```python
   from application.services.agent_guardrails import InputGuardrailValidator

   validator = InputGuardrailValidator()

   # Case 1: Pop culture / Sci-Fi television series containing "Warehouse"
   res1 = validator.evaluate_input("En la serie de televisión Warehouse 13, ¿qué poderes tiene el artefacto de Nikola Tesla?")
   # Observed: res1.action == "allow", res1.input_category == "in_domain", res1.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res1.action == "deflect", res1.input_category == "out_of_domain"

   # Case 2: Astrophysics / Planetary science containing "tránsito" (transit)
   res2 = validator.evaluate_input("En astrofísica, ¿cómo se detectan exoplanetas observando el tránsito de una estrella?")
   # Observed: res2.action == "allow", res2.input_category == "in_domain", res2.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res2.action == "deflect", res2.input_category == "out_of_domain"

   # Case 3: Military history / Biology containing "carrier"
   res3 = validator.evaluate_input("¿Cómo se entrenaban las palomas carrier en la Primera Guerra Mundial para enviar mensajes?")
   # Observed: res3.action == "allow", res3.input_category == "in_domain", res3.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res3.action == "deflect", res3.input_category == "out_of_domain"

   # Case 4: Video gaming containing "paquete" (package)
   res4 = validator.evaluate_input("En el videojuego Death Stranding, ¿cuál es el peso máximo que Sam Porter puede cargar en un paquete?")
   # Observed: res4.action == "allow", res4.input_category == "in_domain", res4.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res4.action == "deflect", res4.input_category == "out_of_domain"

   # Case 5: Board games containing "inventario" (inventory)
   res5 = validator.evaluate_input("En el juego de mesa Catan, ¿cuántas cartas de materia prima componen el inventario total del banco?")
   # Observed: res5.action == "allow", res5.input_category == "in_domain", res5.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res5.action == "deflect", res5.input_category == "out_of_domain"
   ```

2. All 5 cases bypass Layer 1 input validation and pass directly to `intake_node` in the LangGraph agent workflow (`services/api/application/services/agent_workflow.py`), initiating vector search and generating out-of-scope responses.

## Suspected Code Paths

- `services/api/application/services/agent_guardrails.py:410-455` (`_IN_DOMAIN_LOGISTICS_CUES`):
  Matches isolated standalone terms such as:
  - `\b(?:warehouse|warehousing|almac[eé]n|almacenes)\b`
  - `\b(?:carrier|carriers|transportista|transportistas)\b`
  - `\b(?:transit|in\s+transit|tr[aá]nsito|en\s+tr[aá]nsito)\b`
  - `\b(?:package|packages|paquete|paquetes)\b`
  - `\b(?:inventory|inventario|stock|existencias)\b`
  without requiring surrounding operational context (e.g. order tracking, shipping status, facility address, or customer delivery issues).
- `services/api/application/services/agent_guardrails.py:326-394` (`_OUT_OF_DOMAIN_PATTERNS`):
  Only catches narrow sub-domains: weather, basic geography, dining/restaurants, movies/cinema, and executive personal metrics. It does not include patterns for video games, tabletop games, scientific/quantum physics, telecommunications/electronics, architecture theory, or TV series.
- `services/api/application/services/agent_guardrails.py:683-712` (`InputGuardrailValidator.evaluate_input` Tier 5):
  Evaluates `is_direct_in_domain = bool(_IN_DOMAIN_TRACKFLOW_CUE.search(cleaned) or ...)` directly after Tier 3. Any query that contains an in-domain word but evades the specific negative regexes is unconditionally classified as `IN_DOMAIN_ALLOWED`.

## Root Cause Hypothesis

The root cause is a structural asymmetry in Layer 1 evaluation: `_IN_DOMAIN_LOGISTICS_CUES` uses broad, unanchored lexical matches for common polysemic nouns (`carrier`, `transit`, `warehouse`, `inventory`, `package`), while `_OUT_OF_DOMAIN_PATTERNS` attempts an open-ended enumeration of negative topics. Because the vocabulary of human inquiry outside corporate logistics is virtually unbounded (gaming, physics, RF electronics, art history, biology), relying on a whitelist of single words without syntactic collocations or intent boundaries inevitably yields high false positive rates (`IN_DOMAIN_ALLOWED`) for adversarial and out-of-the-box queries.

Confidence: High.

## Proposed Remediation

**Preferred**:
1. **Require Collocation & Operational Intent for Ambiguous Keywords**:
   - Refactor `_IN_DOMAIN_LOGISTICS_CUES` so that polysemic terms like `warehouse`, `carrier`, `transit`, `inventory`, and `package` are only matched when paired with customer operations, shipping terms, or demonstratives/possessives. For example:
     - Instead of standalone `\bwarehouse\b`, match `\b(?:(?:our|the|this|trackflow|zaragoza|los\s+angeles)\s+warehouse|warehouse\s+(?:location|address|hours|pickup|operations|stock|inventory)|almac[eé]n\s+(?:central|de|en|zaragoza))\b`.
     - Instead of standalone `\bcarrier\b`, match `\b(?:carrier\s+(?:assigned|status|delay|tracking|rates?)|transportista\s+(?:asignado|de))\b`.
     - Instead of standalone `\b(?:transit|tr[aá]nsito)\b`, match `\b(?:(?:in|en)\s+transit|tr[aá]nsito\s+hacia|tr[aá]nsito\s+del\s+env[ií]o)\b` and exclude astronomical/physical phrases.
     - Instead of standalone `\b(?:package|paquete)\b`, match `\b(?:(?:my|your|the|this)\s+package|paquete\s+(?:perdido|dañado|retrasado|entregado)|package\s+(?:tracking|status|delayed|lost))\b`.
2. **Expand Negative Out-of-Domain Categories in Tier 3**:
   - Add negative patterns for video games, gaming, and interactive entertainment: `\b(?:videojuego|video\s+game|gameplay|playstation|xbox|nintendo|death\s+stranding|board\s+game|juego\s+de\s+mesa|catan)\b`.
   - Add negative patterns for sciences & engineering disciplines when not related to consumer delivery: `\b(?:exoplanet|astrof[ií]sica|astronomy|cu[aá]ntica|quantum|radiofrecuencia|carrier\s+wave|modulaci[oó]n|ondas?|onda\s+portadora)\b`.
   - Add negative patterns for television series & fictional shows: `\b(?:serie\s+de\s+televisi[oó]n|tv\s+show|tv\s+series|warehouse\s+13)\b`.

**Alternatives**:
- *Alternative 1 (Embedding-based Semantic Centroid Gate)*: Run cosine similarity against TrackFlow logistics domain centroids (`shipment tracking`, `returns & refunds`, `delivery incidents`) before passing Tier 5. Queries with cosine similarity below a calibrated threshold (e.g., < 0.65) default to deflection even if keyword hits occur.
  *Trade-off*: Adds minimal embedding latency (~15ms) to Layer 1, but completely eliminates regex-stuffing vulnerabilities.

**Files likely to change**:
- `services/api/application/services/agent_guardrails.py`
- `services/api/tests/unit/test_agent_guardrails_input.py`

**Tests to add or update**:
- Add unit test cases in `test_agent_guardrails_input.py`:
  - Verify out-of-domain queries containing `warehouse`, `carrier`, `transit`, `package`, `inventory` are deflected (`action="deflect"`).
  - Verify genuine customer logistics queries containing those words continue to pass (`action="allow"`).

## Risks & Considerations

- **False Negatives on Legitimate Colloquial Support**: When restricting single words like `warehouse` or `package`, ensure legitimate questions like `"Can I visit the warehouse?"` or `"Is the warehouse open on Saturdays?"` or `"Where is the package?"` remain allowed.
- **Bilingual Symmetry**: Regex updates must be mirrored symmetrically across English and Spanish.

## Open Questions

- Should Layer 1 integrate a lightweight embedding check or continue refining deterministic regex heuristics?
