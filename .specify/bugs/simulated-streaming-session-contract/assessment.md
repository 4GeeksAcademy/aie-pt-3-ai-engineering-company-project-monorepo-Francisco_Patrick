# Bug Assessment: Simulated Token Streaming, Unaborted LLM Generation & ChatSession / Event Naming Mismatch

- **Slug**: simulated-streaming-session-contract
- **Created**: 2026-11-25
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> The streaming is simulated: `stream_query` waits for `_prepare_pre_generation_state` to generate the full response using `rag_generate_answer` (via an HTTP request without `stream=True`), then breaks that text into chunks and emits them with `sleep`. An interruption only stops this playback; the model has already finished, so the original generation process is not actually aborted. You should implement true streaming—using LangGraph or the model itself—and emit each delta from the generation loop, while supporting cancellation. Furthermore, the interface does not match the specification: `ChatSession` (containing `agent_id`, `client_id`, `user_id`, and `status`) is missing, and you are using `owner_user_id`/`session_rehydrated`/`interrupt` instead of `user_id`/`session_snapshot`/`interrupt_requested`. Please update the names to align with the specification.

## Symptom

1. **Simulated token streaming & non-aborted LLM generation**: `SupportAgentService.stream_query` executes `self._prepare_pre_generation_state(...)` synchronously inside `run_in_threadpool`, which calls `rag_generate_answer(...)` -> `GroundedGenerationAdapter.generate_grounded_answer(...)` -> `_generate_with_external_llm(...)` via a blocking `client.post(...)` without `stream=True`. Only after the entire answer string is synthesized does `stream_query` split `candidate_answer` with `tokenize_for_streaming` and replay chunks in a loop using `await asyncio.sleep(effective_delay)`. Consequently, an interruption during token emission only halts the post-hoc playback loop after the model generation has already completed (or fails to abort an in-flight model stream).
2. **Missing `ChatSession` domain entity / schema & mismatched event/field identifiers**:
   - No `ChatSession` entity/schema (containing `agent_id`, `client_id`, `user_id`, and `status`) exists in the domain, presentation schemas, or TypeScript shared types.
   - Thread ownership and rehydration payloads use `owner_user_id` instead of `user_id`.
   - The server rehydration event is named `session_rehydrated` instead of `session_snapshot`.
   - The client interruption command event is named `interrupt` instead of `interrupt_requested`.

## Reproduction

1. Open a WebSocket connection to `/api/v1/agent/ws` (or inspect `SupportAgentService.stream_query` in `services/api/application/services/support_agent_service.py:641-907`).
2. Send a `user_message` query that triggers RAG generation (`contexts` non-empty). Observe that `_prepare_pre_generation_state` (`support_agent_service.py:614`) invokes `rag_generate_answer` (`data/pipelines/rag_pipeline.py:157`), which calls `GroundedGenerationAdapter._generate_with_external_llm` (`grounded_generation_adapter.py:148-186`) using blocking `client.post(...)` without `stream=True`.
3. Observe that zero `token_chunk` events are emitted until `_prepare_pre_generation_state` returns the complete `candidate_answer`, after which `stream_query` splits the full string via `tokenize_for_streaming` and loops over chunks with `await asyncio.sleep(effective_delay)` (`support_agent_service.py:877-901`).
4. Send an interrupt while `token_chunk` frames are arriving: only the post-generation playback loop is cancelled; the underlying generation call had already finished before chunk `0` was emitted.
5. Inspect the domain entities (`services/api/domain/agent/entities.py`), WebSocket schemas (`services/api/presentation/schemas/agent.py`), and frontend client (`packages/shared/types/knowledge.ts`, `uis/backoffice/lib/supportAgentChatClient.ts`): verify that `ChatSession` (`agent_id`, `client_id`, `user_id`, `status`) is absent, and `owner_user_id`, `session_rehydrated`, and `interrupt` are used in place of `user_id`, `session_snapshot`, and `interrupt_requested`.

