/**
 * Shared Data Transfer Objects (DTOs) for TrackFlow RAG, Knowledge Base & Real-Time Support Agent WebSocket Chat.
 *
 * Defines strict contract interfaces consumed across frontend UIs (`uis/backoffice`)
 * and internal utilities when communicating with `/api/v1/knowledge/*` and `/api/v1/agent/*` endpoints.
 */

/**
 * Represents a verifiable citation pointing to a source corporate policy document and section.
 */
export interface KnowledgeSourceCitationDTO {
  /** Canonical source document slug (e.g. "sla-delivery", "returns-policy", "carrier-coverage", "storage-pricing"). */
  source_document: string;
  /** Title or subtitle of the cited section within the source document. */
  section: string;
  /** Cosine similarity score in range [0.0, 1.0]. */
  similarity_score: number;
}

/**
 * Request payload for submitting a natural-language question to the TrackFlow knowledge base.
 */
export interface KnowledgeQueryRequestDTO {
  /** Plain-text natural-language question (3 to 1000 characters). */
  query: string;
  /** Optional ISO 639-1 preferred response language code (defaults to "en"). */
  language?: string | undefined;
  /** Optional maximum number of candidate chunks to retrieve (1 to 10, defaults to 3). */
  top_k?: number | undefined;
  /** Optional minimum similarity score threshold (0.0 to 1.0, defaults to 0.62). */
  min_score?: number | undefined;
}

/**
 * Synthesized grounded response returned by the TrackFlow knowledge base endpoint.
 */
export interface KnowledgeQueryResponseDTO {
  /** Echoed sanitized input query. */
  query: string;
  /** Grounded synthesized natural-language answer in TrackFlow sales persona. */
  answer: string;
  /** True if the inquiry was refused due to low confidence or missing documentation. */
  is_refusal: boolean;
  /** List of verifiable source citations supporting the answer. */
  sources: KnowledgeSourceCitationDTO[];
  /** End-to-end processing time in milliseconds. */
  execution_time_ms: number;
}

/**
 * Operational health and index metrics for the Qdrant knowledge base collection.
 */
export interface KnowledgeHealthResponseDTO {
  /** Operational status indicator of the vector store collection. */
  status: "healthy" | "degraded" | "unhealthy";
  /** Active Qdrant collection name ("trackflow_knowledge"). */
  collection_name: string;
  /** Total number of vector points indexed in the collection. */
  indexed_points_count: number;
  /** Dimensionality of stored embedding vectors (384). */
  vector_dimensions: number;
}

/**
 * Role of a conversational turn in the Support Agent chat timeline.
 */
export type ChatTurnRole = "user" | "assistant";

/**
 * Lifecycle state of a conversational turn in the Support Agent chat timeline.
 */
export type ChatTurnStatus = "streaming" | "completed" | "interrupted" | "error";

/**
 * Cause of a server-side generation interruption.
 */
export type ChatInterruptedReason =
  | "client_interrupt"
  | "redirect_new_message"
  | "client_disconnect";

/**
 * Connection lifecycle states for the Support Agent WebSocket chat session.
 */
export type WebSocketChatConnectionStatus =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "disconnected"
  | "unauthorized";

/**
 * Authoritative operating jurisdiction for an order or session.
 */
export type AgentOperatingCountry = "US" | "ES";

/**
 * Authenticated caller session context for order ownership and US/ES jurisdiction checks.
 */
export interface AgentAuthenticatedSessionContextDTO {
  /** Unique session or thread identifier. */
  session_id: string;
  /** Authenticated customer or brand account ID. */
  customer_id: string;
  /** Customer business segment ('B2B' or 'B2C'). */
  customer_segment?: "B2B" | "B2C" | undefined;
  /** Default operating country for the session ('US' or 'ES'). */
  primary_operating_country?: AgentOperatingCountry | undefined;
  /** List of order or tracking identifiers owned by the authenticated session. */
  authorized_order_ids?: string[] | undefined;
  /** Optional per-order operational country mapping. */
  order_country_map?: Record<string, AgentOperatingCountry> | undefined;
}

/**
 * Summary of an operational read-only tool invocation during an agent turn.
 */
