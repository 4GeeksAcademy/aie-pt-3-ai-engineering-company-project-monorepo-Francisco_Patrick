# Bug Verification: Docker backend startup fails with NameError: name 'Sequence' is not defined

- **Slug**: docker-backend-missing-sequence
- **Tested**: 2026-11-23T12:25:35+01:00
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: partial

## Summary

The original defect (`NameError: name 'Sequence' is not defined` in `domain/agent/ports.py`) is verified resolved and all targeted unit tests pass. However, end-to-end backend container startup still fails under Python 3.12 due to a downstream missing import bug (`NameError: name 'Any' is not defined` at `services/api/application/services/agent_guardrails.py:480`).

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (original bug) | `docker run --rm -e PYTHONPATH=/app:/app/services:/app/services/api mr-stegmann-ai-engineering-company-project-monorepo-backend:latest python -c "import typing; from domain.agent.ports import InputGuardrailPort; print(typing.get_type_hints(InputGuardrailPort.evaluate_input))"` | pass | `InputGuardrailPort` imports cleanly and resolves `conversation_history: typing.Optional[typing.Sequence[typing.Any]]` without `NameError`. |
| New / updated tests | `.venv\Scripts\pytest.exe tests/unit/test_agent_ports_import.py` | pass | 2 passed in 0.08s. Confirmed runtime type hint evaluation across all agent port interfaces. |
| Regression suite | `.venv\Scripts\pytest.exe tests/unit/test_agent_ports_import.py tests/unit/test_agent_guardrails_input.py tests/unit/test_agent_guardrails_authorization.py tests/unit/test_agent_guardrails_context_isolation.py tests/unit/test_agent_guardrails_output.py tests/unit/test_agent_workflow.py` | pass | 86 passed, 0 failures across all agent and guardrail suites. |
| Container startup (end-to-end) | `docker run --rm -e PYTHONPATH=/app:/app/services:/app/services/api mr-stegmann-ai-engineering-company-project-monorepo-backend:latest python -c "from api.main import app"` | fail | Passed `ports.py:313`, but failed downstream at `agent_guardrails.py:480` with `NameError: name 'Any' is not defined`. |

## Output Excerpts

### Original Bug Resolution (Passed)
```text
Docker hints: {'query': <class 'str'>, 'language': <class 'str'>, 'conversation_history': typing.Optional[typing.Sequence[typing.Any]], 'context': typing.Optional[typing.Dict[str, typing.Any]], 'return': <class 'domain.agent.entities.GuardrailEvaluationResult'>}
```

### Unit & Regression Suite (Passed)
```text
tests\unit\test_agent_ports_import.py ..                                 [  2%]
tests\unit\test_agent_guardrails_input.py .............................. [ 37%]
...................                                                      [ 59%]
tests\unit\test_agent_guardrails_authorization.py ..........             [ 70%]
tests\unit\test_agent_guardrails_context_isolation.py ....               [ 75%]
tests\unit\test_agent_guardrails_output.py ........                      [ 84%]
tests\unit\test_agent_workflow.py .............                          [100%]
======================= 86 passed, 2 warnings in 1.08s ========================
```

### Container Startup Downstream Error (Failed)
```text
Traceback (most recent call last):
  File "<string>", line 1, in <module>
  File "/app/services/api/main.py", line 28, in <module>
    from presentation.api.v1 import (  # noqa: E402
  File "/app/services/api/presentation/api/v1/agent.py", line 31, in <module>
    from presentation.dependencies import (
  File "/app/services/api/presentation/dependencies.py", line 34, in <module>
    from application.services.support_agent_service import SupportAgentService
  File "/app/services/api/application/services/support_agent_service.py", line 21, in <module>
    from application.services.agent_guardrails import (
  File "/app/services/api/application/services/agent_guardrails.py", line 480, in <module>
    conversation_history: Optional[Sequence[Any]] = None,
                                            ^^^
NameError: name 'Any' is not defined. Did you mean: 'any'?
```

## Residual Risks

- **Downstream NameError in Python < 3.14**: In Python 3.12 (the Docker container base image), type annotations in function signatures without `from __future__ import annotations` are evaluated at module load time. While `domain/agent/ports.py` is now protected with `Sequence` import and future annotations, `services/api/application/services/agent_guardrails.py` defines `_has_prior_support_or_clarification_context` using `Any` without importing `Any` from `typing`, preventing `api.main:app` from starting in Docker.

## Recommendation

Hold — the specific fix for `domain/agent/ports.py` is verified, but backend container startup remains blocked by the downstream sister bug in `agent_guardrails.py:480`. Recommend running `/speckit-bug-assess` for the new symptom (`NameError: name 'Any' is not defined` in `agent_guardrails.py`) or applying the missing `Any` import / `from __future__ import annotations` to completely unblock container boot.
