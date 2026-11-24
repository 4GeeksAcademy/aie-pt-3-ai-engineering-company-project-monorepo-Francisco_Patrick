# Bug Assessment: Input Guardrail Out-of-Domain Detection & Cue Enforcement

- **Slug**: input-guardrail-domain-scope
- **Created**: 2026-11-22
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> I dug all the way into the guts of it. I threw in queries like what the capital of France is, asking it to explain photosynthesis, or what the weather in Paris is like. All of them return allow/in_domain, and the agent falls into no_context instead of rejecting and redirecting to TrackFlow. Anything unrelated to shipping, returns, and/or issues should be rejected and redirected. `_IN_DOMAIN_TRACKFLOW_CUE` is defined, yet it's never used.

## Symptom

Queries completely unrelated to TrackFlow logistics (e.g., `"what is the capital of France?"`, `"explain photosynthesis"`, `"what is the weather in Paris like"`, or general trivia/knowledge questions) pass through `InputGuardrailValidator.evaluate_input` with `action="allow"` and `input_category="in_domain"`. 

Because they are falsely classified as in-domain, they proceed into the agent workflow and RAG retrieval pipeline. When no matching knowledge chunk is found, the workflow falls into `refusal_node` (`no_context`), producing an erroneous knowledge refusal:
`"TrackFlow internal documentation does not contain verified policy regarding <topic>. For operational assistance on this topic, please consult the operations leadership directly."`

Instead, per `trackflow-BRIEFING.es.md` (Sections 2, 4, 5) and FR-005, any query unrelated to shipments, returns, and/or delivery incidents is prohibited personal/unrelated chatbot use and must be blocked pre-execution at Layer 1 (`action="block"`, `failure_category="content"`, `input_category="personal_task"`) with the standardized bilingual refusal message redirecting the user back to TrackFlow's logistics scope.

## Reproduction

1. In Python, evaluate out-of-domain queries using `InputGuardrailValidator`:
   ```python
   from application.services.agent_guardrails import InputGuardrailValidator

   validator = InputGuardrailValidator()

   res1 = validator.evaluate_input("what is the capital of France?")
   # Observed: res1.action == "allow", res1.input_category == "in_domain", res1.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res1.action == "block", res1.failure_category == "content", res1.input_category == "personal_task"

   res2 = validator.evaluate_input("explain photosynthesis")
   # Observed: res2.action == "allow", res2.input_category == "in_domain", res2.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res2.action == "block", res2.failure_category == "content", res2.input_category == "personal_task"

   res3 = validator.evaluate_input("what is the weather in Paris like")
   # Observed: res3.action == "allow", res3.input_category == "in_domain", res3.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: res3.action == "block", res3.failure_category == "content", res3.input_category == "personal_task"
   ```

2. Run an end-to-end turn through `SupportAgentService.query` with `"what is the capital of France?"`:
   - Observed response: `"TrackFlow internal documentation does not contain verified policy regarding what the capital of France is. For operational assistance on this topic, please consult the operations leadership directly."`
   - Expected response: `PERSONAL_TASK_REFUSAL_EN` (`"I cannot help with personal tasks, essays, homework, programming code, or topics unrelated to TrackFlow logistics. My purpose is strictly to assist TrackFlow B2B and B2C customers with shipment tracking, return policies and SLAs (United States and Spain), and delivery incidents (lost packages, failed deliveries, or address issues). How can I help you with a TrackFlow shipment or return today?"`).

## Suspected Code Paths

- `services/api/application/services/agent_guardrails.py:278-282`: `_IN_DOMAIN_TRACKFLOW_CUE` is compiled as a regex matching TrackFlow logistics terminology, but it is dead code and never referenced anywhere in `agent_guardrails.py`.
- `services/api/application/services/agent_guardrails.py:338-385` (`InputGuardrailValidator.evaluate_input`):
  - Checks `_JAILBREAK_PATTERNS` (blocks security jailbreaks).
  - Checks `_PERSONAL_TASK_PATTERNS` (only matches specific keywords like essay, homework, python script, therapist, recipe for lasagna).
  - Checks `_CASUAL_TRIVIA_PATTERNS` (matches greetings and reverse logistics/3PL trivia).
  - **Fails open**: Line 378 defaults any unclassified query directly to `action="allow", input_category="in_domain"`, without checking whether the inquiry actually contains domain-relevant cues (shipping, tracking, orders, returns, SLAs, incidents, tickets, inventory, or TrackFlow operations).
- `services/api/application/services/agent_workflow.py:1492-1500` (`refusal_node`): Because `input_guard` allowed the query, zero RAG similarity causes the system to call `build_refusal_message(query)` rather than returning the input guardrail refusal.

