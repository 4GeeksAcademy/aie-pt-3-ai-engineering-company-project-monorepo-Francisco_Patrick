# Phase 0 Research: Real-Time Bidirectional WebSocket Streaming Chat with True Generation Abort (Part 2)

**Feature Branch**: `035-websocket-streaming-chat`  
**Date**: 2026-11-24  
**Specification**: [spec.md](./spec.md)  
**Briefing Reference**: [docs/real-time-notification/trackflow-BRIEFING.es.md](../../docs/real-time-notification/trackflow-BRIEFING.es.md) (§5 Domain Context Alignment)

---

## 1. Unknowns & Architectural Decisions Resolved

### 1.1 Bidirectional WebSocket Transport & FastAPI Endpoint Architecture

- **Decision**: Expose a full-duplex WebSocket endpoint at `/api/v1/agent/ws` (and legacy compatibility alias `/agent/ws` via dual router mounting in `services/api/main.py`) in `services/api/presentation/api/v1/agent.py`, paired with an authenticated REST companion endpoint `GET /api/v1/agent/threads/{thread_id}/history` (and `/agent/threads/{thread_id}/history`) for deterministic thread inspection and fallback state reconciliation.
- **Rationale**:
  - Unlike Part 1 (`034-sse-rfp-notifications`), where notifications were strictly unidirectional (`Server -> Client`), Part 2 requires mid-stream user interaction: while the assistant is streaming `token_chunk` events, the operator can send an `interrupt` signal or a redirecting `user_message` over the same open connection without opening a separate HTTP request or waiting for generation to finish.
  - Running two concurrent coroutines per WebSocket session (`_client_reader_loop` and `_broker_subscriber_writer_loop`) allows the server to process incoming `interrupt`, `user_message`, `rehydrate`, and `ping` frames immediately while tokens are actively streaming outbound.
- **Alternatives Considered**:
  - Server-Sent Events (SSE) + separate `POST /interrupt` endpoint: Rejected because Part 2 explicitly requires a single bidirectional real-time WebSocket channel capable of full-duplex message and control signaling.
  - Raw Socket.IO dependency: Rejected because FastAPI / Starlette native `WebSocket` follows standard RFC 6455 framing, works with browser `new WebSocket(url)` and `Starlette TestClient.websocket_connect`, and requires zero external JavaScript or Python protocol wrappers.

---

### 1.2 Backoffice JWT Authentication & Per-User Thread Ownership Binding

- **Decision**:
  - Authenticate every WebSocket connection using the existing `SecurityPort` (`JwtSecurityAdapter.decode_access_token`) and `UserService.get_user_by_id` from `services/api/presentation/dependencies.py`.
  - Support two browser-compatible token delivery mechanisms:
    1.Handshake query parameter (`?token=<jwt>&session_id=<sid>&thread_id=<tid>`) or `Authorization: Bearer <jwt>` header (for CLI/test clients).
    2. First-frame authentication message (`{"event": "authenticate", "token": "<jwt>", "session_id": "...", "thread_id": "..."}`) when no token is provided in the handshake query/header.
  - If authentication is missing, malformed, expired, or belongs to an inactive user, the server immediately closes the WebSocket with policy/auth violation code `4001` (or `1008`) before accepting or emitting any chat or agent events (FR-002, SC-002).
  - Bind each conversation `thread_id` to the authenticated user's identity (`owner_user_id = str(user.id)`, `owner_email = user.email`). If a different authenticated user attempts to connect to or query an existing `thread_id` owned by another operator, reject with close code `4003` (`THREAD_FORBIDDEN`) or HTTP `403 Forbidden` on the REST history endpoint (FR-003, Clarification 5).
- **Rationale**:
  - Standard browser `new WebSocket(url)` cannot set custom `Authorization` HTTP headers during the HTTP 101 Upgrade handshake. Supporting both handshake token validation and optional first-frame authentication ensures seamless browser connectivity and strict security compliance.
  - Enforcing `owner_user_id` per thread guarantees tenant/operator isolation across sensitive support conversations.
- **Alternatives Considered**:
  - Cookie-only WebSocket auth: Rejected because `uis/backoffice/lib/auth.ts` stores the backoffice JWT in `localStorage` under `auth_token` and passes Bearer tokens explicitly.

---

### 1.3 Decoupled Pub/Sub Event Bus (`AgentChatEventBrokerPort`) & Structured Event Protocol

