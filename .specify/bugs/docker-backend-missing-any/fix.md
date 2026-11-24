# Bug Fix: Backend NameError: name 'Any' is not defined in agent_guardrails.py

- **Slug**: docker-backend-missing-any
- **Fixed**: 2026-11-23
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Added `Any` to the `typing` module imports and prepended `from __future__ import annotations` in `services/api/application/services/agent_guardrails.py`. Added unit test regression coverage verifying runtime type annotation resolution (`get_type_hints`).

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/application/services/agent_guardrails.py` | modified | Added `Any` import from `typing` and `from __future__ import annotations` at the top of the module. |
| `services/api/tests/unit/test_agent_guardrails_input.py` | modified | Added `test_guardrails_type_annotations_evaluate_cleanly` verifying `typing.get_type_hints` succeeds on `_has_prior_support_or_clarification_context` and `InputGuardrailValidator.evaluate_input`. |

## Diff Highlights (optional)

```python
--- a/services/api/application/services/agent_guardrails.py
+++ b/services/api/application/services/agent_guardrails.py
@@ -30,6 +30,8 @@
      `<user_inquiry authority="untrusted">`, and `<external_context authority="passive_data">`.
 """

+from __future__ import annotations
+
 import dataclasses
 import re
-from typing import Dict, List, Optional, Sequence, Tuple
+from typing import Any, Dict, List, Optional, Sequence, Tuple
```

## Tests Added or Updated

- `services/api/tests/unit/test_agent_guardrails_input.py::test_guardrails_type_annotations_evaluate_cleanly` — Validates that `typing.get_type_hints()` successfully resolves annotations without `NameError` for `Any` or other type hints.

## Local Verification

- Commands run:
  - `python -c "import application.services.agent_guardrails; from typing import get_type_hints; get_type_hints(application.services.agent_guardrails._has_prior_support_or_clarification_context)"` → PASS (returned dict with resolved annotations, no `NameError`).
  - `pytest tests/unit/test_agent_guardrails_input.py tests/unit/test_agent_guardrails_authorization.py tests/unit/test_agent_guardrails_context_isolation.py tests/unit/test_agent_guardrails_output.py tests/unit/test_knowledge_guardrails.py tests/unit/test_memory_guardrails.py` → PASS (92 passed, 0 failures).

## Deviations from Assessment

None.

## Follow-ups

- Rebuild or restart the backend container (`docker compose restart backend` / `docker compose up -d --build backend`) to verify clean startup inside Docker.
