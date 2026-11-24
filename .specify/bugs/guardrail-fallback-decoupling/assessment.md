# Bug Assessment: Guardrail Domain Scope Fallback Decoupling & Generic Support Handling

- **Slug**: guardrail-fallback-decoupling
- **Created**: 2026-11-23
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> Documented cases are now blocked, but the fallback continues to fail in both directions. Out-of-domain queries containing a TrackFlow cue are still slipping through: "weather in Los Angeles" and "capital of California" return allow/in_domain; C02 does not cover arbitrary out-of-domain queries. Conversely, legitimate support queries without a cue are being classified as personal: "I need help", "Can I talk to a support agent?", and "Hola, necesito ayuda" are blocked with the essays/code message; C04 ceases to be useful. Decouple out-of-domain intents (weather, geography, trivia) from cues, or require a logistics intent in addition to the cue; for generic support queries, ask for details or redirect to TrackFlow rather than rejecting them. Add tests for these cases.

## Symptom

Input guardrail evaluation fails in both directions:
1. **False Positives (Out-of-domain allowed as in-domain)**: Out-of-domain queries that mention TrackFlow operational locations or entities (e.g., `"weather in Los Angeles"`, `"capital of California"`) match location cues in `_IN_DOMAIN_LOGISTICS_CUES` without any logistics intent, resulting in `action="allow"` and `input_category="in_domain"`. Consequently, C02 fails to block non-logistics trivia, leaking these queries into RAG/execution.
2. **False Negatives (Legitimate support queries blocked as personal abuse)**: Legitimate, generic customer support queries lacking explicit tracking numbers or specific logistics keywords (e.g., `"I need help"`, `"Can I talk to a support agent?"`, `"Hola, necesito ayuda"`) fail the in-domain cue check and fall through to the out-of-domain block (`OUT_OF_DOMAIN_TASK`), returning `action="block"`, `input_category="personal_task"`, and the harsh `PERSONAL_TASK_REFUSAL` ("I cannot help with personal tasks, essays, homework, programming code..."). This degrades CX and prevents general customer assistance initiation (impacting C04).

## Reproduction

1. In Python, evaluate out-of-domain queries with location cues:
   ```python
   from application.services.agent_guardrails import InputGuardrailValidator

   validator = InputGuardrailValidator()

   res1 = validator.evaluate_input("weather in Los Angeles")
   # Observed: res1.action == "allow", res1.input_category == "in_domain", res1.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: Blocked or redirected as out-of-domain content (not allowed as in-domain)

   res2 = validator.evaluate_input("capital of California")
   # Observed: res2.action == "allow", res2.input_category == "in_domain", res2.reason_code == "IN_DOMAIN_ALLOWED"
   # Expected: Blocked or redirected as out-of-domain content (not allowed as in-domain)
   ```

2. Evaluate generic support inquiries:
   ```python
   res3 = validator.evaluate_input("I need help")
   # Observed: res3.action == "block", res3.input_category == "personal_task", res3.message starts with "I cannot help with personal tasks, essays..."
   # Expected: Guided/redirected to TrackFlow CX or allowed with prompt for order details

   res4 = validator.evaluate_input("Can I talk to a support agent?")
   # Observed: res4.action == "block", res4.input_category == "personal_task", res4.message starts with "I cannot help with personal tasks, essays..."
   # Expected: Guided/redirected to TrackFlow CX or allowed with prompt for order details

   res5 = validator.evaluate_input("Hola, necesito ayuda")
   # Observed: res5.action == "block", res5.input_category == "personal_task", res5.message starts with "No puedo ayudarte a escribir ensayos..."
   # Expected: Guided/redirected to TrackFlow CX or allowed with prompt for order details
   ```

## Suspected Code Paths

- `services/api/application/services/agent_guardrails.py:287-330` (`_IN_DOMAIN_LOGISTICS_CUES`):
  Matches location tokens (e.g., `los angeles`, `california`, `zaragoza`, `madrid`) unconditionally as domain cues even when the inquiry has no logistics intent (e.g., weather or geography).
- `services/api/application/services/agent_guardrails.py:252-276` (`_CASUAL_TRIVIA_PATTERNS`):
  Only matches specific greetings and reverse logistics/3PL trivia, omitting general support / human agent requests.
