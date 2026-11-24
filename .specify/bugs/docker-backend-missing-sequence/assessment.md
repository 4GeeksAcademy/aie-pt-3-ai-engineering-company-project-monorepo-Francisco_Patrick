# Bug Assessment: Docker backend startup fails with NameError: name 'Sequence' is not defined

- **Slug**: docker-backend-missing-sequence
- **Created**: 2026-11-23
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

The user provided the initial stack trace showing Uvicorn crashing during worker startup in a Python 3.12 environment:

```text
Process SpawnProcess-1:

Traceback (most recent call last):

  File "/usr/local/lib/python3.12/multiprocessing/process.py", line 314, in _bootstrap

    self.run()

  File "/usr/local/lib/python3.12/multiprocessing/process.py", line 108, in run

    self._target(*self._args, **self._kwargs)

  File "/usr/local/lib/python3.12/site-packages/uvicorn/_subprocess.py", line 80, in subprocess_started

    target(sockets=sockets)

  File "/usr/local/lib/python3.12/site-packages/uvicorn/server.py", line 86, in run

    return asyncio_run(self.serve(sockets=sockets), loop_factory=self.config.get_loop_factory())

           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.12/asyncio/runners.py", line 195, in run

    return runner.run(main)

           ^^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.12/asyncio/runners.py", line 118, in run

    return self._loop.run_until_complete(task)

           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.12/asyncio/base_events.py", line 691, in run_until_complete

    return future.result()

           ^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.12/site-packages/uvicorn/server.py", line 90, in serve

    await self._serve(sockets)

  File "/usr/local/lib/python3.12/site-packages/uvicorn/server.py", line 97, in _serve

    config.load()

  File "/usr/local/lib/python3.12/site-packages/uvicorn/config.py", line 511, in load

    self.loaded_app = self.load_app()

                      ^^^^^^^^^^^^^^^

  File "/usr/local/lib/python3.12/site-packages/uvicorn/config.py", line 434, in load_app
```

The continuation of the traceback obtained from container logs (`docker compose logs backend`) reveals the exact exception:

```text
trackflow-backend  |   File "/usr/local/lib/python3.12/site-packages/uvicorn/config.py", line 434, in load_app
trackflow-backend  |     return import_from_string(self.app)
trackflow-backend  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
trackflow-backend  |   File "/usr/local/lib/python3.12/site-packages/uvicorn/importer.py", line 19, in import_from_string
trackflow-backend  |     module = importlib.import_module(module_str)
trackflow-backend  |              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
trackflow-backend  |   File "/usr/local/lib/python3.12/importlib/__init__.py", line 90, in import_module
trackflow-backend  |     return _bootstrap._gcd_import(name[level:], package, level)
trackflow-backend  |            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
trackflow-backend  |   File "<frozen importlib._bootstrap>", line 1387, in _gcd_import
trackflow-backend  |   File "<frozen importlib._bootstrap>", line 1360, in _find_and_load
trackflow-backend  |   File "<frozen importlib._bootstrap>", line 1331, in _find_and_load_unlocked
trackflow-backend  |   File "<frozen importlib._bootstrap>", line 935, in _load_unlocked
trackflow-backend  |   File "<frozen importlib._bootstrap_external>", line 999, in exec_module
trackflow-backend  |   File "<frozen importlib._bootstrap>", line 488, in _call_with_frames_removed
trackflow-backend  |   File "/app/services/api/main.py", line 28, in <module>
trackflow-backend  |     from presentation.api.v1 import (  # noqa: E402
trackflow-backend  |   File "/app/services/api/presentation/api/v1/agent.py", line 16, in <module>
trackflow-backend  |     from domain.agent.entities import (
trackflow-backend  |   File "/app/services/api/domain/agent/__init__.py", line 28, in <module>
trackflow-backend  |     from domain.agent.ports import (
trackflow-backend  |   File "/app/services/api/domain/agent/ports.py", line 305, in <module>
trackflow-backend  |     class InputGuardrailPort(ABC):
trackflow-backend  |   File "/app/services/api/domain/agent/ports.py", line 313, in InputGuardrailPort
trackflow-backend  |     conversation_history: Optional[Sequence[Any]] = None,
trackflow-backend  |                                    ^^^^^^^^
trackflow-backend  | NameError: name 'Sequence' is not defined
trackflow-backend  | [INFO] Database connection succeeded (host: aws-1-eu-west-1.pooler.supabase.com, port: 6543).
trackflow-backend  | INFO:     Stopping reloader process [1]
```

