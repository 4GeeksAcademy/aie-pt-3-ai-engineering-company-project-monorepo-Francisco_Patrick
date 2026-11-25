# Bug Fix: Simulated Token Streaming, Unaborted LLM Generation & ChatSession / Event Naming Mismatch

- **Slug**: simulated-streaming-session-contract
- **Fixed**: 2026-11-25
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Replaced simulated post-generation chunk playback with true incremental streaming generation (`stream_grounded_answer` with `stream=True` SSE streaming and mid-flight generator cancellation on `abort_event`) decoupled from `_prepare_pre_generation_state`, and aligned the domain, presentation, and frontend contracts to expose `ChatSession` (`agent_id`, `client_id`, `user_id`, `status`) alongside `user_id`, `session_snapshot`, and `interrupt_requested`.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `services/api/domain/knowledge/ports.py` | modified | Added `stream_grounded_answer` streaming generator port method on `LLMGenerationPort` accepting `abort_event`. |
| `services/api/infrastructure/adapters/grounded_generation_adapter.py` | modified | Implemented `stream_grounded_answer`, `_stream_with_external_llm` (`client.stream("POST", ..., json={..., "stream": True})` for OpenAI SSE & Gemini `:streamGenerateContent?alt=sse`), and `_stream_deterministically` with cooperative `abort_event` checks on every delta. |
| `data/pipelines/rag_pipeline.py` | modified | Added `stream_generate_answer` and `build_citations_from_context` to yield live generation deltas without pre-generating a monolithic response. |
| `services/api/application/services/support_agent_service.py` | modified | Decoupled `_prepare_pre_generation_state` from answer synthesis so it only runs pre-generation nodes (`intake`, guardrails, tools, `retrieval`, `tool_fallback`, `refusal`); added `_iter_generation_deltas` and updated `stream_query` to consume live deltas, close the active generator immediately on `abort_event`, and use `user_id` and `ChatSession`. |
| `services/api/domain/agent/entities.py` | modified | Added `ChatSession` and `ChatSessionStatus` (`agent_id`, `client_id`, `user_id`, `status`), updated `ChatThreadState` to use `user_id` (with backward-compatible `owner_user_id` alias), and added `"session_snapshot"` to `AgentChatEventName`. |
| `services/api/domain/agent/ports.py` | modified | Updated `AgentChatThreadRepositoryPort` signatures to use `user_id` and session metadata (`agent_id`, `client_id`, `session_status`). |
| `services/api/infrastructure/adapters/tinydb_chat_thread_repository.py` | modified | Updated TinyDB persistence and queries to store/filter by `user_id` and `ChatSession` fields while maintaining backward compatibility for legacy `owner_user_id` records. |
| `services/api/presentation/schemas/agent.py` | modified | Added `ChatSessionSchema`, `ServerSessionSnapshotEventSchema` (`event: "session_snapshot"`), and `ClientInterruptRequestedFrameSchema` (`event: "interrupt_requested"`), and replaced `owner_user_id` with `user_id` on `ChatThreadHistoryResponseSchema`. |
| `services/api/presentation/api/v1/agent.py` | modified | Updated WebSocket and REST history endpoints to emit `session_snapshot` with `user_id` and `session: ChatSessionSchema`, and handle `interrupt_requested` (plus backward-compatible `interrupt`). |
| `packages/shared/types/knowledge.ts` | modified | Added `ChatSessionDTO` (`ChatSession`), `ChatSessionStatus`, `ServerSessionSnapshotEventDTO` (`session_snapshot`), `ClientInterruptRequestedCommandDTO` (`interrupt_requested`), and `user_id` on `ChatThreadHistoryResponseDTO`. |
| `uis/backoffice/lib/supportAgentChatClient.ts` | modified | Updated parser and reducer to handle `session_snapshot`, `user_id`, and `ChatSessionDTO`. |
| `uis/backoffice/hooks/useSupportAgentChat.ts` | modified | Updated hook to expose `chatSession`, handle `session_snapshot`, and send `{"event": "interrupt_requested"}` on generation abort. |
| `uis/backoffice/components/knowledge/SupportAgentChatPanel.tsx` | modified | Updated documentation comment to reference `interrupt_requested`. |
| `specs/035-websocket-streaming-chat/spec.md` | modified | Updated specification to reference `ChatSession`, `user_id`, `session_snapshot`, and `interrupt_requested`. |
| `specs/035-websocket-streaming-chat/data-model.md` | modified | Updated data model documentation for `ChatSession`, `user_id`, `session_snapshot`, and `interrupt_requested`. |
| `specs/035-websocket-streaming-chat/contracts/websocket-chat-api.yaml` | modified | Updated OpenAPI schema to include `ChatSessionSchema`, `user_id`, `session_snapshot`, and `interrupt_requested`. |
| `specs/035-websocket-streaming-chat/contracts/websocket-chat-events.schema.json` | modified | Updated JSON Schema definitions for `ChatSession`, `ServerSessionSnapshotEvent`, and `ClientInterruptRequestedFrame`. |
| `services/api/tests/test_websocket_streaming_chat.py` | modified | Updated existing WebSocket/REST assertions for `session_snapshot`, `interrupt_requested`, `user_id`, and `ChatSession`, and added `test_true_llm_streaming_and_mid_generation_abort_stops_model_stream`. |
| `uis/backoffice/__tests__/supportAgentChat.test.ts` | modified | Added unit tests validating `session_snapshot`, `interrupt_requested`, `user_id`, and `ChatSession` parsing and serialization. |

