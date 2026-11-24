# Feature Specification: Real-Time Bidirectional WebSocket Streaming Chat with True Generation Abort

**Feature Branch**: `035-websocket-streaming-chat`

**Created**: 2026-11-24

**Status**: Draft

**Input**: User description: "Core Ticket Acceptance Criteria: Bidirectional channel, Real-time token streaming, True generation abort, Live Token Rendering, JWT Authentication, Session / Thread Binding, Interrupt, Preserve & Redirect, Reconnect & Rehydrate, Pub/Sub & Structured Events, Domain Context Alignment."

## Clarifications

### Session 2026-11-24

- Q: Which backoffice UI route should host the real-time WebSocket streaming support chat? → A: Upgrade the existing Support Agent chat view in `uis/backoffice` `/knowledge` to use real-time WebSocket streaming (with optional synchronous fallback).
- Q: What should happen if the last active WebSocket subscriber for a conversation thread disconnects mid-generation? → A: Immediately cancel the active generation task, persist the partial assistant turn with status `interrupted`, and clean up the subscriber queue.
- Q: How should the server enforce output guardrails (such as PII leakage or out-of-bounds operational claims) while tokens are actively streaming? → A: Run input/auth guardrails before streaming, stream tokens in real time, and validate final accumulated text with output guardrails before `generation_completed`.
- Q: How should conversation thread message history (including completed and `interrupted` turns) be persisted for reconnection rehydration? → A: Persist conversation turns in the in-memory broker/checkpointer and mirror them to a backend persistence adapter so history survives both socket drops and server restarts.
- Q: How should the WebSocket endpoint enforce thread ownership across authenticated operators? → A: Bind each conversation thread to the authenticated user's JWT identity and reject attempts by other users to connect to or rehydrate that thread.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Live Token Streaming in Bidirectional Support Agent Chat (Priority: P1)

Backoffice operators and Customer Experience (CX) specialists interact with the TrackFlow support agent to answer shipment tracking, return policy, SLA, incident, and inventory questions across the United States and Spain. Previously, sending a query required waiting for the entire workflow and language model response to finish before any text appeared on screen. With a bidirectional real-time channel, the operator sends a message and immediately sees the assistant's response stream and render token-by-token as it is generated, while retaining full visibility into sources consulted, operational tool outcomes, memory proposals, and guardrail decisions upon turn completion.

**Why this priority**: Real-time token streaming over a bidirectional channel is the foundational user experience improvement of Part 2, eliminating perceived wait latency and enabling interactive mid-stream control.

**Independent Test**: Can be fully tested by opening the backoffice support agent chat interface as an authenticated user, submitting a domain inquiry, and verifying that multiple incremental `token_chunk` events arrive sequentially and render progressively in the active assistant message bubble before the final `generation_completed` event marks the turn complete.

**Acceptance Scenarios**:

1. **Given** an authenticated operator has an active bidirectional chat connection bound to a conversation thread, **When** the operator submits a natural-language question, **Then** the server streams structured `token_chunk` events in real time and the chat interface renders each token chunk incrementally in the assistant message bubble rather than displaying the full response all at once.
2. **Given** an active streaming assistant turn, **When** the generation finishes normally, **Then** the server emits a structured `generation_completed` event containing the finalized assistant message and turn metadata (citations, sources consulted, tool call summaries, memory proposal if any, and trace ID), and the assistant message state transitions from `streaming` to `completed`.
3. **Given** the underlying TrackFlow support agent workflow with its existing RAG retrieval, operational tools (support tickets and inventory stock), persistent memory, and multi-layered guardrails, **When** invoked via the streaming chat channel, **Then** the agent's internal domain logic, tool contracts, memory rules, and guardrail enforcement remain intact without modification or regression.

---

### User Story 2 - True Generation Abort: Interrupt, Preserve & Redirect Mid-Response (Priority: P1)

While the assistant is streaming a multi-sentence answer, an operator may realize they asked about the wrong order, want to narrow the scope, or need to pivot immediately to a different question. Because the communication channel is bidirectional, the client can transmit an interrupt or a new redirecting message while the server is actively streaming. Receiving this signal genuinely aborts the ongoing generation on the server (canceling the active task and stopping the token stream so no further tokens are produced for that turn), preserves the partial assistant text generated so far with an explicit `interrupted` status badge, and immediately accepts and starts streaming the new assistant turn when replacement input is provided.

