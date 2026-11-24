# Bug Assessment: Backend startup fails with NameError: name 'Any' is not defined in agent_guardrails.py

- **Slug**: docker-backend-missing-any
- **Created**: 2026-11-23
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

The user provided the following traceback snippet from backend service execution:

```text
File "/app/services/api/application/services/agent_guardrails.py", line 480, in <module>
  conversation_history: Optional[Sequence[Any]] = None,
                                          ^^^
NameError: name 'Any' is not defined. Did you mean: 'any'?
```

## Symptom

When importing `application.services.agent_guardrails` in environments running Python <= 3.12 (such as the Docker container `/app`), or when evaluating annotations via `typing.get_type_hints()`, Python crashes with `NameError: name 'Any' is not defined. Did you mean: 'any'?`. The expected behavior is for `agent_guardrails.py` to successfully import, parse type annotations without error, and allow the backend Uvicorn worker to boot.

## Reproduction

1. In a Python 3.12 environment (or inside the `trackflow-backend` container):
   ```bash
   python -c "import application.services.agent_guardrails"
   ```
2. Or in Python 3.14 via runtime annotation introspection:
   ```bash
   python -c "import application.services.agent_guardrails; from typing import get_type_hints; get_type_hints(application.services.agent_guardrails._has_prior_support_or_clarification_context)"
   ```
3. Observe the immediate failure:
   ```text
   NameError: name 'Any' is not defined. Did you mean: 'any'?
   ```

## Suspected Code Paths

- `services/api/application/services/agent_guardrails.py:35` — Imports `Dict`, `List`, `Optional`, `Sequence`, `Tuple` from `typing`, but omits `Any`.
- `services/api/application/services/agent_guardrails.py:480-481` — `conversation_history: Optional[Sequence[Any]] = None` and `context: Optional[Dict[str, Any]] = None` annotate parameters with `Any`.
- `services/api/application/services/agent_guardrails.py:543-545` — `conversation_history: Optional[Sequence[Any]] = None`, `context: Optional[Dict[str, Any]] = None`, and `**kwargs: Any` in `InputGuardrailValidator.evaluate_input` annotate parameters with `Any`.

## Root Cause Hypothesis

**Confidence: high**.
In `services/api/application/services/agent_guardrails.py`, line 35 imports:
```python
from typing import Dict, List, Optional, Sequence, Tuple
```
`Any` is omitted from the imports. When `_has_prior_support_or_clarification_context` is defined at line 480, Python evaluates `Optional[Sequence[Any]]` at module definition time (in Python <= 3.12 without `from __future__ import annotations`), triggering a fatal `NameError: name 'Any' is not defined`. In Python 3.14, the error is deferred until runtime annotation evaluation (e.g., `typing.get_type_hints()`).

## Proposed Remediation

**Preferred**:
1. Update line 35 in `services/api/application/services/agent_guardrails.py` to import `Any`:
   ```python
   from typing import Any, Dict, List, Optional, Sequence, Tuple
   ```
2. Prepend `from __future__ import annotations` to the top of `agent_guardrails.py` to ensure consistent deferred evaluation across Python versions, aligning with `domain/agent/ports.py`.

**Alternatives** (optional):
- Only adding `Any` to `from typing import ...` without `__future__` annotations. (Adding both is preferred for consistency across the codebase).

**Files likely to change**:
- `services/api/application/services/agent_guardrails.py`
- `services/api/tests/unit/test_agent_guardrails_input.py`

**Tests to add or update**:
- Add a unit test verifying `typing.get_type_hints()` on `_has_prior_support_or_clarification_context` and `InputGuardrailValidator.evaluate_input` to ensure type annotations evaluate cleanly.

## Risks & Considerations

- **Blast Radius**: None. This is a non-breaking fix importing a standard library typing primitive that was already intended to be in scope.
- **Side Effects**: Restores startup capability for the Docker backend and dependency injection initialization.

## Open Questions

- None.