export interface AgentToolCallTraceDTO {
  /** Identifier of the invoked operational tool. */
  tool_name: "ticket_tool" | "inventory_tool";
  /** Outcome status of the tool call. */
  status: "success" | "not_found" | "timeout" | "error";
  /** Total matching records prior to the 20-record slice. */
  total_matched: number;
  /** Number of records returned into agent state (0..20). */
  returned_count: number;
  /** Tool execution duration in milliseconds. */
  latency_ms: number;
  /** Sanitized failure message when status is not_found, timeout, or error. */
  error_message?: string | null | undefined;
}

/**
 * Candidate operational memory proposed during single-turn evaluation.
 */
export interface AgentMemoryProposalDTO {
  /** Unique proposal UUID. */
  proposal_id: string;
  /** Operational memory category. */
  category: "carrier_rule" | "incident_context" | "b2b_preference";
  /** Target carrier, branch/region, or B2B client identifier. */
  target_entity: string;
  /** Optional ISO 2-letter country code ('ES', 'US'). */
  country_code?: string | null | undefined;
  /** Normalized rule summary proposed to the operator. */
  summary: string;
  /** Current proposal lifecycle status. */
  status: "pending" | "approved" | "rejected" | "edited" | "discarded";
  /** Self-evaluation confidence score in [0.0, 1.0]. */
  confidence: number;
  /** ISO-8601 UTC timestamp of proposal creation. */
  created_at: string;
}

/**
 * Sanitized guardrail intervention audit record triggered during an agent turn.
 */
export interface AgentGuardrailInterventionDTO {
  /** Unique audit event UUID. */
  event_id: string;
  /** ISO-8601 UTC timestamp of the intervention. */
  timestamp: string;
  /** Session or thread identifier. */
  session_id: string;
  /** Correlated LangGraph execution trace UUID. */
  trace_id?: string | null | undefined;
  /** Primary guardrail failure classification. */
  failure_type: "structural" | "content" | "security";
  /** Guardrail layer triggered. */
  layer: "input_guard" | "authorization_guard" | "context_sanitizer" | "output_guard";
  /** Specific semantic violation or routing category. */
  input_category: string;
  /** Machine-readable trigger rule code. */
  reason_code: string;
  /** Enforcement outcome. */
  disposition: "blocked" | "redirected" | "deflected" | "clarified";
  /** Sanitized preview snippet with PII and restricted domain data masked. */
  redacted_preview: string;
}

/**
 * Synchronous response payload returned by `POST /api/v1/agent/query`.
 */
export interface AgentQueryResponseDTO {
  /** Echoed sanitized customer inquiry. */
  query: string;
  /** Synthesized grounded answer, hybrid partial answer, fallback notice, or refusal. */
  answer: string;
  /** Whether the inquiry was refused. */
  is_refusal: boolean;
  /** Whether an operational tool degraded/timed out and traversed tool_fallback. */
  fallback_triggered: boolean;
  /** List of cited policy documents and sections. */
  sources: KnowledgeSourceCitationDTO[];
  /** Ordered list of data sources consulted ('ticket_tool', 'inventory_tool', 'rag', 'agent_memory'). */
  sources_consulted: string[];
  /** Ordered summary of operational tool invocations. */
  tool_calls: AgentToolCallTraceDTO[];
  /** Optional structured memory candidate proposed during single-call evaluation. */
  memory_proposal: AgentMemoryProposalDTO | null;
  /** Recalled persistent operational rules applied in this turn. */
  recalled_memories: string[];
  /** Guardrail interventions triggered during this turn. */
  guardrail_interventions: AgentGuardrailInterventionDTO[];
  /** Authoritative operating country resolved for the inquiry. */
  resolved_country: AgentOperatingCountry | null;
  /** Unique execution trace UUID for audit and state inspection. */
  trace_id: string;
  /** Chronological sequence of LangGraph nodes executed. */
  node_sequence: string[];
  /** Total workflow execution duration in milliseconds. */
  execution_time_ms: number;
}

/**
 * Single user or assistant conversational turn in a Support Agent thread timeline.
 */