## Symptom

When launching the backend service via `docker compose up --build backend`, the `trackflow-backend` container immediately crashes on startup with `NameError: name 'Sequence' is not defined` while defining `InputGuardrailPort` in `services/api/domain/agent/ports.py`. As a result, the backend cannot boot or serve requests, container healthchecks fail, and dependent services (such as `trackflow-ui`) cannot connect.

## Reproduction

1. Run `docker compose up --build backend` (or execute `python -c "import domain.agent.ports"` in a Python 3.12 environment).
2. Observe container startup failure and Uvicorn reloader crash in `docker compose logs backend`.
3. Note the unhandled `NameError: name 'Sequence' is not defined` at `services/api/domain/agent/ports.py:313`.

## Suspected Code Paths

- `services/api/domain/agent/ports.py:10` — `from typing import Any, Dict, List, Optional, Tuple` fails to import `Sequence`.
- `services/api/domain/agent/ports.py:313` — `conversation_history: Optional[Sequence[Any]] = None` uses `Sequence` in the parameter type annotations of `InputGuardrailPort.evaluate_input`.
- `services/api/domain/agent/ports.py:1` — Missing `from __future__ import annotations`, causing Python runtime (< 3.14) to eagerly evaluate type annotations at class definition time.

## Root Cause Hypothesis

In commit `c75973d` (`fix: improve agent guardrail input classification for logistics domain and support requests`), the method signature of `InputGuardrailPort.evaluate_input` in `services/api/domain/agent/ports.py` was updated to accept `conversation_history: Optional[Sequence[Any]] = None`. However, `Sequence` was never added to the `typing` imports at the top of `ports.py`, and the file does not include `from __future__ import annotations`. When Python 3.12 imports `main.py` -> `presentation.api.v1.agent` -> `domain.agent.ports`, it evaluates the class body of `InputGuardrailPort` and raises `NameError: name 'Sequence' is not defined`, crashing the Uvicorn reload worker.

Confidence: high.

## Proposed Remediation

**Preferred**:
1. In `services/api/domain/agent/ports.py`, add `Sequence` to the `typing` import statement:
   ```python
   from typing import Any, Dict, List, Optional, Sequence, Tuple
   ```
2. Add `from __future__ import annotations` at the very top of `services/api/domain/agent/ports.py` to ensure all type annotations are treated as strings at runtime, protecting against similar runtime evaluation crashes across Python versions.

**Alternatives**:
- Change `Optional[Sequence[Any]]` to `Optional[List[Any]]`. While functional, `Sequence[Any]` is cleaner and more semantically accurate because callers may pass tuples or other immutable sequences without requiring explicit list conversion.

**Files likely to change**:
- `services/api/domain/agent/ports.py`
- `services/api/tests/unit/test_agent_ports_import.py` (or extending existing domain tests)

**Tests to add or update**:
- Add a unit test verifying `from domain.agent.ports import InputGuardrailPort` imports cleanly without `NameError`.
- Verify `python -c "import main"` and `docker compose build backend` start without errors.

## Risks & Considerations

- Low risk: Adding `Sequence` to the `typing` import is completely non-breaking and standard across all supported Python versions (3.11, 3.12, 3.14).
- Ensure consistency across other guardrail service implementations (`services/api/application/services/agent_guardrails.py`) where `Sequence` is already imported and used.

## Open Questions

- None. The missing import and resulting `NameError` are directly evidenced by git history and runtime container logs.
