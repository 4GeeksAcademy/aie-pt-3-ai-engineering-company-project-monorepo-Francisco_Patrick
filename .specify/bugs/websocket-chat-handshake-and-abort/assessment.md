# Bug Assessment: WebSocket Streaming Chat Abort Synchronization, Handshake Thread Validation, and Token Security Observations

- **Slug**: websocket-chat-handshake-and-abort
- **Created**: 2026-11-24T23:14:00+01:00
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: low

## Report (verbatim or summarized)

```text
# Technical findings and observations from the analysis

1. **Potential deadlock/race condition in `abort_active_generation` (`agent_chat_event_broker.py`)**:
* `abort_active_generation` performs `await asyncio.wait_for(asyncio.shield(task), timeout=0.24)`. If the `task` is awaiting an operation that ignores `CancelledError` or takes longer than 240ms, `wait_for` catches a `TimeoutError` and proceeds. However, in `_launch_generation_turn` (`agent.py`), `broker.abort_active_generation(...)` is called directly within `_client_reader_loop` before the new turn is created. While this is covered by the `< 250ms` test case, it is worth monitoring in environments with higher I/O latency to ensure that the `timeout=0.24` does not interrupt the persistence of the `generation_interrupted` state before the redirected turn begins.


2. **Validation of `thread_id` / `session_id` during the handshake (`agent.py`)**:
* The requirements specify that a `session_id` and/or `thread_id` must be provided during the handshake or via the URL. Currently, the endpoint generates a default `thr_<uuid>` if both are omitted; this prevents socket connection failures but is more permissive than an explicit rejection, which would be the case if strict validation were enforced.


3. **Token in the query string (`?token=...`)**:
* This is explicitly included in the requirements to account for limitations in the browser's `new WebSocket` API, in conjunction with support for an initial `authenticate` frame. Please be aware, however, that URLs containing `?token=` may be recorded in proxy or server logs. 4. **Test coverage**:
* Includes tests in `services/api/tests/test_websocket_streaming_chat.py` and `uis/backoffice/__tests__/supportAgentChat.test.ts` covering streaming, aborting in `< 250ms`, redirection, `4001`/`4003` authentication, reconnection/rehydration, and the absence of RFP fields.
```

## Symptom

During architectural and post-implementation review of Feature 035 (`035-websocket-streaming-chat`), three technical observations and edge-case behaviors were identified across `agent_chat_event_broker.py` and `agent.py`, alongside a confirmation of test coverage:
1. **Race Condition on High-I/O Abort (`abort_active_generation`)**: `AgentChatEventBroker.abort_active_generation` waits up to `240ms` (`timeout=0.24`) for a cancelled task (`asyncio.shield(task)`) to finish persisting the `interrupted` state and publishing `generation_interrupted`. If pre-generation synchronous work running inside `run_in_threadpool(self._prepare_pre_generation_state, ...)` takes longer than 240ms to yield or if TinyDB disk I/O experiences latency spikes during `_persist_and_publish_interrupted`, `wait_for` times out and returns early. In `_launch_generation_turn`, the redirected turn then starts immediately while the old task may finalize slightly later, risking out-of-order `generation_interrupted` / `generation_started` events or TinyDB thread message ordering races.
2. **Permissive Fallback for Missing `thread_id` / `session_id` (`agent.py`)**: In `support_agent_websocket_endpoint`, when a client omits both `thread_id` and `session_id` from the handshake URL query parameters and the `authenticate` frame, the server falls back to generating an ephemeral `thr_<uuid>` (`f"thr_{uuid.uuid4().hex[:12]}"`) instead of enforcing explicit presence of `thread_id` or `session_id` per FR-003.
3. **Query String JWT Exposure in Access Logs (`?token=...`)**: Passing the JWT via `?token=<jwt>` in the WebSocket handshake URL satisfies browser `new WebSocket()` header limitations and FR-002, but query strings can be logged in plain text by reverse proxies or ASGI access logs unless sanitized or paired with first-frame `authenticate` preference.
4. **Test Coverage Verification**: Automated test suites in `services/api/tests/test_websocket_streaming_chat.py` and `uis/backoffice/__tests__/supportAgentChat.test.ts` comprehensively cover US1–US5, `< 250ms` abort latency, authentication (`4001`/`4003`), rehydration, and zero Part 1 RFP field leakage.

## Reproduction