export interface ChatMessageDTO {
  /** Unique identifier for this conversational turn. */
  turn_id: string;
  /** Bound conversation thread identifier. */
  thread_id: string;
  /** Bound session identifier. */
  session_id: string;
  /** Author role of the turn ('user' or 'assistant'). */
  role: ChatTurnRole;
  /** Full message text or accumulated partial text if interrupted. */
  content: string;
  /** Lifecycle state of the turn ('streaming', 'completed', 'interrupted', 'error'). */
  status: ChatTurnStatus;
  /** For assistant turns, references the triggering user turn_id. */
  parent_user_turn_id?: string | null | undefined;
  /** Cause of interruption when status is 'interrupted'. */
  interrupted_reason?: ChatInterruptedReason | null | undefined;
  /** Whether the turn resulted in a policy, mutation, or guardrail refusal. */
  is_refusal: boolean;
  /** Whether an operational tool degraded/timed out and traversed tool_fallback. */
  fallback_triggered: boolean;
  /** Correlated AgentTrace.trace_id in TraceRegistryPort. */
  trace_id?: string | null | undefined;
  /** Ordered LangGraph nodes executed for this turn. */
  node_sequence: string[];
  /** Turn execution duration in milliseconds. */
  execution_time_ms: number;
  /** Grounded corporate policy citations. */
  sources: KnowledgeSourceCitationDTO[];
  /** Data sources consulted ('ticket_tool', 'inventory_tool', 'rag', 'agent_memory'). */
  sources_consulted: string[];
  /** Summary of read-only operational tool calls executed during the turn. */
  tool_calls: AgentToolCallTraceDTO[];
  /** Candidate operational memory proposed during this turn, if any. */
  memory_proposal: AgentMemoryProposalDTO | null;
  /** Confirmed cross-session rules recalled and applied in this turn. */
  recalled_memories: string[];
  /** Sanitized guardrail audit records triggered during this turn. */
  guardrail_interventions: AgentGuardrailInterventionDTO[];
  /** Authoritative operating jurisdiction resolved for the turn. */
  resolved_country: AgentOperatingCountry | null;
  /** ISO-8601 UTC timestamp when the turn started. */
  created_at: string;
  /** ISO-8601 UTC timestamp when the turn completed or was interrupted. */
  updated_at: string;
}

/**
 * Persisted thread history and checkpoint snapshot returned by `GET /api/v1/agent/threads/{thread_id}/history`.
 */
export interface ChatThreadHistoryResponseDTO {
  /** Bound conversation thread identifier. */
  thread_id: string;
  /** Bound session identifier. */
  session_id: string;
  /** Authenticated operator's user ID owning this thread. */
  owner_user_id: string;
  /** Chronologically ordered list of user and assistant turns (including interrupted partial turns). */
  messages: ChatMessageDTO[];
  /** Active unconfirmed MemoryProposal on this thread, if any. */
  pending_proposal: AgentMemoryProposalDTO | null;
  /** Most recent LangGraph checkpointer snapshot ID for this thread_id. */
  latest_checkpoint_id: string | null;
  /** Monotonically increasing per-thread event sequence counter. */
  latest_sequence_id: number;
  /** Count of LangGraph checkpoints recorded for this thread_id. */
  checkpoint_count: number;
  /** ISO-8601 UTC creation timestamp of the thread. */
  created_at: string;
  /** ISO-8601 UTC timestamp of most recent turn update or interruption. */
  updated_at: string;
}

/**
 * Server-to-client WebSocket event emitted upon initial connection, reconnection, or explicit `rehydrate` command.
 */
export interface ServerSessionRehydratedEventDTO {
  /** Discriminator event name. */
  event: "session_rehydrated";
  /** Bound conversation thread identifier. */
  thread_id: string;
  /** Bound session identifier. */
  session_id: string;
  /** Authenticated operator's user ID owning this thread. */
  owner_user_id: string;
  /** Chronologically ordered list of user and assistant turns. */
  messages: ChatMessageDTO[];
  /** Active unconfirmed MemoryProposal on this thread, if any. */
  pending_proposal: AgentMemoryProposalDTO | null;
  /** Most recent LangGraph checkpointer snapshot ID for this thread_id. */
  latest_checkpoint_id: string | null;
  /** Count of LangGraph checkpoints recorded for this thread_id. */
  checkpoint_count: number;
  /** Monotonic per-thread sequence ID. */
  sequence_id: number;
  /** ISO-8601 UTC emission timestamp. */
  timestamp: string;
}

/**
 * Server-to-client WebSocket event emitted when an assistant generation turn starts executing.
 */