## Suspected Code Paths

- `services/api/application/services/support_agent_service.py:432-639` (`_prepare_pre_generation_state`) — Synchronously executes `rag_generate_answer` (lines 614–632) inside pre-generation preparation rather than only preparing pre-generation state (intake, guardrails, tools, retrieval) and streaming deltas from the generation step.
- `services/api/application/services/support_agent_service.py:641-913` (`stream_query`) — Awaits `run_in_threadpool(self._prepare_pre_generation_state, ...)` to obtain the complete `candidate_answer`, then simulates streaming via `self.tokenize_for_streaming(candidate_answer)` and `await asyncio.sleep(effective_delay)`. Also accepts/propagates `owner_user_id` instead of `user_id`.
- `services/api/infrastructure/adapters/grounded_generation_adapter.py:75-208` (`generate_grounded_answer`, `_generate_with_external_llm`) — Uses blocking `httpx.Client.post` without `stream=True` (OpenAI `/v1/chat/completions` and Gemini `:generateContent`), providing no async/sync token delta generator (`stream_grounded_answer`) or cooperative `abort_event` / stream close hook during generation.
- `services/api/domain/knowledge/ports.py:87-106` (`LLMGenerationPort`) — Lacks a streaming generation method (e.g., `stream_grounded_answer`) capable of yielding token deltas as they are generated by the model/LangGraph node and aborting in-flight generation when `abort_event` is set.
- `data/pipelines/rag_pipeline.py:157-206` (`generate_answer`) — Only supports full-text synchronous generation (`generate_grounded_answer`), with no streaming generator function (`stream_generate_answer` / streaming path).
- `services/api/domain/agent/entities.py:58-66, 861-980` (`AgentChatEventName`, `ChatThreadState`, `AgentChatStreamEvent`) — Missing `ChatSession` dataclass (with `agent_id`, `client_id`, `user_id`, `status`); uses `"session_rehydrated"` in `AgentChatEventName` and `owner_user_id` on `ChatThreadState`.
- `services/api/domain/agent/ports.py:423-457` (`AgentChatThreadRepositoryPort`) — Method signatures use `owner_user_id` instead of `user_id` (or lack `user_id` alignment).
- `services/api/infrastructure/adapters/tinydb_chat_thread_repository.py:77-238` (`TinyDBAgentChatThreadRepository`) — Persists and queries `owner_user_id` instead of `user_id` (and lacks `ChatSession` metadata persistence/projection).
- `services/api/presentation/schemas/agent.py:440-523` (`ChatThreadHistoryResponseSchema`, `ClientInterruptFrameSchema`, `ServerSessionRehydratedEventSchema`) — Missing `ChatSessionSchema` (`ChatSession` with `agent_id`, `client_id`, `user_id`, `status`); defines `owner_user_id`, `event: Literal["session_rehydrated"]`, and `event: Literal["interrupt"]` instead of `user_id`, `session_snapshot`, and `interrupt_requested`.
- `services/api/presentation/api/v1/agent.py:556-1097` (`_validate_and_serialize_outbound_frame`, `get_thread_history_endpoint`, `support_agent_websocket_endpoint`) — Emits `"session_rehydrated"` with `"owner_user_id"`, expects client `"interrupt"` frames, and does not construct or expose `ChatSession` (`agent_id`, `client_id`, `user_id`, `status`).
- `packages/shared/types/knowledge.ts:268-563`, `uis/backoffice/lib/supportAgentChatClient.ts:408-436, 666`, `uis/backoffice/hooks/useSupportAgentChat.ts:252, 383` — Frontend DTOs, parser, reducer, and WebSocket hook reference `owner_user_id`, `session_rehydrated`, and `interrupt` instead of `ChatSession`, `user_id`, `session_snapshot`, and `interrupt_requested`.

## Root Cause Hypothesis