- `services/api/application/services/agent_guardrails.py:436-459` (`InputGuardrailValidator.evaluate_input`):
  - In step 4, evaluates `is_in_domain` based solely on any cue match (`_IN_DOMAIN_TRACKFLOW_CUE.search(cleaned)`) without verifying absence of out-of-domain intents (weather, trivia, geography) or presence of logistics verbs when only location cues match.
  - In step 5, defaults all unmatched queries directly to `action="block"`, `input_category="personal_task"`, sending the accusatory essays/code refusal message even for genuine help requests.

## Root Cause Hypothesis

`InputGuardrailValidator.evaluate_input` couples domain determination solely to substring/regex presence of entities and locations without decoupling explicit out-of-domain intents (weather, trivia, geography), allowing queries containing "Los Angeles" or "California" to pass unconditionally into `in_domain`. Concurrently, the classifier lacks a category for generic customer support / assistance intents (`"I need help"`, `"Hola, necesito ayuda"`), causing legitimate support requests without pre-supplied tracking numbers to fall through into the punitive `personal_task` (essays/homework) refusal filter. Confidence: High.

## Proposed Remediation

**Preferred**:
1. **Decouple Out-of-Domain Intents from Cues**:
   - Define patterns for out-of-domain queries (weather, geography, general trivia, astronomy, etc., e.g., `weather`, `clima`, `tiempo`, `capital of`, `capital de`, `temperature`, `forecast`).
   - Give out-of-domain intent checks precedence, or require that entity/location cues (e.g. "Los Angeles", "California", "Zaragoza") MUST be accompanied by logistics keywords (e.g. shipping, delivery, order, package, tracking, return, warehouse, inventory, SLA) to be classified as `in_domain`.
2. **Generic Support Query Recognition & TrackFlow Redirection**:
   - Define a pattern for generic customer assistance and agent requests (e.g., `"I need help"`, `"help me"`, `"can I talk to a support agent"`, `"necesito ayuda"`, `"ayuda"`, `"hablar con un agente"`).
   - Route these either:
     - As `casual_trivia` / `general_support` with `action="redirect"` and a welcoming TrackFlow prompt asking the customer for their order number, tracking ID, or shipment details (e.g., `"Hello! I'm TrackFlow's CX support assistant. I'm here to help with your shipments, returns, and delivery incidents. Could you please provide your order or tracking number, or tell me what issue you are experiencing?"`), OR
     - As `action="allow"` / `in_domain` so the conversational agent can greet them and ask for their order details.
3. Keep strict blocking for explicit personal tasks (essays, homework, code generation, therapy) and jailbreaks.

**Alternatives**:
- *Alternative 1*: Require two distinct cues (e.g. a location + an action verb) for all domain matching. *Trade-off*: Could reject simple queries like "Where is my package?" or "Madrid delivery" if verb patterns are too rigid.
- *Alternative 2*: Run an LLM guardrail classifier node. *Trade-off*: Introduces latency and violates offline deterministic testing requirement (FR-013).

**Files likely to change**:
- `services/api/application/services/agent_guardrails.py`
- `services/api/tests/unit/test_agent_guardrails_input.py`

**Tests to add or update**:
- Add unit tests verifying:
  - `"weather in Los Angeles"` and `"capital of California"` (and Spanish equivalents `"tiempo en Los Ángeles"`, `"capital de California"`) are blocked or redirected as out-of-domain, NOT allowed as `in_domain`.
  - Generic support queries (`"I need help"`, `"Can I talk to a support agent?"`, `"Hola, necesito ayuda"`, `"¿Puedo hablar con un agente?"`) are NOT rejected with the essays/homework message, but rather politely redirected or handled by TrackFlow CX.
  - Legitimate logistics queries with locations (e.g., `"SLA delivery in Los Angeles"`, `"Devolución en Zaragoza"`, `"Warehouse stock in California"`) continue to be allowed as `in_domain`.

## Risks & Considerations

- **Pattern Overlaps**: Location cues must still allow legitimate logistics questions involving facilities (e.g. "What carrier is used in Los Angeles?"). Requiring logistics keywords or explicitly filtering out-of-domain intents (weather/trivia) preserves this balance.
- **Language Support**: All new patterns and support redirect messages must be fully bilingual (English and Spanish).

## Open Questions

- None. The required behavior aligns directly with TrackFlow CX mission and briefing requirements.