export interface ServerGenerationStartedEventDTO {
  /** Discriminator event name. */
  event: "generation_started";
  /** Bound conversation thread identifier. */
  thread_id: string;
  /** Bound session identifier. */
  session_id: string;
  /** Unique identifier of the new assistant turn. */
  turn_id: string;
  /** Identifier of the triggering user turn. */
  user_turn_id: string;
  /** Sanitized user query being processed. */
  query: string;
  /** Monotonic per-thread sequence ID. */
  sequence_id: number;
  /** ISO-8601 UTC emission timestamp. */
  timestamp: string;
}

/**
 * Server-to-client WebSocket event emitted incrementally for each streamed token or word chunk.
 */
export interface ServerTokenChunkEventDTO {
  /** Discriminator event name. */
  event: "token_chunk";
  /** Bound conversation thread identifier. */
  thread_id: string;
  /** Bound session identifier. */
  session_id: string;
  /** Unique identifier of the streaming assistant turn. */
  turn_id: string;
  /** Zero-based index of this chunk within the turn. */
  chunk_index: number;
  /** Incremental token/word delta string. */
  delta: string;
  /** Full accumulated assistant text up to and including this chunk. */
  accumulated_content: string;
  /** Monotonic per-thread sequence ID. */
  sequence_id: number;
  /** ISO-8601 UTC emission timestamp. */
  timestamp: string;
}

/**
 * Server-to-client WebSocket event emitted immediately upon cooperative task cancellation.
 */
export interface ServerGenerationInterruptedEventDTO {
  /** Discriminator event name. */
  event: "generation_interrupted";
  /** Bound conversation thread identifier. */
  thread_id: string;
  /** Bound session identifier. */
  session_id: string;
  /** Unique identifier of the interrupted assistant turn. */
  turn_id: string;
  /** Accumulated partial text up to the instant of abort. */
  partial_content: string;
  /** Permanent interrupted status marker. */
  status: "interrupted";
  /** Cause of interruption ('client_interrupt', 'redirect_new_message', 'client_disconnect'). */
  reason: ChatInterruptedReason;
  /** Monotonic per-thread sequence ID. */
  sequence_id: number;
  /** ISO-8601 UTC emission timestamp. */
  timestamp: string;
}

/**
 * Server-to-client WebSocket event emitted after all token chunks and post-stream output guardrail validation succeed.
 */
export interface ServerGenerationCompletedEventDTO {
  /** Discriminator event name. */
  event: "generation_completed";
  /** Bound conversation thread identifier. */
  thread_id: string;
  /** Bound session identifier. */
  session_id: string;
  /** Unique identifier of the completed assistant turn. */
  turn_id: string;
  /** Echoed sanitized query. */
  query: string;
  /** Final validated assistant response content. */
  content: string;
  /** Completed turn status marker. */
  status: "completed";
  /** Whether the turn resulted in a refusal. */
  is_refusal: boolean;
  /** Whether an operational tool degraded/timed out and traversed tool_fallback. */
  fallback_triggered: boolean;
  /** Unique execution trace UUID recorded in TraceRegistryPort. */
  trace_id: string;
  /** Chronological sequence of LangGraph nodes executed. */
  node_sequence: string[];
  /** Turn execution duration in milliseconds. */
  execution_time_ms: number;
  /** Grounded corporate policy citations. */
  sources: KnowledgeSourceCitationDTO[];
  /** Data sources consulted ('ticket_tool', 'inventory_tool', 'rag', 'agent_memory'). */
  sources_consulted: string[];
  /** Summary of read-only operational tool calls executed during the turn. */
  tool_calls: AgentToolCallTraceDTO[];
  /** Candidate operational memory proposed during this turn, if any. */
  memory_proposal: AgentMemoryProposalDTO | null;
  /** Confirmed cross-session rules recalled and applied in this turn. */
  recalled_memories: string[];
  /** Sanitized guardrail audit records triggered during this turn. */
  guardrail_interventions: AgentGuardrailInterventionDTO[];
  /** Authoritative operating jurisdiction resolved for the turn. */
  resolved_country: AgentOperatingCountry | null;
  /** Monotonic per-thread sequence ID. */
  sequence_id: number;
  /** ISO-8601 UTC emission timestamp. */
  timestamp: string;
}