## Diff Highlights (optional)

```python
# services/api/application/services/support_agent_service.py
            gen_start_ns = time.perf_counter()
            delta_iterator = self._iter_generation_deltas(
                state=state,
                prefix_segments=prefix_segments,
                requires_rag_stream=requires_rag_stream,
                abort_event=abort_event,
            )

            _SENTINEL = object()
            chunk_index = 0
            while True:
                if turn_finalized or (
                    abort_event is not None and abort_event.is_set()
                ):
                    return _persist_and_publish_interrupted(_resolve_abort_reason())

                active_iter = delta_iterator
                if active_iter is None:
                    break

                next_piece = await run_in_threadpool(
                    next,
                    active_iter,
                    _SENTINEL,
                )
                if next_piece is _SENTINEL:
                    break
```

## Tests Added or Updated

- `services/api/tests/test_websocket_streaming_chat.py::test_true_llm_streaming_and_mid_generation_abort_stops_model_stream` — Pins down `ChatSession` fields (`agent_id`, `client_id`, `user_id`, `status`), verifies `GroundedGenerationAdapter.stream_grounded_answer` dispatches `client.stream("POST", ..., json={..., "stream": True})` and closes the HTTP stream mid-flight when `abort_event` is set, and confirms `SupportAgentService.stream_query` does not invoke blocking `generate_grounded_answer` in `_prepare_pre_generation_state` and aborts the active generator mid-stream before remaining tokens are produced.
- `services/api/tests/test_websocket_streaming_chat.py` (`test_us1_*`, `test_us2_*`, `test_us3_*`, `test_us4_*`) — Updated to verify `session_snapshot`, `interrupt_requested`, `user_id`, and `session` (`ChatSession`) metadata across WebSocket and REST endpoints.
- `uis/backoffice/__tests__/supportAgentChat.test.ts` — Added unit tests for `interrupt_requested` command serialization and `session_snapshot` event parsing with `ChatSession` (`agent_id`, `client_id`, `user_id`, `status`).

## Local Verification

- Commands run:
  - `.venv\Scripts\python.exe -m pytest services/api/tests/test_websocket_streaming_chat.py -q` → `12 passed in 11.93s`
  - `npm.cmd test --prefix uis/backoffice -- __tests__/supportAgentChat.test.ts` → `1 passed test suite (7 passed tests)`
  - `npx.cmd tsc --noEmit --project uis/backoffice/tsconfig.json` → `0 errors (exit code 0)`
- Manual checks: Verified strict TypeScript compliance (`strict: true`, `exactOptionalPropertyTypes`, zero `any`, explicit return types, `import type`) and backward-compatible alias deserialization in `ChatThreadState.from_dict`.

## Deviations from Assessment

None.

## Follow-ups

- Run `/speckit-bug-test slug=simulated-streaming-session-contract` to record the formal verification report.