1. **Abort Persistence Race Under High I/O Latency**:
   - In `SupportAgentService.stream_query` (`services/api/application/services/support_agent_service.py:846`), `_prepare_pre_generation_state` executes synchronously inside `run_in_threadpool`.
   - If a client sends a redirecting `user_message` while `_prepare_pre_generation_state` is mid-flight and takes `> 240ms` (or if `_persist_and_publish_interrupted` takes `> 240ms`), `broker.abort_active_generation` sets `abort_event`, cancels the coroutine task, hits the `0.24s` `asyncio.TimeoutError` on `asyncio.wait_for(asyncio.shield(task), timeout=0.24)`, and returns `True`.
   - `_launch_generation_turn` immediately invokes Turn 2 (`stream_query`), which reads `thread_state` and appends `usr_turn_2` and `asst_turn_2` before Turn 1's `CancelledError` handler finishes persisting `asst_turn_1 (status="interrupted")` or if `CancelledError` interrupts `run_in_threadpool` while synchronous persistence is contended.
2. **Handshake Without `thread_id` or `session_id`**:
   - Connect to `/api/v1/agent/ws?token=<valid_jwt>` without `thread_id` or `session_id` query parameters.
   - *Observed*: Connection succeeds and emits `session_rehydrated` with an auto-generated `thread_id: "thr_<12-hex>"` (`services/api/presentation/api/v1/agent.py:796-808`).
   - *Strict FR-003 interpretation*: Should either require explicit `thread_id` / `session_id` or document/enforce deterministic binding rules.
3. **JWT in Handshake Query String**:
   - Inspect `buildSupportAgentWebSocketUrl` in `uis/backoffice/lib/supportAgentChatClient.ts:99-116` and `useSupportAgentChat.ts:209-218`.
   - Observe that `?token=<jwt>` is appended to the WebSocket URL and transmitted on connection open.

## Suspected Code Paths

- `services/api/infrastructure/messaging/agent_chat_event_broker.py:221-249` — `abort_active_generation` cancels `task` and awaits `asyncio.wait_for(asyncio.shield(task), timeout=0.24)`, swallowing ` asyncio.TimeoutError` if the task does not finalize within 240ms.
- `services/api/application/services/support_agent_service.py:777-885` — `_persist_and_publish_interrupted` and `stream_query` cancellation handling; if `task.cancel()` interrupts `await run_in_threadpool(self._prepare_pre_generation_state, ...)`, `_persist_and_publish_interrupted` runs synchronously on the event loop thread, or if a custom awaitable takes `> 240ms`, finalization races with the next turn.
- `services/api/presentation/api/v1/agent.py:894-904` — `_launch_generation_turn` awaits `broker.abort_active_generation(...)` before launching the new turn task.
- `services/api/presentation/api/v1/agent.py:796-809` — `support_agent_websocket_endpoint` auto-generates `f"thr_{uuid.uuid4().hex[:12]}"` when both `thread_id` and `session_id` are omitted.
- `uis/backoffice/hooks/useSupportAgentChat.ts:209-238` — WebSocket client sends `token` in the handshake URL query string and does not send a first-frame `authenticate` message or redact tokens on the backend logger.

## Root Cause Hypothesis

**Confidence: High**.
1. **Abort Finalization Window vs. `< 250ms` SLA (SC-003)**: `abort_active_generation` uses `timeout=0.24` specifically to guarantee compliance with SC-003 (`< 250ms` abort latency). In normal execution, `asyncio.CancelledError` is raised immediately at the current `await` point (`asyncio.sleep` between token chunks or `run_in_threadpool`), and `_persist_and_publish_interrupted` is a synchronous function that finishes in `< 5ms`. However, if an inner coroutine shields cancellation or if `_persist_and_publish_interrupted` is not guaranteed to run once and atomically before `abort_active_generation` returns, a slow task could emit `generation_interrupted` *after* the redirected turn has already started. Ensuring deterministic, idempotent finalization (e.g., guarded by a per-turn finalization flag/lock so `abort_active_generation` guarantees `generation_interrupted` is published and persisted before returning, even if an underlying threadpool worker takes longer to unwind) eliminates the race condition while keeping abort latency well under 250ms.
2. **Permissive Handshake Defaulting**: Generating `thr_<uuid>` when both `thread_id` and `session_id` are absent was added as a defensive fallback so bare WebSocket connections wouldn't crash, whereas FR-003 states that every WebSocket connection must bind to a conversation context identified by `session_id` and/or `thread_id` supplied in the handshake URL or initial binding frame. Note that existing tests in `services/api/tests/test_websocket_streaming_chat.py` always pass `thread_id=...` in the URL or `authenticate` frame.
3. **Query String Token Logging**: Browser `WebSocket` APIs cannot attach custom `Authorization: Bearer` headers, which is why FR-002 explicitly requires supporting `?token=` and/or first-frame `authenticate`. While `?token=` is required by the spec and tested in `test_websocket_streaming_chat.py` and `supportAgentChat.test.ts`, server-side log sanitization (or sending `authenticate` on `onopen` when appropriate) mitigates accidental token exposure in diagnostic logs.