## Root Cause Hypothesis

`InputGuardrailValidator.evaluate_input` was implemented with a negative-allowlist ("fail-open") architecture: it only blocks explicit jailbreak patterns and a small, narrow set of personal task keywords (essays, code generation, therapy). Any general out-of-domain query (e.g. geography, science, weather, general trivia) misses all negative filters and falls through to the default return statement at line 378, which unconditionally classifies it as `action="allow"` and `input_category="in_domain"`. Furthermore, `_IN_DOMAIN_TRACKFLOW_CUE` was defined on line 278 to identify domain relevance, but was inadvertently left unused during the implementation of Milestone 8. Confidence: High.

## Proposed Remediation

**Preferred**:
1. Implement a comprehensive in-domain cue pattern (expanding `_IN_DOMAIN_TRACKFLOW_CUE` or defining a robust bilingual `_IN_DOMAIN_LOGISTICS_CUES` pattern) covering:
   - Shipment & tracking: orders, tracking numbers, packages, delivery status, transit, couriers (UPS, FedEx, DHL, MRW, SEUR), dispatch, shipping addresses.
   - Returns & refunds: return windows, refund amounts, restock fees, exchanges, Spain vs US return policies, SLAs.
   - Incidents & claims: lost/damaged packages, failed deliveries, wrong address, support tickets (`INC-xxx`, tickets).
   - Inventory & operations: SKUs (`TF-xxx`), stock levels, warehouse fulfillment (Los Angeles, Zaragoza, Madrid).
   - Brand & entities: TrackFlow, Valentina Cruz, Miguel Torres, Sofía Ramos, Carlos Vega.
2. In `InputGuardrailValidator.evaluate_input`:
   - Keep step 1 (`_JAILBREAK_PATTERNS`) and step 2 (`_PERSONAL_TASK_PATTERNS`) for explicit matches.
   - Keep step 3 (`_CASUAL_TRIVIA_PATTERNS`) for greetings and general logistics trivia.
   - At step 4, check whether the query satisfies the in-domain criteria (matching `_IN_DOMAIN_TRACKFLOW_CUE` / logistics cues, or order reference patterns).
   - If in-domain cues are found, allow the query with `input_category="in_domain"`.
   - If neither in-domain cues nor casual trivia match, treat the query as an out-of-domain personal/unrelated request per FR-005, returning `action="block"`, `failure_category="content"`, `input_category="personal_task"`, `reason_code="OUT_OF_DOMAIN_TASK"`, and the standardized `PERSONAL_TASK_REFUSAL_ES` / `PERSONAL_TASK_REFUSAL_EN` message.

**Alternatives**:
- *Alternative 1*: Route unclassified queries to a small LLM classifier. *Trade-off*: Adds network latency, cost, and non-determinism, violating offline deterministic requirements (FR-013).
- *Alternative 2*: Let RAG `no_context` distinguish between logistics topics and non-logistics topics using a classifier. *Trade-off*: Wastes RAG vector search latency and embedding calls on out-of-domain queries that should be blocked pre-execution at Layer 1.

**Files likely to change**:
- `services/api/application/services/agent_guardrails.py`
- `services/api/tests/unit/test_agent_guardrails_input.py`

**Tests to add or update**:
- In `test_agent_guardrails_input.py`:
  - Add tests verifying that out-of-domain queries like `"what is the capital of France?"`, `"explain photosynthesis"`, `"what is the weather in Paris like"`, `"¿cuál es la capital de Francia?"`, and `"cuéntame un chiste"` are blocked with `action="block"`, `failure_category="content"`, `input_category="personal_task"`, and return the TrackFlow redirection message.
  - Verify that existing valid in-domain queries (shipping tracking, return policies, SLAs, tickets, inventory SKU stock) continue to pass with `action="allow"` and `input_category="in_domain"`.
  - Verify that casual small talk and logistics trivia continue to return `action="redirect"` and `input_category="casual_trivia"`.

## Risks & Considerations

- **False Positives on In-Domain Queries**: If the in-domain regex / keyword pattern is too strict, legitimate customer inquiries phrased colloquially (e.g., `"Where is my stuff?"`, `"Can I get my money back?"`, `"My box arrived broken"`, `"¿Dónde está mi paquete?"`) might be mistakenly classified as out-of-domain. The in-domain cue pattern must encompass colloquial shipping, return, and damaged/missing goods vocabulary in both English and Spanish.

## Open Questions

- None. The operational domain scope is explicitly mandated in `docs/agent-engineering/harnessing/trackflow-BRIEFING.es.md` (Sections 2 and 5) and `specs/030-agent-guardrails/spec.md` (FR-005).
