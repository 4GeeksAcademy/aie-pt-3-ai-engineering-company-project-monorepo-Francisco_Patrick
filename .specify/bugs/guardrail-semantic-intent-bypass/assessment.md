# Bug Assessment: Guardrail Bypass via Valid Logistics Collocations in Alien Semantic Domains

- **Slug**: guardrail-semantic-intent-bypass
- **Created**: 2026-11-23
- **Source**: Empirical guardrail boundary evaluation (50 out-of-domain adversarial probes in Batería 3)
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> In empirical boundary testing of the hardened `InputGuardrailValidator` using 50 out-of-the-box adversarial queries designed to probe guardrail limits across diverse non-corporate disciplines (e.g. classical archaeology, lunar exploration, BSL-4 virology, NATO armament logistics, and naval warfare), 20 out of 50 queries (40%) successfully bypassed the input guardrail with `action="allow"` and `input_category="in_domain"`.
>
> While previous remediation hardened single unanchored nouns (`warehouse`, `rates`, `transit`) by requiring multi-word collocations, adversaries can trivially evade detection by formulating queries concerning subjects completely outside TrackFlow's B2B/B2C logistics support scope (such as etruscan pottery fractures, lunar rock sample hermetic seals, live pathogen transport leakage, or Geneva Convention prisoner repatriation) as long as they incorporate authorized logistics collocations such as `"cardboard shipping box"`, `"arrived damaged"`, `"cargo in transit to destination"`, `"delivery incident report"`, `"shipping rates per kg"`, or `"return window"`.
>
> Because Layer 1 relies strictly on lexical regex collocation matching without verifying the semantic intent or target entity domain, and because the cascading Stage 2 Semantic Router and Stage 3 LLM Judge are left unconfigured (`None`) in production dependency injection, the frontline guardrail permits out-of-scope inquiries to reach downstream RAG retrieval and generation.

## Symptom

When a user submits a query regarding non-TrackFlow topics (e.g., biological pathogens, space probe trajectories, museum art pieces, military ordnance) that syntactically includes a valid logistics collocation recognized in `_IN_DOMAIN_LOGISTICS_CUES` (e.g., `"cardboard shipping box"`, `"package is in transit"`, `"cold-chain logistics protocol"`, `"shipping damage claim"`), `InputGuardrailValidator.evaluate_input` classifies the request as:
- `action="allow"`
- `decision="allow"`
- `input_category="in_domain"`
- `reason_code="IN_DOMAIN_ALLOWED"`

**Expected behavior:**
Queries unrelated to TrackFlow's corporate logistics support scope (US/Spain shipment tracking, commercial returns/SLAs, and parcel delivery incidents) must be deflected at Layer 1 with `action="deflect"`, `input_category="out_of_domain"`, and `reason_code="OUT_OF_DOMAIN_DEFLECTION"` (or deflected via the semantic classifier/router), returning the standard deflection message and preventing unnecessary LLM inference and vector database queries.

## Reproduction

1. In `services/api`, run Python via `uv run`:
   ```python
   from application.services.agent_guardrails import InputGuardrailValidator

   validator = InputGuardrailValidator()

   # Case 1: Classical Archaeology / Ancient Pottery
   res1 = validator.evaluate_input(
       "¿Qué medidas de embalaje en a cardboard shipping box previenen la fractura de cerámicas etruscas del siglo IV a.C.?"
   )
   # Observed: res1.action == "allow", res1.input_category == "in_domain", res1.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res1.action == "deflect", res1.input_category == "out_of_domain"

   # Case 2: Deep Space Planetary Exploration (Mars)
   res2 = validator.evaluate_input(
       "How does NASA ensure that sealed scientific cargo in transit to the destination of Mars avoids biological contamination?"
   )
   # Observed: res2.action == "allow", res2.input_category == "in_domain", res2.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res2.action == "deflect", res2.input_category == "out_of_domain"

   # Case 3: Biosafety / Pathogen Transport (BSL-4)
   res3 = validator.evaluate_input(
       "In BSL-4 biosafety laboratories, what dry ice packaging for shipping prevents live virus pathogen leakage?"
   )
   # Observed: res3.action == "allow", res3.input_category == "in_domain", res3.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res3.action == "deflect", res3.input_category == "out_of_domain"

   # Case 4: Military Ordnance Logistics / NATO
   res4 = validator.evaluate_input(
       "¿Qué cláusula de return policy aplica la OTAN a los arsenales de munición obsoleta devuelta por los países miembros?"
   )
   # Observed: res4.action == "allow", res4.input_category == "in_domain", res4.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res4.action == "deflect", res4.input_category == "out_of_domain"

   # Case 5: Art Theft / Maritime Freight Insurance
   res5 = validator.evaluate_input(
       "Under international art heritage law, how are freight contracts with carriers drafted to insure stolen renaissance masterworks?"
   )
   # Observed: res5.action == "allow", res5.input_category == "in_domain", res5.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res5.action == "deflect", res5.input_category == "out_of_domain"
   ```

2. All 5 cases bypass Layer 1 input validation and pass directly to downstream nodes in the LangGraph agent workflow (`agent_workflow.py`), initiating RAG vector search on irrelevant domains.

## Suspected Code Paths

