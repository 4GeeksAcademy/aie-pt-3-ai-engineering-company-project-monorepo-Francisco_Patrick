# Bug Assessment: Guardrail Routing & Fallback Taxonomy Contract Gaps

- **Slug**: guardrail-routing-taxonomy-contract
- **Created**: 2026-11-23
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

The guardrail implementation does not fully fit the Routing & Fallback Guardrail Acceptance Criteria (AC-1 through AC-7):
1. **AC-1 & AC-4 (Taxonomy & Precedence)**: Benign out-of-domain queries (weather, geography, general knowledge) are currently classified as `personal_task` with action `block` emitting the essays/homework rejection message rather than routing as `deflect` / `out_of_domain` with a neutral topic-deflection message.
2. **AC-4 & AC-5 (Contract Taxonomy & Observability)**: `GuardrailAction` in `domain/agent/entities.py` only defines `Literal["allow", "redirect", "block"]`, lacking `deflect` and `clarify`. `GuardrailInputCategory` lacks `out_of_domain` and `needs_context`. The decision contract is not aligned with the required `allow` | `clarify` | `deflect` | `block` structure with dedicated category reason codes.
3. **AC-6 (Multi-Turn Continuity)**: `InputGuardrailValidator.evaluate_input` accepts only a single query string without conversational history or clarification state tracking, preventing elliptical follow-ups (e.g. Turn 1: *"Hola, necesito ayuda"* -> Turn 2: *"Con el paquete que va a Los Ángeles"*) from utilizing prior turn context.

## Symptom

1. When a user asks a benign out-of-domain question containing a location cue (e.g., *"weather in Los Angeles"* or *"capital of California"*), the guardrail returns `action="block"`, `input_category="personal_task"`, and outputs the essay/coding rejection message (`C04` message) instead of a neutral deflection (`deflect` / `out_of_domain`).
2. The domain model and evaluation result do not expose the typed `decision` enum (`allow` | `clarify` | `deflect` | `block`) required by the AC, causing generic fallback messages to be emitted.
3. In multi-turn dialogues where the agent issues a clarification request, follow-up messages that lack standalone verbs cannot be linked back to the preceding turn context.

## Reproduction

1. In Python, evaluate benign out-of-domain queries:
   ```python
   from application.services.agent_guardrails import InputGuardrailValidator

   validator = InputGuardrailValidator()
   res = validator.evaluate_input("weather in Los Angeles")
   # Observed: res.action == "block", res.input_category == "personal_task", res.message contains "I cannot help with personal tasks, essays, homework, programming code..."
   # Expected per AC-1/AC-4/AC-5: decision == "deflect", input_category == "out_of_domain", neutral deflection message without C04 essay rejection.
   ```

2. Inspect `domain.agent.entities.GuardrailAction` and `GuardrailEvaluationResult`:
   - `GuardrailAction` is `Literal["allow", "redirect", "block"]` (missing `"deflect"`, `"clarify"`).
   - `input_category` lacks `"out_of_domain"`.

3. Attempt multi-turn evaluation with conversational context:
   - `validator.evaluate_input(query=...)` does not take `conversation_history` or prior agent state, failing AC-6.

## Suspected Code Paths

- `services/api/domain/agent/entities.py:32-46`:
  `GuardrailAction` and `GuardrailInputCategory` types do not support `deflect`, `clarify`, or `out_of_domain`.
- `services/api/application/services/agent_guardrails.py:504-515`:
  `_OUT_OF_DOMAIN_PATTERNS` matches weather and geography but assigns `action="block"`, `input_category="personal_task"`, and `message=PERSONAL_TASK_REFUSAL_*`.
- `services/api/application/services/agent_guardrails.py:440-448`:
  `InputGuardrailValidator.evaluate_input` lacks parameters for conversational turns / context.

## Root Cause Hypothesis

The initial guardrail implementation utilized a coarse 3-action model (`allow`, `redirect`, `block`) designed for single-turn standalone queries, grouping benign out-of-domain trivia together with restricted personal tasks (essays/code). Consequently, the decision taxonomy and data contracts lack the granular `deflect` and `clarify` states, neutral deflection messaging, and multi-turn context awareness mandated by AC-1 through AC-6. Confidence: High.

## Proposed Remediation

**Preferred**:
1. **Extend Domain Action & Category Contracts (`domain/agent/entities.py`)**:
   - Update `GuardrailAction` to include `deflect` and `clarify` (or map `redirect` <-> `clarify`/`deflect` while maintaining backward compatibility).
   - Add `out_of_domain` and `needs_context` to `GuardrailInputCategory`.
2. **Implement 5-Tier Precedence in `agent_guardrails.py`**:
   - Tier 1: Security violations / prompt injection (`block` + `jailbreak_attempt`).
   - Tier 2: Explicitly restricted personal tasks (essays, coding, homework) (`block` + `personal_task` + `C04` message).
   - Tier 3: Benign out-of-domain queries (weather, geography, trivia) (`deflect` + `out_of_domain` + neutral deflection message).
   - Tier 4: Ambiguous / generic support inquiries (`clarify` + `needs_context` + prompt for tracking/order context).
   - Tier 5: Valid TrackFlow operational queries (`allow` + `in_domain`).
3. **Add Neutral Deflection Messages**:
   - Provide bilingual neutral deflection responses that politely state the assistant's logistics scope without accusing the user of requesting essays or homework.
4. **Support Multi-Turn Context in Input Guardrail**:
   - Allow passing prior turn context or conversation history into `evaluate_input` so elliptical follow-up responses (e.g. *"Con el paquete que va a Los Ángeles"*) inherit active support context.
5. **Update Unit and Integration Tests**:
   - Verify `decision == deflect` for weather/geography with location cues.
   - Verify `decision == clarify` for generic support queries.
   - Verify `decision == block` for true essays/coding requests.
   - Verify multi-turn resolution.

**Files likely to change**:
- `services/api/domain/agent/entities.py`
- `services/api/domain/agent/ports.py`
- `services/api/application/services/agent_guardrails.py`
- `services/api/application/services/guardrail_observability.py`
- `services/api/tests/unit/test_agent_guardrails_input.py`
- `services/api/tests/integration/test_agent_guardrails_observability.py`

**Tests to add or update**:
- Test cases covering AC-1 through AC-7 directly against the new contract.

## Risks & Considerations

- Downstream dependencies (such as LangGraph agent nodes and observability loggers) expecting `action in ["allow", "redirect", "block"]` must be updated or mapped cleanly if `deflect` and `clarify` are introduced.

## Open Questions

- None.
