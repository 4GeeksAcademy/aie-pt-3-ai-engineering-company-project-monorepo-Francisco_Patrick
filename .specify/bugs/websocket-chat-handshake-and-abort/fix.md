# Bug Fix: WebSocket Streaming Chat Abort Synchronization, Handshake Thread Validation, and Token Security Observations

- **Slug**: websocket-chat-handshake-and-abort
- **Fixed**: 2026-11-24T23:19:00+01:00
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Eliminated the potential high-latency abort race condition between `AgentChatEventBroker.abort_active_generation` and redirected generation turns by introducing a thread-safe idempotent turn finalizer callback on `_ActiveGenerationHandle` and `SupportAgentService.stream_query`, enforced explicit presence of `thread_id` and/or `session_id` during the WebSocket handshake (closing connections omitting both with policy code `1008`), added query-string `?token=` log redaction in `agent.py`, and updated Feature 035 specification status to `Complete`.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/infrastructure/messaging/agent_chat_event_broker.py` | modified | Added `on_abort_finalize` / `finalized` tracking on `_ActiveGenerationHandle`, `register_abort_finalizer`, and fallback finalizer invocation in `abort_active_generation` within the `< 250ms` SC-003 budget. |
| `services/api/application/services/support_agent_service.py` | modified | Guarded `_persist_and_publish_interrupted` and token chunk emission with a per-turn `threading.RLock()` and idempotent `turn_finalized` flag, registering the finalizer with the event broker before streaming. |
| `services/api/presentation/api/v1/agent.py` | modified | Enforced explicit `thread_id` or `session_id` during WebSocket handshake (closing with `1008 MISSING_THREAD_OR_SESSION_ID` when both are omitted, deriving `thread_id = session_id` when only `session_id` is supplied) and added `_sanitize_websocket_query_for_logging`. |
| `services/api/tests/test_websocket_streaming_chat.py` | added test | Added `test_us2_high_latency_abort_fallback_finalizer_prevents_race_and_duplicate_events` and `test_us3_handshake_thread_and_session_id_validation_and_token_log_redaction`. |
| `specs/035-websocket-streaming-chat/spec.md` | modified | Updated feature status from `Draft` to `Complete`. |

## Diff Highlights (optional)

```python
# services/api/infrastructure/messaging/agent_chat_event_broker.py
task.cancel()
try:
    await asyncio.wait_for(asyncio.shield(task), timeout=0.20)
except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
    pass

finalizer: Optional[Callable[[ChatInterruptedReason], Any]] = None
with self._lock:
    current = self._active_tasks.get(cleaned_thread)
    if current is not None and current.turn_id == active_turn_id:
        current.finalized = True
        finalizer = (
            current.on_abort_finalize
            or self._abort_finalizers.pop((cleaned_thread, active_turn_id), None)
        )
        self._active_tasks.pop(cleaned_thread, None)
    else:
        finalizer = self._abort_finalizers.pop((cleaned_thread, active_turn_id), None)

if finalizer is not None:
    finalizer(reason)
```

```python
# services/api/presentation/api/v1/agent.py
raw_thread_id = (
    auth_thread_id
    or websocket.query_params.get("thread_id")
    or auth_session_id
    or websocket.query_params.get("session_id")
    or ""
).strip()
if not raw_thread_id:
    await websocket.close(code=1008, reason="MISSING_THREAD_OR_SESSION_ID")
    return
```

## Tests Added or Updated

- `services/api/tests/test_websocket_streaming_chat.py::test_us2_high_latency_abort_fallback_finalizer_prevents_race_and_duplicate_events` — Simulates a generation turn whose cancellation unwinding takes 300ms (`> 200ms` wait timeout), verifying that `abort_active_generation` still returns in `< 250ms`, deterministically persists `status="interrupted"` and publishes `generation_interrupted` before Turn 2's `generation_started` event, and emits zero duplicate `generation_interrupted` or trailing `token_chunk` events when the slow task finishes unwinding.
- `services/api/tests/test_websocket_streaming_chat.py::test_us3_handshake_thread_and_session_id_validation_and_token_log_redaction` — Verifies that connections omitting both `thread_id` and `session_id` are rejected with close code `1008`, connections providing only `session_id` derive `thread_id = session_id`, and `_sanitize_websocket_query_for_logging` masks `?token=` and `&token=` query parameters.

## Local Verification

- Commands run:
  - `.\.venv\Scripts\python.exe -m pytest tests/test_websocket_streaming_chat.py -v` (in `services/api`) → `11 passed in 11.06s`
  - `npx.cmd jest __tests__/supportAgentChat.test.ts` (in `uis/backoffice`) → `1 passed suite, 7 passed tests in 1.115s`
- Manual checks: Verified that `isPermanentAuthCloseCode(1008)` in `uis/backoffice/lib/supportAgentChatClient.ts` already treats `1008` as a non-retryable policy violation close code.

## Deviations from Assessment

None.

## Follow-ups

- In production reverse-proxy configurations (e.g., Nginx / Envoy / Traefik), ensure access log formats redact `?token=` query parameters on `/api/v1/agent/ws` and `/agent/ws` or prefer first-frame `authenticate` messages when query-string logging cannot be disabled.
