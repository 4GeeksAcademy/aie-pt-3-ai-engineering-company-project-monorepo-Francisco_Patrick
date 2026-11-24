# Bug Verification: Guardrail Domain Scope Fallback Decoupling & Generic Support Handling

- **Slug**: guardrail-fallback-decoupling
- **Tested**: 2026-11-23
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The bug no longer reproduces in either direction: out-of-domain queries with location cues are blocked as out-of-domain content, and generic customer support queries are politely redirected to TrackFlow CX workflows without triggering punitive personal task refusals. All new and existing guardrail regression suites pass with zero failures.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `& "services/api/.venv/Scripts/python.exe" -c "<eval reproduction queries>"` | pass | Evaluated `"weather in Los Angeles"`, `"capital of California"`, `"tiempo en Los Ángeles"`, `"capital de California"`, `"I need help"`, `"Can I talk to a support agent?"`, and `"Hola, necesito ayuda"`. False positives blocked with `OUT_OF_DOMAIN_TASK`; false negatives redirected with `CASUAL_TRIVIA_MANDATORY_REDIRECT`. |
| New / updated tests | `& "services/api/.venv/Scripts/python.exe" -m pytest services/api/tests/unit/test_agent_guardrails_input.py` | pass | 45 passed (100% of input guardrail tests including all decoupled out-of-domain, generic support redirection, and location+logistics test cases). |
| Regression suite | `& "services/api/.venv/Scripts/python.exe" -m pytest services/api/tests/unit/test_agent_guardrails_*.py services/api/tests/integration/test_agent_guardrails_observability.py` | pass | 73 passed across input, output, authorization, context isolation, and end-to-end observability integration suites. |
| Lint / type-check | `& "services/api/.venv/Scripts/python.exe" -m mypy services/api/application/services/agent_guardrails.py` | not-run | Mypy is not installed in the local virtual environment. |

## Output Excerpts

### Post-fix Reproduction Checks
```text
weather in Los Angeles -> action=block, reason=OUT_OF_DOMAIN_TASK, category=content
capital of California -> action=block, reason=OUT_OF_DOMAIN_TASK, category=content
tiempo en Los Angeles -> action=block, reason=OUT_OF_DOMAIN_TASK, category=content
capital de California -> action=block, reason=OUT_OF_DOMAIN_TASK, category=content
I need help -> action=redirect, reason=CASUAL_TRIVIA_MANDATORY_REDIRECT, category=content
Can I talk to a support agent? -> action=redirect, reason=CASUAL_TRIVIA_MANDATORY_REDIRECT, category=content
Hola, necesito ayuda -> action=redirect, reason=CASUAL_TRIVIA_MANDATORY_REDIRECT, category=content
SLA delivery in Los Angeles -> action=allow, reason=IN_DOMAIN_ALLOWED, category=none
```

### Generic Support Redirect Messages
```text
EN: Hello! I am TrackFlow's Customer Experience (CX) support assistant. I'm here to help with your authorized shipment tracking, return policies and SLAs (United States and Spain), and delivery incidents. Could you please provide your order or tracking number, or let me know what issue you are experiencing? At TrackFlow, we apply these logistics workflows directly across our United States (Los Angeles) and Spain (Zaragoza) operations...
ES: ¡Hola! Soy el asistente de soporte de Customer Experience (CX) de TrackFlow. Estoy a tu disposición para ayudarte con el seguimiento de tus pedidos, políticas de devolución y SLAs (Estados Unidos y España) o gestión de incidencias de entrega. ¿Podrías indicarme tu número de pedido, tracking ID o detallarme en qué puedo asistirte? En TrackFlow aplicamos estos procesos logísticos directamente en nuestras operaciones de Estados Unidos (Los Ángeles) y España (Zaragoza)...
```

### Full Guardrails Test Suite
```text
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0
rootdir: J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api
collected 73 items

services\api\tests\unit\test_agent_guardrails_input.py ................. [ 23%]
............................                                             [ 61%]
services\api\tests\unit\test_agent_guardrails_output.py ........         [ 72%]
services\api\tests\unit\test_agent_guardrails_authorization.py ......... [ 84%]
.                                                                        [ 86%]
services\api\tests\unit\test_agent_guardrails_context_isolation.py ....  [ 91%]
services\api\tests\integration\test_agent_guardrails_observability.py .. [ 94%]
....                                                                     [100%]
======================= 73 passed, 2 warnings in 0.72s ========================
```

## Residual Risks

- **Novel Out-of-Domain Trivia Phrasing**: While regex patterns cover common trivia keywords (weather, climate, capital of, astronomy, jokes, etc.), users could submit arbitrary world knowledge queries that omit these keywords yet include facility names. However, requiring explicit logistics keywords alongside bare facility locations mitigates cue hijacking.
- **Language Coverage**: Patterns and greetings are currently localized to English and Spanish. Additional operational locales would require localized regex patterns in `_GENERIC_SUPPORT_PATTERN` and `_OUT_OF_DOMAIN_PATTERNS`.

## Recommendation

Close the bug — verified end-to-end. Both false-positive out-of-domain queries and false-negative generic support queries are resolved, and all unit, integration, and backward-compatibility guardrail suites pass cleanly.