**Why this priority**: True bidirectional mid-stream interruption and redirection is the core capability that distinguishes a full-duplex conversational channel from a unidirectional stream or a traditional request-response endpoint.

**Independent Test**: Can be independently tested by starting a multi-token assistant response, sending an interrupt signal (with or without a new replacement prompt) after the first few `token_chunk` events arrive, and verifying that: (a) the server immediately stops producing further `token_chunk` events for the original turn and emits `generation_interrupted`, (b) the partial assistant message remains visible in the conversation history marked `interrupted` (neither deleted nor overwritten), and (c) if new input was provided (or sent immediately after), a new assistant turn begins streaming right away.

**Acceptance Scenarios**:

1. **Given** an assistant response is actively streaming `token_chunk` events for turn `A`, **When** the client sends an interrupt event over the bidirectional channel mid-response, **Then** the server immediately cancels the ongoing generation task, emits a structured `generation_interrupted` event carrying the partial content accumulated up to that instant, and produces zero subsequent `token_chunk` events for turn `A`.
2. **Given** an assistant turn is interrupted mid-response after several tokens have rendered in the chat UI, **When** the `generation_interrupted` event is processed, **Then** the chat interface preserves the partial assistant message in the conversation timeline and marks its status as `interrupted` without deleting, clearing, or overwriting the partial text.
3. **Given** an assistant response is actively streaming (or has just been interrupted), **When** the user submits a new message to redirect the conversation, **Then** any in-flight generation is aborted first (preserving its partial response as `interrupted`) and a new assistant turn immediately starts streaming tokens reflecting the new user input.

---

### User Story 3 - Backoffice JWT Authentication & Session / Thread Binding (Priority: P2)

Support conversations contain sensitive operational context, customer order references, and internal policy citations. Every real-time chat connection must enforce the exact same backoffice JWT authentication policy as existing protected routes and bind deterministically to a conversation thread (`session_id` and/or LangGraph `thread_id`) during the connection handshake or URL establishment, rejecting unauthenticated or invalid-token clients before any chat events are accepted or emitted.

**Why this priority**: Securing the bidirectional socket against unauthenticated access and binding each connection to an explicit conversation thread are mandatory prerequisites for multi-turn state continuity and enterprise security compliance.

**Independent Test**: Can be independently tested by attempting to open a WebSocket connection without a token or with an invalid/expired JWT (verifying rejection before any chat events) and by connecting with a valid JWT plus a specific `session_id` / `thread_id` (verifying the session binds to that exact thread and confirmational handshake state is emitted).

**Acceptance Scenarios**:

1. **Given** a client attempting to connect to the WebSocket chat endpoint without a JWT or with an expired/malformed JWT (via query parameter or first-frame authentication), **When** the server evaluates authentication, **Then** the server rejects and closes the connection before processing or emitting any chat or agent events.
2. **Given** an authenticated client connecting with a valid backoffice JWT and an explicit `session_id` and/or `thread_id` in the handshake URL or initial frame, **When** the connection is established, **Then** the server binds the WebSocket session to that conversation thread and emits a structured session-bound confirmation / state hydration event.

---

### User Story 4 - Automatic Reconnection with Progressive Backoff & Thread Rehydration (Priority: P2)

Transient network drops, Wi-Fi switches, or proxy timeouts can disconnect an active chat session mid-conversation. When the WebSocket connection drops unexpectedly, the chat client automatically reconnects with progressive exponential backoff using the same `session_id` / `thread_id` and rehydrates the conversation from persisted thread checkpoints and message history so that no prior turns (including completed and interrupted messages) are lost.

**Why this priority**: Operators rely on multi-turn context across long support shifts; losing conversation history or requiring manual page reloads on a brief network blip disrupts operational workflows.

**Independent Test**: Can be independently tested by completing a multi-turn conversation (including at least one completed turn and one interrupted turn), simulating a WebSocket drop, observing automatic progressive-backoff reconnection with the same `session_id` / `thread_id`, and confirming the conversation history is rehydrated intact without duplicate messages.

**Acceptance Scenarios**:

1. **Given** an active chat session bound to a `session_id` / `thread_id`, **When** the WebSocket connection drops due to a network interruption, **Then** the client transitions to a reconnecting state and automatically retries connection using progressive exponential backoff (`1s, 2s, 4s, 8s, 16s`, capped at `30s`), halting retries immediately if rejected due to invalid authentication.
2. **Given** a conversation thread with existing user messages, completed assistant responses, and interrupted partial responses stored in thread history/checkpoints, **When** the client reconnects using the same `session_id` / `thread_id`, **Then** the server rehydrates the conversation state from the thread checkpoint / message history and the UI restores the thread seamlessly without losing or duplicating turns.

---

### User Story 5 - Decoupled Pub/Sub Event Bus & Domain Context Alignment (Priority: P2)

To keep the real-time transport clean, testable, and extensible, agent event production must be decoupled from WebSocket transport consumers through a publisher/subscriber (producer/consumer) pattern using named, structured events (`token_chunk`, `generation_started`, `generation_interrupted`, `generation_completed`, `session_rehydrated`, `error`) rather than a single generic untyped message or tight direct coupling between the LLM/graph runner and the raw socket. All field and entity names must strictly align with TrackFlow's established domain conventions without mixing in Part 1's SSE/RFP `Ticket` notification schema.

**Why this priority**: Decoupling event producers from WebSocket consumers prevents zombie generation tasks on socket drops, allows clean task cancellation and multi-consumer inspection, and upholds hexagonal architecture boundaries.

**Independent Test**: Can be independently tested by running unit and integration tests against the conversation pub/sub broker and event schemas in isolation from the WebSocket route, verifying that published structured events (`token_chunk`, `generation_interrupted`, `generation_completed`) are delivered to subscribers with strict domain field alignment and zero RFP SSE schema leakage.

**Acceptance Scenarios**:

1. **Given** an agent turn executing for a bound `thread_id`, **When** the agent producer emits lifecycle and token events, **Then** those events are published to a decoupled pub/sub channel/broker as distinctly named, typed event structures (`token_chunk`, `generation_interrupted`, `generation_completed`, etc.) and forwarded to subscribed WebSocket consumers.
2. **Given** all payloads exchanged over the WebSocket chat channel and persisted in conversation state, **When** inspected against project specifications and `docs/real-time-notification/trackflow-BRIEFING.es.md` (§5 restrictions), **Then** field names strictly follow TrackFlow's support agent domain conventions (`session_id`, `thread_id`, `trace_id`, `turn_id`, `sources`, `sources_consulted`, `tool_calls`, `memory_proposal`, `guardrail_interventions`, `resolved_country`) and never mix in Part 1's RFP `Ticket` SSE notification schema (`rfp_ticket_created`, `rfp_id`, `services_requested`).

---

### Edge Cases