High confidence. First, during the implementation of feature `035-websocket-streaming-chat`, `_prepare_pre_generation_state` in `SupportAgentService` was written to execute not only pre-generation nodes (`intake`, `ticket_tool`, `inventory_tool`, `retrieval`, `tool_fallback`, `refusal`) but also the full synchronous `rag_generate_answer` call before returning to `stream_query`. Because `GroundedGenerationAdapter._generate_with_external_llm` performs a single non-streaming `httpx.Client.post` call (without `stream=True`) and returns the full response string at once, `stream_query` resorted to tokenizing the already-completed string (`tokenize_for_streaming`) and sleeping between chunks (`asyncio.sleep(effective_delay)`). As a result, cancelling the task during token playback never aborts an active LLM stream or LangGraph generation stream. Second, the internal specification for `035-websocket-streaming-chat` defined custom identifiers (`owner_user_id`, `session_rehydrated`, `interrupt`) and omitted the `ChatSession` model (`agent_id`, `client_id`, `user_id`, `status`), diverging from the target specification contract (`ChatSession`, `user_id`, `session_snapshot`, `interrupt_requested`).

## Proposed Remediation

**Preferred**:
1. **Implement True Streaming Generation & Real Cancellation**:
   - Decouple pre-generation state preparation from answer generation: `_prepare_pre_generation_state` must only run pre-generation nodes (Layer 1–2 intake/auth guardrails, memory recall, operational tools, and RAG retrieval with Layer 3 context sanitization) while checking `abort_event` between node transitions.
   - Add true streaming generation support to `LLMGenerationPort` and `GroundedGenerationAdapter` (e.g., `stream_grounded_answer` / async or sync iterator using `httpx` streaming `client.stream("POST", ..., json={..., "stream": True})` for OpenAI SSE chunks and Gemini `:streamGenerateContent?alt=sse`, plus progressive streaming from the generator/LangGraph `generation` node when falling back to deterministic synthesis without pre-generating the entire response before streaming begins), checking `abort_event` on every delta and closing the HTTP stream immediately upon cancellation or `abort_event.is_set()`.
   - In `SupportAgentService.stream_query`, iterate directly over the live generation delta stream (via LangGraph streaming / model streaming generator), emitting each `token_chunk` delta as it is produced and immediately aborting the underlying stream/task when `interrupt_requested`, a redirecting `user_message`, or a last-subscriber disconnect occurs.
2. **Align Interface, Entity & Event Names with the Specification**:
   - Introduce `ChatSession` in `services/api/domain/agent/entities.py`, `services/api/presentation/schemas/agent.py`, and `packages/shared/types/knowledge.ts` containing `session_id`, `thread_id`, `agent_id`, `client_id`, `user_id`, and `status` (e.g., `"active" | "streaming" | "interrupted" | "disconnected" | "closed"`), and include `session: ChatSession` (or its fields) in session snapshot / history payloads.
   - Replace `owner_user_id` with `user_id` across `ChatSession`, `ChatThreadState`, `AgentChatThreadRepositoryPort`, `TinyDBAgentChatThreadRepository`, `SupportAgentService`, REST/WebSocket schemas, and frontend TypeScript types (preserving backward-compatible alias deserialization in TinyDB `from_dict` if existing records contain `owner_user_id`).
   - Rename the server rehydration event from `session_rehydrated` to `session_snapshot` (updating `AgentChatEventName`, `ServerSessionSnapshotEventSchema`, `_send_rehydration_snapshot`, and frontend `supportAgentChatClient.ts` / `useSupportAgentChat.ts`, while optionally accepting legacy aliases if needed).
   - Rename the client interruption event from `interrupt` to `interrupt_requested` (updating `ClientInterruptRequestedFrameSchema`, `agent.py` WebSocket reader loop, and frontend `useSupportAgentChat.ts` / `supportAgentChatClient.ts`, while keeping backward compatibility if a client sends `"interrupt"`).