- `services/api/application/services/agent_guardrails.py:528-601` (`_IN_DOMAIN_LOGISTICS_CUES`):
  Evaluates purely lexical surface collocations (such as `cardboard shipping box`, `cargo in transit to destination`, `freight contracts with carriers`, `return policy`, `cold-chain logistics protocol`, `shipping damage claim`). It matches these collocations unconditionally even when the subject matter is clearly extraterrestrial, military, archaeological, or pathogen-related.
- `services/api/application/services/agent_guardrails.py:865-916` (`Cascading Guardrail Architecture: Stages 2 & 3`):
  Stage 2 (`self.semantic_router`) and Stage 3 (`self.llm_judge`) hook logic exists, but both are bypassed because default instances are instantiated with `semantic_router=None` and `llm_judge=None`.
- `services/api/presentation/dependencies.py:350-356` (`get_input_guardrail`):
  Initializes `_input_guardrail_singleton = InputGuardrailValidator()` with no semantic router or LLM judge injected, leaving the frontline agent solely dependent on Stage 1 regex heuristics.
- `services/api/application/services/agent_guardrails.py:350-425` (`_OUT_OF_DOMAIN_PATTERNS`):
  Negative patterns focus on entertainment, dining, basic weather, and narrow gaming terms, but lack domain indicators for military ordnance, planetary space exploration, pathogen virology, or fine art antiquities.

## Root Cause Hypothesis

The root cause is a fundamental limitation of regex-only domain boundary enforcement: surface-level lexical collocations (e.g., *"package arrived damaged"*, *"freight contracts with carriers"*, *"return policy"*) are structurally domain-agnostic and frequently appear across archaeology, defense, aerospace, and biomedical research. When an adversary embeds these permitted logistical collocations into out-of-scope inquiries, Stage 1 regex checks grant immediate passage (`is_direct_in_domain = True`), while Stage 2 and Stage 3 semantic verification layers remain uninstantiated in production dependency injection.

Confidence: High.

## Proposed Remediation

**Preferred**:
1. **Activate Stage 2 Semantic Router in Production**:
   - Provide an embedded, lightweight fast semantic intent router (e.g. using cosine similarity against pre-computed TrackFlow CX intent centroids or a fast embeddings classifier via Qdrant/local model) or configure the pluggable `semantic_router` in `services/api/presentation/dependencies.py`.
   - When Stage 1 matches `_IN_DOMAIN_TRACKFLOW_CUE`, pass queries through Stage 2 verification if the query length exceeds a minimum threshold (e.g. > 60 characters) or contains high-risk cross-disciplinary entity markers.
2. **Expand Negative Out-of-Domain Exclusion Patterns in Stage 1**:
   - Add targeted negative patterns in `_OUT_OF_DOMAIN_PATTERNS` to intercept obvious non-commercial logistics domains:
     - Space exploration: `\b(?:nasa|mars|lunar|moon\s+rocks?|hubble|james\s+webb|orbit|spacecraft|cohete|espacial|sat[eé]lite)\b`
     - Weapons / Military warfare: `\b(?:nato|otan|ammunition|arsenal|warfare|geneva\s+convention|prisioneros\s+de\s+guerra|torpedeamiento|misil|armamento)\b`
     - Antiquities / Archaeology: `\b(?:etruscan|sarc[oó]fago|pharaonic|fara[oó]nico|archaeolog|arqueolog|renaissance\s+masterwork|escultura\s+romana)\b`
     - High-containment biohazard: `\b(?:bsl-4|pathogen|pat[oó]geno|live\s+virus|antidote|antiof[ií]dico|biol[oó]gico\s+peligroso)\b`
   - Ensure negative exclusions retain precedence over Stage 1 in-domain collocation matches.

**Alternatives**:
- *Alternative A*: Require an authenticated session context or explicit order ID match before accepting complex freight/B2B collocations like `freight contracts with carriers` or `cargo in transit to destination`.
- *Alternative B*: Invoke Stage 3 (`llm_judge`) via a lightweight LLM (e.g., Gemini Flash) specifically on turns where Stage 1 passes but no authenticated order or active shipment ID exists in the conversation state.

**Files likely to change**:
- `services/api/application/services/agent_guardrails.py`
- `services/api/presentation/dependencies.py`
- `services/api/tests/unit/test_agent_guardrails_input.py`

**Tests to add or update**:
- Unit tests in `test_agent_guardrails_input.py` covering:
  - Exclusion of non-corporate logistics (space missions, antiquities, BSL-4 virology, military warfare).
  - Verification that valid TrackFlow customer support inquiries with collocations (e.g. "my cardboard shipping box arrived damaged") continue to be allowed without regression.
  - Verification of Stage 2 Semantic Router deflection when enabled.

## Risks & Considerations

- **False Deflections (False Positives in Defense):** Overly aggressive exclusion patterns (e.g., filtering `antivirus` or generic scientific terms) could accidentally deflect legitimate B2B pharmaceutical or tech shipments handled by TrackFlow.
- **Latency Impact:** If Stage 2 or Stage 3 calls an external API or model, latency on the frontline turn could increase by 100-300ms. A local regex + vector centroid threshold check is preferred for sub-10ms response times.

## Open Questions

- Should TrackFlow's CX agent support B2B cold-chain pharmaceutical queries only when associated with an active B2B commercial account session, deflecting anonymous inquiries about general vaccine transport?