## Proposed Remediation

**Preferred**:
1. **Deterministic Idempotent Turn Interrupt Finalization (`agent_chat_event_broker.py` & `support_agent_service.py`)**:
   - Track an idempotent `finalized` state (or finalization callback / per-thread turn lock) on `_ActiveGenerationHandle` / `stream_query` so that when `abort_active_generation` is invoked:
     - `abort_event.set()` and `task.cancel()` are triggered immediately.
     - If `await asyncio.wait_for(asyncio.shield(task), timeout=0.20)` completes within the budget, `_persist_and_publish_interrupted` has already executed inside `stream_query`.
     - If `TimeoutError` occurs (e.g., due to a slow blocking I/O call or uncooperative awaitable in a high-latency environment), `abort_active_generation` invokes a registered synchronous/fast fallback finalizer callback on the handle (and marks the handle finalized so the late-unwinding task cannot double-publish `generation_interrupted` or emit trailing `token_chunk` events). This guarantees 100% deterministic persistence of `status="interrupted"` *before* `_launch_generation_turn` creates the redirected turn, while strictly honoring the `< 250ms` SC-003 budget.
2. **Handshake `thread_id` / `session_id` Validation (`agent.py`)**:
   - Check whether at least one of `thread_id` or `session_id` was provided via the URL query parameters (`?thread_id=...` or `?session_id=...`) or the first-frame `authenticate` payload (`auth_thread_id` / `auth_session_id`).
   - Verify whether any existing tests in `services/api/tests/` omit both `thread_id` and `session_id`. If all valid tests supply `thread_id` or `session_id` (or if strict validation is desired), reject connections that omit both with close code `4002` / `1008` (or `4003`), or make strict validation configurable while ensuring `session_id`-only connections properly derive `thread_id = session_id`.
3. **Query String Token Hygiene & Spec Status (`agent.py`, `spec.md`)**:
   - Add a helper or filter to ensure any internal logging in `agent.py` never logs raw query strings containing `token=`.
   - Optionally send the `authenticate` frame on socket open or document the proxy log redaction recommendation for `?token=` in `agent.py`.
   - Update `specs/035-websocket-streaming-chat/spec.md` status from `Draft` to `Complete` once verified.

**Alternatives**:
- *Per-Thread Asyncio Lock in `SupportAgentService.stream_query`*: Serialize turn execution per `thread_id` with an `asyncio.Lock` in the broker so Turn 2 waits for Turn 1's `finally` block. Trade-off: If Turn 1 is stuck in an uninterruptible >250ms I/O operation, waiting on the lock without a fallback finalizer would delay Turn 2 and exceed the `< 250ms` abort SLA. Combining an idempotent finalizer callback on `_ActiveGenerationHandle` with guarded publication gives both `< 250ms` responsiveness and strict turn ordering.

**Files likely to change**:
- `services/api/infrastructure/messaging/agent_chat_event_broker.py`
- `services/api/application/services/support_agent_service.py`
- `services/api/presentation/api/v1/agent.py`
- `services/api/tests/test_websocket_streaming_chat.py`
- `specs/035-websocket-streaming-chat/spec.md`

**Tests to add or update**:
- `services/api/tests/test_websocket_streaming_chat.py`:
  - Add a high-latency abort/redirection test where a simulated slow generation task exceeds the `wait_for` timeout, verifying that `generation_interrupted` and TinyDB persistence still complete deterministically before the redirected turn's `generation_started` event, with zero duplicate `generation_interrupted` events when the slow task finally unwinds.
  - Add a test verifying handshake behavior when `session_id` is provided without `thread_id` (and when both `thread_id` and `session_id` are omitted).

## Risks & Considerations

- **Backward Compatibility with Existing Tests**: Must ensure all tests in `services/api/tests/test_websocket_streaming_chat.py` and `uis/backoffice/__tests__/supportAgentChat.test.ts` continue to pass with zero regressions.
- **Double Emission Prevention**: If a fallback finalizer runs on `TimeoutError` during `abort_active_generation`, the late task unwinding must check the idempotent finalization flag so it does not emit a second `generation_interrupted` frame or overwrite the redirected turn's state.

## Open Questions

- None. All findings are grounded in the codebase and ready for remediation via `/speckit-bug-fix`.