**Alternatives** (optional):
- **LangGraph `astream` / custom streaming node writer**: Stream directly from LangGraph's async execution (`compiled_graph.astream(..., stream_mode=...)` or an async streaming generation node that yields deltas into the broker/callback as the model stream produces them). Using an async streaming generation step coupled with `GroundedGenerationAdapter` HTTP streaming (`stream=True`) ensures both LangGraph state progression and true model token streaming can be cancelled mid-flight.

**Files likely to change**:
- `services/api/domain/knowledge/ports.py`
- `services/api/infrastructure/adapters/grounded_generation_adapter.py`
- `data/pipelines/rag_pipeline.py`
- `services/api/domain/agent/entities.py`
- `services/api/domain/agent/ports.py`
- `services/api/infrastructure/adapters/tinydb_chat_thread_repository.py`
- `services/api/infrastructure/messaging/agent_chat_event_broker.py`
- `services/api/application/services/agent_workflow.py`
- `services/api/application/services/support_agent_service.py`
- `services/api/presentation/schemas/agent.py`
- `services/api/presentation/api/v1/agent.py`
- `packages/shared/types/knowledge.ts`
- `uis/backoffice/lib/supportAgentChatClient.ts`
- `uis/backoffice/hooks/useSupportAgentChat.ts`
- `uis/backoffice/components/knowledge/SupportAgentChatPanel.tsx`
- `services/api/tests/test_websocket_streaming_chat.py`
- `uis/backoffice/__tests__/supportAgentChat.test.ts`
- `specs/035-websocket-streaming-chat/spec.md`
- `specs/035-websocket-streaming-chat/data-model.md`
- `specs/035-websocket-streaming-chat/contracts/websocket-chat-api.yaml`
- `specs/035-websocket-streaming-chat/contracts/websocket-chat-events.schema.json`

**Tests to add or update**:
- **True model/LangGraph streaming & mid-generation abort test**: Verify that `GroundedGenerationAdapter` issues streaming requests (`stream=True` / `:streamGenerateContent`) when configured with an external LLM and yields incremental deltas from the generation loop, and that triggering `interrupt_requested` mid-stream closes/aborts the in-flight generator before remaining deltas are produced by the model (verifying the generator is not exhausted prior to streaming).
- **`ChatSession` & contract naming tests**: Verify that `ChatSession` includes `agent_id`, `client_id`, `user_id`, and `status`, that thread state and REST/WebSocket payloads expose `user_id` instead of `owner_user_id`, that the initial/rehydrate server event is `session_snapshot`, and that the client cancellation frame is `interrupt_requested`.
- **Frontend unit tests**: Update `uis/backoffice/__tests__/supportAgentChat.test.ts` to validate `session_snapshot`, `interrupt_requested`, `user_id`, and `ChatSession` DTO parsing and state reduction.

## Risks & Considerations

- **Post-stream guardrails and structured JSON LLM output**: When the external LLM streams raw text or JSON (`{"answer": "...", "memory_proposal": ...}`), streaming deltas must emit progressive answer deltas in real time while still running Layer 4 `OutputGuardrailPort.validate_output` and memory candidate extraction before `generation_completed` is published.
- **Backward compatibility in persisted TinyDB records**: Existing serialized thread documents in TinyDB may have `owner_user_id`; `ChatThreadState.from_dict` should read `data.get("user_id") or data.get("owner_user_id")` while serializing `user_id` going forward.
- **Strict TypeScript compliance**: All updates to `packages/shared/types/knowledge.ts` and `uis/backoffice` must adhere to `strict: true`, `exactOptionalPropertyTypes`, zero `any`, explicit return types, and `import type`.

## Open Questions

- None — all requirements (`true streaming` with delta emission and cancellation, `ChatSession` with `agent_id`, `client_id`, `user_id`, `status`, and renaming `owner_user_id` -> `user_id`, `session_rehydrated` -> `session_snapshot`, `interrupt` -> `interrupt_requested`) are explicitly specified in the report.