- **Interrupt arrives when no generation is active**: If the client sends an interrupt signal after a turn has already completed or before any turn starts, the server handles it idempotently (no crash, no corrupted history, optional no-op acknowledgement) and keeps the connection open for subsequent turns.
- **Rapid consecutive user messages (redirect while streaming)**: If a user submits a new message while an assistant response is still streaming, the system deterministically aborts the active generation first, finalizes and persists the partial message with status `interrupted`, and immediately starts a new turn for the newly submitted message.
- **Client disconnects abruptly mid-generation**: If the WebSocket disconnects unexpectedly while a response is streaming, the server aborts the active generation task cleanly, persists the partial assistant turn as `interrupted` in the thread history/checkpoint so it is available upon reconnection rehydration, and unsubscribes the consumer queue without memory leaks.
- **Guardrail refusal or tool fallback on streaming path**: When a user message triggers an input/authorization/output guardrail or an operational tool timeout/fallback, the assistant response still streams (or delivers its structured refusal/fallback tokens) and completes with `generation_completed` carrying the full guardrail or fallback metadata without breaking the event protocol.
- **Pending memory proposal confirmation over WebSocket**: When a turn generates a `MemoryProposal` (from Milestone 8 Part 1), the proposal metadata is included in `generation_completed`, and the operator can confirm, reject, or edit it in subsequent conversational turns over the same WebSocket thread just as in the synchronous agent flow.
- **Invalid or expired JWT on handshake or first frame**: Unauthenticated connections are closed immediately with an appropriate WebSocket policy/auth close code (e.g., `4001` / `1008`) before any agent execution or thread state disclosure occurs.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The backend service MUST expose a bidirectional WebSocket endpoint (at `/api/v1/agent/ws` and legacy alias `/agent/ws`) enabling full-duplex communication where the client can transmit messages and control signals (`user_message`, `interrupt`, `ping`) while the server actively streams response events.
- **FR-002**: The WebSocket endpoint MUST require and validate the same backoffice JWT authentication as existing protected backoffice routes (accepted via the `token` query parameter during the handshake and/or a dedicated first-frame authentication message before any chat interaction), immediately rejecting and closing unauthenticated or invalid-token connections before emitting or accepting any chat events.
- **FR-003**: Every WebSocket connection MUST bind to a conversation context identified by `session_id` and/or LangGraph `thread_id` supplied in the handshake URL query parameters (or initial binding frame), creating or resuming the corresponding checkpointed conversation thread; each thread MUST be bound to the authenticated user's JWT identity (`user_id` / `email`), rejecting attempts by any other user to connect to or rehydrate that thread.
- **FR-004**: Agent event production MUST be decoupled from WebSocket transport consumers via a pub/sub (producer/consumer) abstraction (`AgentChatEventBrokerPort`) keyed by conversation `thread_id`, allowing the generation producer to publish structured events to a thread channel while WebSocket consumer loop(s) subscribe and forward frames to the client.
- **FR-005**: All server-to-client and client-to-server WebSocket frames MUST use explicit, named, structured event schemas discriminated by an `event` (or `type`) field—specifically including at minimum `session_bound` / `session_rehydrated`, `generation_started`, `token_chunk`, `generation_interrupted`, `generation_completed`, and `error` for server events, and `user_message` (or `send_message`), `interrupt`, and `rehydrate` / `ping` for client events—rather than a single generic untyped message format.
- **FR-006**: When a user submits a message over the WebSocket, the backend MUST execute the existing TrackFlow support agent workflow—running input and authorization guardrails before streaming begins, streaming response tokens in real time via sequential `token_chunk` events as they are produced (rather than buffering the entire response), and validating the final accumulated text against output guardrails before emitting `generation_completed`.
- **FR-007**: The backoffice chat interface inside `/knowledge` (Support Agent view, with optional synchronous fallback) MUST render incoming `token_chunk` payloads live in the active assistant message bubble as they arrive, providing progressive real-time token rendering.
- **FR-008**: When the client sends an `interrupt` signal, submits a redirecting `user_message` while a turn is currently streaming, or disconnects as the last active WebSocket subscriber for the thread mid-generation, the server MUST perform a **true generation abort**: it MUST immediately cancel the active generation task / stop the model token stream via cooperative cancellation (`asyncio.Task.cancel()` / cancellation token) so that zero further `token_chunk` events are generated or emitted for that turn, and clean up the subscriber queue.
- **FR-009**: Upon aborting an in-flight turn, the server MUST emit a `generation_interrupted` event and persist the partial assistant message accumulated up to the point of interruption with status `interrupted` in the thread's conversation history and checkpoint state.
- **FR-010**: The chat interface MUST preserve any interrupted partial assistant message in the conversation timeline with a visible `interrupted` status indicator (never deleting or overwriting the partial text) and MUST immediately accept and process new user input to start a new assistant turn reflecting the redirected request.
- **FR-011**: When a WebSocket connection drops unexpectedly, the frontend chat client MUST automatically attempt reconnection using progressive exponential backoff (`1s, 2s, 4s, 8s, 16s`, capped at `30s`, halting retries on authentication failure) with the same `session_id` / `thread_id`.
- **FR-012**: Upon connecting or reconnecting with an existing `session_id` / `thread_id`, the system MUST rehydrate the conversation state from the backend thread checkpoint and message history store—persisted in both the in-memory broker/checkpointer and a durable backend persistence adapter under `services/api/infrastructure/adapters/` (delivered via a `session_rehydrated` event and/or companion thread history endpoint `GET /api/v1/agent/threads/{thread_id}/history`)—so that all prior user messages, completed assistant messages, and `interrupted` partial assistant messages are restored in order without loss or duplication across socket drops and server restarts.
- **FR-013**: The implementation MUST preserve the existing support agent's internal domain logic, LangGraph routing, read-only operational tools (`ticket_tool`, `inventory_tool`), persistent memory lifecycle (`MemoryProposal`), and defense-in-depth guardrails without regression, and MUST adhere strictly to TrackFlow domain field names without mixing in Part 1's SSE/RFP `Ticket` notification schema (`rfp_ticket_created`, `rfp_id`, `services_requested`).

