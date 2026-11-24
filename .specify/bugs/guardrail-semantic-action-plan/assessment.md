# Bug Assessment: Guardrail Lexical Heuristics Reliance & Semantic Intent Action Plan

- **Slug**: guardrail-semantic-action-plan
- **Created**: 2026-11-23
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> The core issue in `agent_guardrails.py` is an **over-reliance on lexical heuristics (whitelists and regex)** without semantic intent validation. A guardrail system based on keyword matching will always fail against polysemy and context camouflaging.
> 
> To reduce the bypass rate from **84% to under 2%** without degrading latency or blocking legitimate TrackFlow queries, execute the following four-phase action plan:
> 
> ---
> 
> ### Phase 1: Immediate Critical Patches (Rules & Regex)
> Remove rules that grant automatic "immunity" to a query before evaluating its actual intent.
> * **Downgrade `_ORDER_REFERENCE_PATTERNS` from *Allow* to *Boost*:**
>   * *Current issue:* Detecting `ORD-99214` or `TRK-88123` immediately returns `IN_DOMAIN_ALLOWED` (Tests #46, #47, #48, #50).
>   * *Solution:* Regex patterns for tracking, order, or ticket IDs **must never approve a query on their own**. Convert them into a context signal (*feature*) or use them solely to validate against the live database (if the ID does not exist in TrackFlow, revoke the boost).
> * **Remove Polysemous Nouns from the Level 5 *Whitelist*:**
>   * *Current issue:* Words such as `rates`, `storage`, `contract`, `claim`, `incident`, `ticket`, `box`, and `carrier` approve the query without verifying the domain.
>   * *Solution:* Purge generic terms from deterministic fast-approval rules (`IN_DOMAIN_ALLOWED`). Route them to the semantic classification layer instead.
> * **Disable Keyword-Trap Blocking Rules (`OUT_OF_DOMAIN_WEATHER`):**
>   * *Current issue:* Tests #6, #7, and #29 were mistakenly blocked upon detecting *temperature* or *refrigeration*. In a logistics business (TrackFlow), legitimate questions regarding cold-chain shipping will be falsely blocked by this rule.
>   * *Solution:* Replace single-word blacklists with intent classification, as *temperature* is a valid term in perishable freight transport.
> 
> ---
> 
> ### Phase 2: Cascading Guardrail Architecture (Defense in Depth)
> Restructure `agent_guardrails.py` as a three-stage funnel ordered from lowest to highest computational cost:
> 1. **Fast Filter**: Regex + Strict Heuristics (greetings, profanity, obvious prompt injections, or valid ID + operational verb).
> 2. **Semantic Router**: Embeddings (`text-embedding-3-small` or local `bge-m3`) computing cosine similarity against TrackFlow intent centroids.
> 3. **Lightweight LLM Judge**: Small, fast model (`gpt-4o-mini`, `claude-3-haiku`, or quantized `Llama-3.1-8B`) evaluating actionable intent with structured JSON output.
> 
> ---
> 
> ### Phase 3: Semantic Judge Prompt Design (Stage 3)
> System prompt evaluating user actionable intent rather than superficial keywords, responding exclusively in JSON: `{"intent": "IN_DOMAIN" | "OUT_OF_DOMAIN", "domain_detected": "string", "reason": "string"}`.
> 
> ---
> 
> ### Phase 4: Validation & Regression (CI/CD)
> 1. Integrate 50 adversarial queries into pytest pipeline requiring 100% deflection.
> 2. Create control dataset of 50 legitimate TrackFlow queries requiring >= 98% approval.
> 3. Latency benchmarking: Stage 1 + Stage 2 resolve 70-80% under 30ms; Stage 3 LLM (150-300ms) only for ambiguous queries.

## Symptom

`InputGuardrailValidator.evaluate_input` relies excessively on superficial lexical cues and regex patterns, causing two opposing failure modes:
1. **Adversarial / Out-of-domain Bypass (False Positives in Domain Classification):**
   - Injecting an order/tracking pattern such as `ORD-99214` or `TRK-88123` into any arbitrary prompt (e.g., philosophical questions, coding requests, general biology/history) bypasses domain filtering at lines 724-740 because `any(pattern.search(cleaned) for pattern in _ORDER_REFERENCE_PATTERNS)` directly forces `is_direct_in_domain = True` and grants immediate `IN_DOMAIN_ALLOWED` status.
   - Polysemic and uncollocated nouns in `_IN_DOMAIN_LOGISTICS_CUES` (e.g. `rates`, `contract`, `claim`, `incident`, `ticket`, `box`, `carrier`, `storage`) pass queries when mentioned in non-logistics contexts (e.g., financial interest rates, sports tickets, boxing matches, carrier wave physics).
2. **False Deflections / False Negatives on Legitimate Logistics Inquiries:**
   - Single-word blacklists like `temperature` in `OUT_OF_DOMAIN_WEATHER` (line 331) trigger false `OUT_OF_DOMAIN_WEATHER` deflections on legitimate TrackFlow inquiries regarding cold-chain, pharmaceutical, and refrigerated freight transport (e.g., *"What is the temperature monitoring SLA for cold-chain vaccines?"*).

## Reproduction

1. **Reproduction Case 1: Order ID Lexical Bypass granting automatic immunity:**
   ```python
   from application.services.agent_guardrails import InputGuardrailValidator

   validator = InputGuardrailValidator()
   query = "Tell me about the history of ancient Rome and gladiators. By the way, reference is ORD-99214."
   res = validator.evaluate_input(query)
   # Observed: res.action == "allow", res.input_category == "in_domain", res.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res.action == "deflect", res.input_category == "out_of_domain"
   ```

2. **Reproduction Case 2: Polysemic Noun without operational collocation:**
   ```python
   query = "What are the current interest rates set by the European Central Bank?"
   res = validator.evaluate_input(query)  # Matches \brates\b in _IN_DOMAIN_LOGISTICS_CUES
   # Observed: res.action == "allow", res.input_category == "in_domain"
   # Expected: res.action == "deflect", res.input_category == "out_of_domain"
   ```

3. **Reproduction Case 3: Legitimate Cold-Chain Query Falsely Blocked by Weather Blacklist:**
   ```python
   query = "What is the temperature control requirement for perishable food shipments?"
   res = validator.evaluate_input(query)  # Matches \btemperature\b in OUT_OF_DOMAIN_WEATHER (Tier 3)
   # Observed: res.action == "deflect", res.reason_code == "OUT_OF_DOMAIN_WEATHER"
   # Expected: res.action == "allow", res.input_category == "in_domain", res.reason_code == "IN_DOMAIN_ALLOWED"
   ```

## Suspected Code Paths

- [agent_guardrails.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/application/services/agent_guardrails.py#L326-L336): `_OUT_OF_DOMAIN_PATTERNS["OUT_OF_DOMAIN_WEATHER"]` matches `temperature` without distinguishing meteorological weather from cold-chain freight conditions.
- [agent_guardrails.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/application/services/agent_guardrails.py#L420-L427): `_ORDER_REFERENCE_PATTERNS` detects IDs, which are later evaluated as a sufficient condition for `is_direct_in_domain`.
- [agent_guardrails.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/application/services/agent_guardrails.py#L465-L487): `_IN_DOMAIN_LOGISTICS_CUES` includes unconstrained polysemic tokens such as `rates`, `contract`, `claim`, `incident`, `ticket`, `storage` without requiring operational collocations or intent framing.
- [agent_guardrails.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/application/services/agent_guardrails.py#L722-L750): `InputGuardrailValidator.evaluate_input` executes Level 5 deterministic approval directly if `_ORDER_REFERENCE_PATTERNS` matches, completely lacking a semantic embedding or LLM judge fallback for ambiguous inputs.

## Root Cause Hypothesis

`InputGuardrailValidator` operates strictly as a sequential series of static regex heuristics. There is a lack of semantic intent classification:
1. `_ORDER_REFERENCE_PATTERNS` acts as an absolute pass-through bypass (`is_direct_in_domain = True`), bypassing deflection whenever an ID pattern is present.
2. The weather regex is evaluated in Tier 3 (preceding Tier 5 logistics checks) and uses broad keywords (`temperature`) that capture cold-chain transport queries before domain cues can be assessed.
3. The guardrail architecture lacks a tiered semantic fall-through (Stage 2 semantic embedding similarity router and Stage 3 lightweight LLM judge) to distinguish genuine logistics intent from adversarial keyword camouflaging.

Confidence: **High**.

## Proposed Remediation

**Preferred**: Execute a staged refactoring aligning with the 4-phase action plan:
1. **Immediate Rule & Regex Patches (Phase 1)**:
   - Downgrade `_ORDER_REFERENCE_PATTERNS` so that detecting an ID format alone does not approve a query; require an accompanying operational verb (`track`, `quote`, `cancel`, `locate`, `status`, `where is`, `incidencia`, `rastrear`) or valid session/database context.
   - Refactor polysemous words (`rates`, `storage`, `contract`, `claim`, `incident`, `ticket`, `carrier`) to require logistics collocations (e.g. `freight rates`, `shipping contract`, `delivery incident`, `support ticket`).
   - Narrow `OUT_OF_DOMAIN_WEATHER` by excluding phrases with cold-chain, freight, refrigeration, or perishable goods cues, or checking logistics cold-chain keywords before weather deflection.
2. **Cascading Guardrail Architecture (Phases 2 & 3)**:
   - Introduce an optional semantic router / LLM judge hook in `InputGuardrailValidator` for borderline queries where regex confidence is ambiguous (gray zone).
3. **Automated Test Matrix (Phase 4)**:
   - Implement the 50 adversarial evaluation tests and 50 legitimate control tests in `services/api/tests/unit/test_agent_guardrails_input.py` to ensure $\ge 98\%$ precision and recall.

**Alternatives**:
- *Pure Regex Hardening*: Refine regex rules without adding embedding or LLM stages. *Trade-off*: Zero added latency and no external LLM/embedding dependency, but remains vulnerable to novel polysemic phrasing and adversarial camouflaging.
- *Full LLM Judge for Every Query*: Route 100% of queries through `gpt-4o-mini` or similar. *Trade-off*: Maximizes semantic accuracy, but introduces 150-300ms latency and API costs on trivial queries (greetings, explicit tracking IDs).

**Files likely to change**:
- `services/api/application/services/agent_guardrails.py`
- `services/api/tests/unit/test_agent_guardrails_input.py`
- `services/api/tests/integration/test_agent_guardrails_observability.py`

**Tests to add or update**:
- Unit tests verifying that queries with fake order IDs (`ORD-99214`, `TRK-88123`) embedded in off-topic text (e.g. Roman history, ECB interest rates) are deflected.
- Unit tests verifying that cold-chain inquiries with `temperature` or `refrigeration` are correctly allowed as in-domain.
- Control dataset regression suite covering tricky legitimate logistics vocabulary.

## Risks & Considerations

- **Latency Impact**: Adding embedding or LLM evaluation must be strictly gated to the ambiguous gray zone to preserve sub-30ms execution for deterministic clear-cut cases.
- **Backwards Compatibility**: Downstream tests in `test_agent_guardrails_input.py` that rely on standalone order IDs or concise single-turn ID submissions must remain supported (e.g., when an ID is accompanied by conversational history or explicit tracking intent).
- **Offline / Isolated Execution**: Pytest suite and CI runs must continue functioning without mandatory external network access (mocking or local fallback for any Stage 2/3 classifier).

## Open Questions

- Should Stage 2 (embedding centroid similarity) utilize local embeddings (`bge-m3` or lightweight sentence-transformers) or an API endpoint?
- Does TrackFlow's live database session verification already provide an active session order validation hook inside `InputGuardrailValidator`? (Currently handled downstream in Layer 2 `AuthorizationGuardrailValidator`).