- **Decision**:
  - Define an abstract port `AgentChatEventBrokerPort` in `services/api/domain/agent/ports.py` and implement a thread-safe and async-safe `AgentChatEventBroker` in `services/api/infrastructure/messaging/agent_chat_event_broker.py`.
  - The broker manages per-thread subscriber queues (`asyncio.Queue[AgentChatStreamEvent]`), monotonic per-thread `sequence_id` counters, active generation task handles (`asyncio.Task`), and cooperative cancellation events (`asyncio.Event`).
  - Use explicit, named, discriminated event schemas (`event` field) for all WebSocket frames (FR-004, FR-005):
    - **Server-to-Client Events**:
      - `session_rehydrated`: Emitted immediately after authentication and thread binding (and on explicit `rehydrate` requests), delivering `thread_id`, `session_id`, `owner_user_id`, `messages` (ordered history of `user`, `completed`, and `interrupted` turns), `pending_proposal`, and `latest_sequence_id`.
      - `generation_started`: Emitted when a new assistant turn begins (`turn_id`, `user_message_id`, `query`, `timestamp`).
      - `token_chunk`: Emitted sequentially for each streamed token or word chunk (`turn_id`, `chunk_index`, `delta`, `accumulated_content`).
      - `generation_interrupted`: Emitted immediately when an active generation is aborted (`turn_id`, `partial_content`, `reason`: `"client_interrupt" | "redirect_new_message" | "client_disconnect"`, `status`: `"interrupted"`).
      - `generation_completed`: Emitted only after all tokens have streamed and Layer 4 output guardrails have validated the accumulated text (`turn_id`, `content`, `status`: `"completed"`, `is_refusal`, `fallback_triggered`, `trace_id`, `node_sequence`, `execution_time_ms`, `sources`, `sources_consulted`, `tool_calls`, `memory_proposal`, `recalled_memories`, `guardrail_interventions`, `resolved_country`).
      - `error`: Structured sanitized error frame (`error_code`, `detail`, `turn_id`).
      - `pong`: Heartbeat response to client `ping`.
    - **Client-to-Server Events**:
      - `user_message`: Submits a natural-language question (`query`, optional `turn_id`, `language`, `top_k`, `min_score`, `session_context`). If a turn is already streaming on the thread, automatically triggers a true generation abort of the active turn (`reason="redirect_new_message"`) before starting the new turn.
      - `interrupt`: Requests immediate abort of the currently streaming assistant turn (`reason="client_interrupt"`, optional `turn_id`). Handled idempotently as a no-op if no turn is currently streaming.
      - `rehydrate`: Requests an immediate `session_rehydrated` snapshot (optionally filtered by `last_sequence_id`).
      - `ping`: Keep-alive frame answered with `pong`.
- **Rationale**:
  - Decoupling the agent producer task from the WebSocket transport loop via `AgentChatEventBrokerPort` ensures that generation lifecycle, cancellation, and persistence are deterministic and unit-testable without requiring a live socket.
  - Strict adherence to TrackFlow's support agent domain conventions (`session_id`, `thread_id`, `trace_id`, `turn_id`, `sources`, `sources_consulted`, `tool_calls`, `memory_proposal`, `guardrail_interventions`, `resolved_country`) satisfies `docs/real-time-notification/trackflow-BRIEFING.es.md` §5 with zero leakage of Part 1's `rfp_ticket_created` SSE schema.
- **Alternatives Considered**:
  - Writing directly to `websocket.send_json()` inside LangGraph nodes: Rejected because it tightly couples domain/application workflow logic to FastAPI presentation sockets and makes clean cancellation on socket drop brittle.

---

### 1.4 Real-Time Token Streaming, Guardrail Sequencing & True Generation Abort

- **Decision**:
  - **Pre-Stream Intake, Guardrails & Tool/RAG Execution**: When a `user_message` arrives for `thread_id`, the streaming runner executes the existing `SupportAgentService` workflow stages in sequence:
    1. `intake_node` (Layer 1 `InputGuardrailPort`, Layer 2 `AuthorizationGuardrailPort`, memory proposal resolution, cross-session memory recall, and autonomous source planning).
    2. If routed to `refusal_node`, or after executing planned read-only tools (`ticket_tool_node`, `inventory_tool_node`, `retrieval_node`, `tool_fallback_node` with Layer 3 `ContextSanitizerPort`), the candidate response segments are synthesized.
    3. Token streaming (`token_chunk` events): Whether tokens originate from an external streaming LLM call or deterministic grounded synthesis in `GroundedGenerationAdapter`, the response is tokenized into natural progressive chunks and published sequentially as `token_chunk` events with cooperative cancellation checkpoints before every chunk emission.
    4. Post-stream output guardrail validation (Clarification 3, FR-006): Once all token chunks are emitted (and before `generation_completed`), Layer 4 `OutputGuardrailPort.validate_output()` validates the final accumulated text (and evaluates single-turn `MemoryProposal` candidates if not blocked). The validated final answer and full metadata (`sources`, `sources_consulted`, `tool_calls`, `memory_proposal`, `guardrail_interventions`, `trace_id`) are then emitted in `generation_completed` and recorded in `TraceRegistryPort`.
  - **True Cooperative Generation Abort (FR-008, FR-009, SC-003)**:
    - Each active generation runs inside a managed `asyncio.Task` registered in `AgentChatEventBroker` for `thread_id` alongside an `abort_event: asyncio.Event`.
    - When `interrupt` arrives, a redirecting `user_message` arrives mid-stream, or the last active WebSocket subscriber for `thread_id` disconnects mid-generation (Clarification 2), `broker.abort_active_generation(thread_id, reason=...)` immediately sets `abort_event.set()` and calls `task.cancel()`.
    - The producer task catches `asyncio.CancelledError` (or detects `abort_event.is_set()`), immediately ceases token generation so **zero additional `token_chunk` events** are emitted for that turn, persists the accumulated partial assistant turn with `status="interrupted"` in the thread history store and checkpoint state, and publishes `generation_interrupted` within `< 250ms` (typically `< 10ms`).