### Key Entities *(include if feature involves data)*

- **Conversation Thread (`ChatThreadState`)**: Represents a persistent multi-turn support conversation bound to a `thread_id` and `session_id`, maintaining an ordered list of `ChatMessage` turns, the latest LangGraph checkpoint reference, active pending `MemoryProposal` (if any), and `AuthenticatedSessionContext`.
- **Chat Message Turn (`ChatMessage`)**: Represents a single user or assistant turn within a conversation thread. Key attributes include `message_id` (or `turn_id`), `thread_id`, `session_id`, `role` (`user` | `assistant`), `content` (full text or accumulated partial text), `status` (`streaming` | `completed` | `interrupted` | `error`), `created_at`, `updated_at`, and optional assistant turn metadata (`trace_id`, `sources`, `sources_consulted`, `tool_calls`, `memory_proposal`, `recalled_memories`, `guardrail_interventions`, `resolved_country`, `is_refusal`, `fallback_triggered`).
- **Structured Chat Event (`AgentChatStreamEvent`)**: A typed event envelope published by the agent runner to the conversation pub/sub broker and serialized over the WebSocket (`event`: `session_rehydrated` | `generation_started` | `token_chunk` | `generation_interrupted` | `generation_completed` | `error` | `pong`, `thread_id`, `session_id`, `turn_id`, `sequence_id`, `timestamp`, and typed payload fields).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of multi-token assistant responses, the chat interface receives and renders response text incrementally across multiple `token_chunk` events before `generation_completed`, with the first token chunk arriving prior to full response completion.
- **SC-002**: 100% of unauthenticated or invalid-JWT WebSocket connection attempts are rejected before any chat or agent events are emitted.
- **SC-003**: When an `interrupt` or redirecting message is sent mid-generation, the server aborts the active generation task within 250 milliseconds, emits `generation_interrupted`, and emits 0 additional `token_chunk` events for the aborted turn.
- **SC-004**: In 100% of mid-response interruption and redirection scenarios, the partial assistant response generated prior to the interrupt remains visible in the UI and persisted in thread history with status `interrupted`, while the subsequent user message immediately initiates a new streaming assistant turn.
- **SC-005**: After an unexpected connection drop, the client automatically reconnects via progressive backoff using the same `session_id` / `thread_id` and restores 100% of prior completed and interrupted conversation turns from thread history/checkpoints with 0 duplicate messages.
- **SC-006**: 100% of existing support agent unit, integration, memory, and guardrail test suites continue to pass with zero regressions and zero leakage of Part 1 RFP SSE schema fields into the Part 2 chat protocol.

## Assumptions

- The backoffice authentication system (`services/api/presentation/dependencies.py` and `uis/backoffice/lib/auth.ts`) issues standard HS256 Bearer JWT tokens stored in the backoffice client; because browser `new WebSocket(url)` cannot set custom HTTP `Authorization` headers during the upgrade request, supporting JWT passage via query parameter (`?token=<jwt>`) and/or first-frame authentication message satisfies both browser constraints and strict authentication enforcement.
- The existing `SupportAgentService` and compiled LangGraph state machine (`services/api/application/services/support_agent_service.py` and `agent_workflow.py`) execute deterministic intake, guardrails, tool calls, RAG retrieval, and answer synthesis; adding an asynchronous token-streaming execution path (and cooperative task cancellation hook) on `SupportAgentService` allows real-time token emission while preserving the exact same domain nodes, tools, memory, and output guardrails.
- An in-process asynchronous pub/sub broker (`AgentChatEventBroker`) implementing a domain port (`AgentChatEventBrokerPort`) decouples agent producer tasks from WebSocket consumer connections and maintains thread message/checkpoint history for instant rehydration across reconnects.
- The interactive streaming chat UI will be integrated directly into the existing Support Agent view inside `/knowledge` in the backoffice application (with optional synchronous fallback) so operators can test and use real-time token streaming, mid-response interruption, redirection, and automatic reconnection with thread rehydration.