/**
 * Server-to-client WebSocket event emitted on sanitized validation or workflow errors.
 */
export interface ServerErrorEventDTO {
  /** Discriminator event name. */
  event: "error";
  /** Bound conversation thread identifier. */
  thread_id: string;
  /** Bound session identifier. */
  session_id: string;
  /** Optional turn identifier correlated with the error. */
  turn_id: string | null;
  /** Machine-readable error classification code. */
  error_code: string;
  /** User-safe error explanation without internal stack traces. */
  detail: string;
  /** Monotonic per-thread sequence ID. */
  sequence_id: number;
  /** ISO-8601 UTC emission timestamp. */
  timestamp: string;
}

/**
 * Server-to-client WebSocket event emitted in response to a client `ping` heartbeat frame.
 */
export interface ServerPongEventDTO {
  /** Discriminator event name. */
  event: "pong";
  /** Bound conversation thread identifier. */
  thread_id: string;
  /** Bound session identifier. */
  session_id: string;
  /** Monotonic per-thread sequence ID. */
  sequence_id: number;
  /** ISO-8601 UTC emission timestamp. */
  timestamp: string;
}

/**
 * Discriminated union of all structured server-to-client Support Agent WebSocket streaming events.
 */
export type AgentChatStreamEventDTO =
  | ServerSessionRehydratedEventDTO
  | ServerGenerationStartedEventDTO
  | ServerTokenChunkEventDTO
  | ServerGenerationInterruptedEventDTO
  | ServerGenerationCompletedEventDTO
  | ServerErrorEventDTO
  | ServerPongEventDTO;

/**
 * Client-to-server first-frame JWT authentication command (when `?token=` is not passed in the URL).
 */
export interface ClientAuthenticateCommandDTO {
  /** Discriminator event name. */
  event: "authenticate";
  /** Backoffice Bearer JWT token. */
  token: string;
  /** Optional conversation thread identifier. */
  thread_id?: string | null | undefined;
  /** Optional session identifier. */
  session_id?: string | null | undefined;
}

/**
 * Client-to-server command submitting a user question (or mid-stream redirecting question).
 */
export interface ClientUserMessageCommandDTO {
  /** Discriminator event name. */
  event: "user_message";
  /** Natural-language policy or operational question (1..1000 chars). */
  query: string;
  /** Optional client-generated idempotency turn ID. */
  turn_id?: string | null | undefined;
  /** Optional thread identifier override. */
  thread_id?: string | null | undefined;
  /** Optional session identifier override. */
  session_id?: string | null | undefined;
  /** Optional preferred response language ('en' or 'es'). */
  language?: "en" | "es" | undefined;
  /** Optional maximum knowledge chunks to retrieve (1..20). */
  top_k?: number | undefined;
  /** Optional minimum similarity score threshold (0.0..1.0). */
  min_score?: number | undefined;
  /** Optional authenticated session context for order ownership and jurisdiction checks. */
  session_context?: AgentAuthenticatedSessionContextDTO | null | undefined;
}

/**
 * Client-to-server command requesting immediate server-side abort of the active streaming assistant turn.
 */
export interface ClientInterruptCommandDTO {
  /** Discriminator event name. */
  event: "interrupt";
  /** Optional target assistant turn_id to interrupt. */
  turn_id?: string | null | undefined;
  /** Optional human-readable interruption reason. */
  reason?: string | null | undefined;
}

/**
 * Client-to-server command requesting an immediate `session_rehydrated` snapshot.
 */
export interface ClientRehydrateCommandDTO {
  /** Discriminator event name. */
  event: "rehydrate";
  /** Optional last sequence ID received by the client. */
  last_sequence_id?: number | null | undefined;
}

/**
 * Client-to-server heartbeat keep-alive frame.
 */
export interface ClientPingCommandDTO {
  /** Discriminator event name. */
  event: "ping";
  /** Optional ISO-8601 client timestamp. */
  timestamp?: string | null | undefined;
}

/**
 * Discriminated union of all structured client-to-server Support Agent WebSocket commands.
 */
export type AgentChatClientCommandDTO =
  | ClientAuthenticateCommandDTO
  | ClientUserMessageCommandDTO
  | ClientInterruptCommandDTO
  | ClientRehydrateCommandDTO
  | ClientPingCommandDTO;
