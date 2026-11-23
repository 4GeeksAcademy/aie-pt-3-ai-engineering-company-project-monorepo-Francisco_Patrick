# Bug Fix: Docker backend startup fails with NameError: name 'Sequence' is not defined

- **Slug**: docker-backend-missing-sequence
- **Fixed**: 2026-11-23
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Added `Sequence` to the `typing` import and included `from __future__ import annotations` in `services/api/domain/agent/ports.py` to resolve the `NameError: name 'Sequence' is not defined` crash during backend startup when evaluating `InputGuardrailPort.evaluate_input`.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/domain/agent/ports.py` | modified | Added `from __future__ import annotations` and imported `Sequence` from `typing` |
| `services/api/tests/unit/test_agent_ports_import.py` | added test | Unit test suite verifying import and runtime type hint evaluation for `InputGuardrailPort` and all domain agent ports |

## Diff Highlights (optional)

```python
diff --git a/services/api/domain/agent/ports.py b/services/api/domain/agent/ports.py
--- a/services/api/domain/agent/ports.py
+++ b/services/api/domain/agent/ports.py
@@ -5,9 +5,11 @@ decoupling presentation controllers and LangGraph orchestration from operational
 tool adapters (`SupportTicketToolPort`, `InventoryStockToolPort`) and trace storage.
 """
 
+from __future__ import annotations
+
 from abc import ABC, abstractmethod
 from datetime import datetime
-from typing import Any, Dict, List, Optional, Tuple
+from typing import Any, Dict, List, Optional, Sequence, Tuple
```

## Tests Added or Updated

- `services/api/tests/unit/test_agent_ports_import.py::test_input_guardrail_port_import_and_type_hints` — pins down that `InputGuardrailPort` imports cleanly and `evaluate_input` type annotations resolve `conversation_history` to `Optional[Sequence[Any]]` without `NameError`.
- `services/api/tests/unit/test_agent_ports_import.py::test_all_agent_ports_type_hints_resolve` — introspects all port interfaces in `domain.agent.ports` to ensure `typing.get_type_hints` succeeds for every method without unresolved symbols.

## Local Verification

- Commands run:
  - `python -c "import typing; from domain.agent.ports import InputGuardrailPort; typing.get_type_hints(InputGuardrailPort.evaluate_input)"` → passed (resolved type hints without NameError).
  - `pytest tests/unit/test_agent_ports_import.py tests/unit/test_agent_guardrails_input.py` → 51 passed in 0.44s.
- Manual checks: Verified that all classes and methods in `domain.agent.ports` have fully resolvable type annotations.

## Deviations from Assessment

None. The implementation followed the preferred remediation outlined in `assessment.md`.

## Follow-ups

- Rebuild and launch the Docker backend container with `docker compose up --build backend` to verify that the container starts without crashing.