- **Rationale**:
  - Checking `abort_event.is_set()` and awaiting cooperative cancellation at every token step and node boundary guarantees that an aborted turn never emits trailing tokens after `generation_interrupted` and never wastes compute after the operator redirects or disconnects.
  - Preserving the partial assistant message with `status="interrupted"` in thread history ensures both the live UI and future reconnections see the exact partial output produced prior to interruption.
- **Alternatives Considered**:
  - Client-only UI ignore on abort (letting the server finish generation in the background): Explicitly forbidden by FR-008 and SC-003, which mandate true server-side task cancellation and zero subsequent `token_chunk` events.

---

### 1.5 Dual In-Memory + Durable TinyDB Thread History Persistence & Reconnection Rehydration

- **Decision**:
  - Define `AgentChatThreadRepositoryPort` in `services/api/domain/agent/ports.py` and implement a thread-safe TinyDB persistence adapter `TinyDBAgentChatThreadRepository` in `services/api/infrastructure/adapters/tinydb_chat_thread_repository.py` (following the exact pattern of `TinyDBAgentMemoryRepository`).
  - Persist every `ChatThreadState` (`thread_id`, `session_id`, `owner_user_id`, `owner_email`, ordered `messages: List[ChatMessage]`, `pending_proposal`, `latest_checkpoint_id`, `created_at`, `updated_at`) in both the in-memory `AgentChatEventBroker` state cache and `TinyDBAgentChatThreadRepository`.
  - On initial WebSocket connection or automatic progressive-backoff reconnection (`1s, 2s, 4s, 8s, 16s, cap 30s`) with an existing `thread_id` / `session_id`:
    1. If the in-memory broker lacks the thread (e.g. after a server restart), it loads the persisted `ChatThreadState` from `TinyDBAgentChatThreadRepository` and queries `SupportAgentService.get_checkpoints(thread_id)` / `memory_service.get_pending_proposal(thread_id)`.
    2. The server immediately emits `session_rehydrated` carrying the full ordered turn list (including `user` turns, `completed` assistant turns with citations/metadata, and `interrupted` partial assistant turns).
    3. The frontend client (`useSupportAgentChat` + `supportAgentChatClient.ts`) reconciles and deduplicates turns by `turn_id` (`message_id`) so zero messages are lost or duplicated across disconnects (FR-011, FR-012, SC-005).
- **Rationale**:
  - Satisfies Clarification 4 and Constitution Principle I (Database & Persistence Isolation): all persistence lives behind a repository port in `services/api/infrastructure/adapters/`, uses `MemoryStorage` by default in isolated unit tests or `AGENT_CHAT_DB_PATH` / shared TinyDB table `agent_chat_threads` for durable runtime persistence, and survives both transient socket drops and server restarts.
- **Alternatives Considered**:
  - In-memory-only history: Rejected by Clarification 4 because history must mirror to a backend persistence adapter to survive server restarts.

---

### 1.6 Backoffice `/knowledge` Upgrade with Live Token Rendering & Synchronous Fallback

- **Decision**:
  - Upgrade `uis/backoffice/app/knowledge/page.tsx` to host the interactive real-time WebSocket Support Agent chat interface (`SupportAgentChatPanel`) while retaining a mode toggle / automatic fallback to synchronous `POST /api/v1/agent/query` (and `POST /api/v1/knowledge/query` compatibility for existing unit tests) (Clarification 1, FR-007, FR-010, FR-011).
  - Build a dedicated client library `uis/backoffice/lib/supportAgentChatClient.ts` and React hook `uis/backoffice/hooks/useSupportAgentChat.ts` providing:
    - Real-time `token_chunk` accumulation and progressive rendering inside the active assistant message bubble.
    - Mid-response **"Detener / Interrumpir"** (`Stop Generating`) button that sends `{"event": "interrupt"}` and transitions the bubble to `status: "interrupted"` with an explicit `"Interrumpido"` / `"Interrupted"` badge while preserving all partial text rendered so far.
    - Mid-response **Redirection**: allowing the operator to type and submit a new message while a response is still streaming, which automatically aborts the active turn (preserving it as `interrupted`) and immediately begins streaming the new assistant response.
    - Connection status indicator (`connecting`, `connected`, `reconnecting`, `disconnected`, `unauthorized`) with progressive exponential backoff (`1s, 2s, 4s, 8s, 16s, 30s`).
    - Rich assistant turn metadata display upon `generation_completed` (source citations, consulted sources badges, operational tool summaries, guardrail intervention badges, and interactive `MemoryProposal` approve/reject confirmation prompts).
- **Rationale**:
  - Directly fulfills Clarification 1 and User Stories 1–4 while keeping existing `/knowledge` accessibility, Core Web Vitals (non-blocking client WebSocket effect), and strict TypeScript (`strict: true`, zero `any`, explicit JSDoc) standards intact.
