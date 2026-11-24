# Bug Fix: Guardrail Domain Scope Fallback Decoupling & Generic Support Handling

- **Slug**: guardrail-fallback-decoupling
- **Fixed**: 2026-11-23
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Decoupled out-of-domain intents (weather, geography, general trivia) and bare location cues from unconditional in-domain classification, and added generic customer support pattern recognition that politely redirects assistance and human-agent queries to TrackFlow CX instead of blocking them with personal task essay/homework refusals.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/application/services/agent_guardrails.py` | modified | Added `_GENERIC_SUPPORT_PATTERN` and `_OUT_OF_DOMAIN_PATTERNS`; decoupled bare location cues (`_LOCATION_FACILITY_CUES`) from `_IN_DOMAIN_LOGISTICS_CUES`; updated `build_casual_trivia_response` to provide bilingual customer support prompts; updated `InputGuardrailValidator.evaluate_input` to prioritize out-of-domain intent blocking and route generic support to casual trivia redirection. |
| `services/api/tests/unit/test_agent_guardrails_input.py` | modified | Added unit test coverage for decoupled out-of-domain queries with location cues (`weather in Los Angeles`, `capital of California`, `tiempo en Los Ángeles`, `capital de California`), generic support inquiries (`I need help`, `Can I talk to a support agent?`, `Hola, necesito ayuda`, `¿Puedo hablar con un agente?`), and valid logistics queries with locations. |

## Diff Highlights (optional)

```python
# Content guardrail: Prioritize explicit out-of-domain intent blocking
for _reason_code, pattern in _OUT_OF_DOMAIN_PATTERNS:
    if pattern.search(cleaned):
        return GuardrailEvaluationResult(
            layer="input_guard",
            action="block",
            failure_category="content",
            input_category="personal_task",
            reason_code="OUT_OF_DOMAIN_TASK",
            message=PERSONAL_TASK_REFUSAL_ES if use_es else PERSONAL_TASK_REFUSAL_EN,
        )

# Permitted generic support queries redirect politely to TrackFlow CX
if _GENERIC_SUPPORT_PATTERN.search(query or ""):
    return (
        "Hello! I am TrackFlow's Customer Experience (CX) support assistant. "
        "I'm here to help with your authorized shipment tracking, return policies and SLAs "
        "(United States and Spain), and delivery incidents. Could you please provide your order or "
        "tracking number, or let me know what issue you are experiencing? "
        f"{MANDATORY_TRIVIA_REDIRECT_SUFFIX_EN}"
    )
```

## Tests Added or Updated

- `services/api/tests/unit/test_agent_guardrails_input.py::TestPersonalTaskRefusalAndCasualTriviaRedirection::test_out_of_domain_queries_are_blocked_and_redirected` — Pins down that out-of-domain queries mentioning TrackFlow facilities/locations (`weather in Los Angeles`, `capital of California`, `tiempo en Los Ángeles`, `capital de California`) return `action="block"`, `failure_category="content"`, and `reason_code="OUT_OF_DOMAIN_TASK"`.
- `services/api/tests/unit/test_agent_guardrails_input.py::TestPersonalTaskRefusalAndCasualTriviaRedirection::test_generic_support_queries_redirect_to_trackflow` — Pins down that generic assistance and human agent queries (`I need help`, `Can I talk to a support agent?`, `Hola, necesito ayuda`, `¿Puedo hablar con un agente?`, `help me`, `necesito ayuda`) return `action="redirect"`, `failure_category="content"`, and a welcoming TrackFlow prompt rather than the essays/homework refusal.
- `services/api/tests/unit/test_agent_guardrails_input.py::TestPersonalTaskRefusalAndCasualTriviaRedirection::test_in_domain_queries_are_allowed` — Validates that queries combining locations with logistics keywords (`SLA delivery in Los Angeles`, `Devolución en Zaragoza`, `Warehouse stock in California`) continue to be allowed with `action="allow"` and `reason_code="IN_DOMAIN_ALLOWED"`.

## Local Verification

- Commands run:
  - `powershell -NoProfile -Command "Set-Location services/api; $env:PYTHONPATH='.'; .venv\Scripts\python.exe -m pytest tests/unit/test_agent_guardrails_input.py tests/integration/test_agent_guardrails_observability.py"` → `51 passed in 0.60s`
- Manual checks: Verified that `evaluate_input` correctly decouples location cues and blocks trivia/weather, routes generic support to TrackFlow prompts without accusatory refusal, and maintains backward compatibility for all jailbreak, in-domain, and casual trivia suites.

## Deviations from Assessment

None.

## Follow-ups

- Run `/speckit-bug-test slug=guardrail-fallback-decoupling` to perform end-to-end regression verification against the full suite.
