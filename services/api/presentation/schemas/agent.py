"""Pydantic request and response schemas for TrackFlow Support Agent endpoints (T044).

Conforms strictly to:
- `specs/027-support-agent-langgraph/contracts/agent-api.yaml`
- Monorepo Constitution Principle II (Public API Compatibility & Strict Contract Serialization)
- Monorepo Constitution Principle IV (Defensive Error Handling & Zero Sensitive Data Leaks).
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from presentation.schemas.knowledge import KnowledgeSourceCitationSchema


class AuthenticatedSessionContextSchema(BaseModel):
    """Authenticated caller identity, customer segment, operating country, and owned order IDs (FR-007, FR-008)."""

    session_id: str = Field(..., min_length=1, max_length=128, description="Unique session or thread identifier")
    customer_id: str = Field(..., min_length=1, max_length=128, description="Authenticated customer or brand account ID")
    customer_segment: Literal["B2B", "B2C"] = Field(
        default="B2C", description="Customer business segment ('B2B' or 'B2C')"
    )
    primary_operating_country: Literal["US", "ES"] = Field(
        default="US", description="Default operating country for the session ('US' or 'ES')"
    )
    authorized_order_ids: List[str] = Field(
        default_factory=list,
        description="List of order or tracking identifiers owned by the authenticated session",
    )
    order_country_map: Dict[str, Literal["US", "ES"]] = Field(
        default_factory=dict,
        description="Optional per-order operational country mapping (order_id -> 'US' | 'ES')",
    )


class GuardrailInterventionSchema(BaseModel):
    """Structured audit record of a guardrail block or mandatory redirection (FR-011)."""

    event_id: str = Field(..., description="Unique audit event UUID")
    timestamp: str = Field(..., description="ISO-8601 UTC timestamp of the intervention")
    session_id: str = Field(..., description="Session or thread identifier")
    trace_id: Optional[str] = Field(default=None, description="Correlated LangGraph execution trace UUID")
    failure_type: Literal["structural", "content", "security"] = Field(
        ..., description="Primary guardrail failure classification"
    )
    layer: Literal["input_guard", "authorization_guard", "context_sanitizer", "output_guard"] = Field(
        ..., description="Guardrail layer triggered"
    )
    input_category: Literal[
        "in_domain",
        "casual_trivia",
        "personal_task",
        "jailbreak_attempt",
        "unauthorized_order",
        "policy_mismatch",
        "restricted_data_leak",
        "external_injection",
        "malformed_output",
        "out_of_domain",
        "needs_context",
    ] = Field(..., description="Specific semantic violation or routing category")
    reason_code: str = Field(..., description="Machine-readable trigger rule code")
    disposition: Literal["blocked", "redirected", "deflected", "clarified"] = Field(
        ..., description="Enforcement outcome ('blocked', 'redirected', 'deflected', or 'clarified')"
    )
    redacted_preview: str = Field(
        ...,
        description="Sanitized preview snippet with PII, restricted domain data, and system prompt fragments masked",
    )


class GuardrailSummaryResponseSchema(BaseModel):
    """Aggregated observability metric view returned by GET /api/v1/agent/guardrails/summary (FR-012)."""

    total_evaluations: int = Field(..., ge=0, description="Total evaluations performed across guardrail layers")
    total_interventions: int = Field(..., ge=0, description="Total guardrail blocks and mandatory redirections recorded")
    by_failure_type: Dict[str, int] = Field(
        default_factory=dict,
        description="Trigger counts keyed by 'structural', 'content', and 'security'",
    )
    by_layer: Dict[str, int] = Field(
        default_factory=dict,
        description="Trigger counts keyed by 'input_guard', 'authorization_guard', 'context_sanitizer', and 'output_guard'",
    )
    by_input_category: Dict[str, int] = Field(
        default_factory=dict,
        description="Trigger counts keyed by GuardrailInputCategory",
    )
    by_disposition: Dict[str, int] = Field(
        default_factory=dict,
        description="Trigger counts keyed by 'blocked' and 'redirected'",
    )
    window_start: Optional[str] = Field(default=None, description="Earliest recorded event timestamp in ISO-8601 UTC")
    window_end: Optional[str] = Field(default=None, description="Latest recorded event timestamp in ISO-8601 UTC")
    recent_events: List[GuardrailInterventionSchema] = Field(
        default_factory=list,
        description="Up to 50 most recent sanitized GuardrailAuditEvent records",
    )


class GuardrailResetResponseSchema(BaseModel):
    """Response returned by POST /api/v1/agent/guardrails/reset."""

    status: str = Field(default="cleared", description="Status code of the reset operation")
    message: str = Field(
        default="Guardrail observability metrics and audit events cleared.",
        description="Human-readable confirmation of the reset operation",
    )


class AgentQueryRequestSchema(BaseModel):
    """Request payload for submitting policy or operational inquiries to the LangGraph support agent."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Customer policy inquiry or real-time ticket/inventory question",
    )
    top_k: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Maximum number of knowledge chunks to retrieve when RAG is consulted",
    )
    min_score: Optional[float] = Field(
        default=0.62,
        ge=0.0,
        le=1.0,
        description="Calibrated minimum cosine similarity score threshold",
    )
    thread_id: Optional[str] = Field(
        default=None,
        description="Optional thread or session identifier for state checkpointing",
    )
    language: Optional[str] = Field(
        default="en",
        description="Optional target response language ISO code",
    )
    session_context: Optional[AuthenticatedSessionContextSchema] = Field(
        default=None,
        description="Optional authenticated session context for order ownership and country jurisdiction checks",
    )


class ToolCallTraceSchema(BaseModel):
    """Audit summary of an operational tool invocation during an agent run."""

    tool_name: Literal["ticket_tool", "inventory_tool"] = Field(
        ..., description="Identifier of the invoked operational tool"
    )
    status: Literal["success", "not_found", "timeout", "error"] = Field(
        ..., description="Outcome status of the tool call"
    )
    total_matched: int = Field(
        ..., ge=0, description="Total matching records prior to the 20-record slice"
    )
    returned_count: int = Field(
        ..., ge=0, le=20, description="Number of records returned into agent state"
    )
    latency_ms: float = Field(
        ..., ge=0.0, description="Tool execution duration in milliseconds"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Sanitized failure message when status is not_found, timeout, or error",
    )


class MemoryProposalSchema(BaseModel):
    """Structured memory candidate proposal returned in single-turn evaluation (FR-008, FR-010)."""

    proposal_id: str = Field(..., description="Unique proposal UUID")
    category: Literal["carrier_rule", "incident_context", "b2b_preference"] = Field(
        ..., description="Operational memory category"
    )
    target_entity: str = Field(
        ..., description="Target carrier, branch/region, or B2B client identifier"
    )
    country_code: Optional[str] = Field(
        default=None, description="Optional ISO 2-letter country code (e.g. 'ES', 'US')"
    )
    summary: str = Field(..., description="Normalized rule summary proposed to the operator")
    status: Literal["pending", "approved", "rejected", "edited", "discarded"] = Field(
        ..., description="Current proposal lifecycle status"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Self-evaluation confidence score"
    )
    created_at: str = Field(..., description="ISO-8601 UTC timestamp of proposal creation")


class MemoryProposalResponseSchema(BaseModel):
    """Response payload for retrieving the active pending memory proposal for a session."""

    proposal: Optional[MemoryProposalSchema] = Field(
        default=None, description="Active pending proposal or null if none pending"
    )


class MemoryProposalFeedbackRequestSchema(BaseModel):
    """Request payload for submitting explicit out-of-band feedback on a pending memory proposal."""

    action: Literal["approve", "reject", "edit"] = Field(
        ..., description="Explicit operator disposition on the proposal"
    )
    refined_content: Optional[str] = Field(
        default=None,
        description="Modified rule content required when action is 'edit'",
    )
    operator_id: Optional[str] = Field(
        default=None,
        description="Optional operator identifier for confirmation attribution",
    )


class MemoryProposalFeedbackResponseSchema(BaseModel):
    """Response payload returned after processing explicit proposal feedback."""

    proposal_id: str = Field(..., description="Unique proposal UUID")
    status: Literal["pending", "approved", "rejected", "edited", "discarded"] = Field(
        ..., description="Updated proposal lifecycle status"
    )
    resulting_action: str = Field(
        ..., description="Concrete system action taken ('memory_persisted', 'proposal_discarded', 'proposal_edited')"
    )
    committed_memory_id: Optional[str] = Field(
        default=None, description="Persisted memory UUID when status is 'approved'"
    )


class ConsolidatedCarrierProfileResponseSchema(BaseModel):
    """Consolidated operational profile for a carrier and country (FR-016)."""

    carrier: str = Field(..., description="Carrier identifier (e.g. 'SEUR', 'FedEx')")
    country_code: str = Field(..., description="Country ISO code ('ES', 'US')")
    active_rules: List[str] = Field(
        default_factory=list,
        description="Deduplicated list of active operational constraints (max 20)",
    )
    memory_ids: List[str] = Field(
        default_factory=list,
        description="Underlying persistent memory record UUIDs",
    )
    last_verified_at: str = Field(
        ..., description="ISO-8601 UTC timestamp of most recent rule confirmation"
    )


class MemoryAuditLogEntrySchema(BaseModel):
    """Immutable audit log record of a memory proposal lifecycle event (FR-014)."""

    log_id: str = Field(..., description="Unique audit log UUID")
    proposal_id: Optional[str] = Field(default=None, description="Associated proposal UUID")
    memory_id: Optional[str] = Field(default=None, description="Associated memory UUID if committed")
    event_type: str = Field(
        ..., description="Lifecycle event category ('proposed', 'approved', 'rejected', 'edited', 'discarded', 'evicted')"
    )
    classified_intent: Optional[str] = Field(
        default=None, description="Classified user intent ('approve', 'reject', 'edit', 'unrelated_or_ambiguous')"
    )
    user_message: str = Field(..., description="Sanitized operator message triggering the event")
    resulting_action: str = Field(..., description="Concrete system action executed")
    session_id: Optional[str] = Field(default=None, description="Session or thread identifier")
    timestamp: str = Field(..., description="ISO-8601 UTC timestamp of the audit event")
    details: Dict[str, Any] = Field(
        default_factory=dict, description="Additional structured audit metadata"
    )


class AgentQueryResponseSchema(BaseModel):
    """Response payload returned by POST /api/v1/agent/query."""

    query: str = Field(..., description="Echoed sanitized customer inquiry")
    answer: str = Field(
        ...,
        description="Synthesized grounded answer, hybrid partial answer, honest tool fallback notice, or standardized refusal",
    )
    is_refusal: bool = Field(
        ...,
        description="Whether the inquiry was refused due to blank input, write-mutation attempt, or out-of-scope policy query",
    )
    fallback_triggered: bool = Field(
        default=False,
        description="Whether an operational tool degraded, timed out, or returned not_found and traversed tool_fallback",
    )
    sources: List[KnowledgeSourceCitationSchema] = Field(
        default_factory=list,
        description="List of cited policy documents and sections",
    )
    sources_consulted: List[str] = Field(
        default_factory=list,
        description="Ordered list of data sources consulted during the run ('ticket_tool', 'inventory_tool', 'rag', 'agent_memory')",
    )
    tool_calls: List[ToolCallTraceSchema] = Field(
        default_factory=list,
        description="Ordered summary of operational tool invocations",
    )
    memory_proposal: Optional[MemoryProposalSchema] = Field(
        default=None,
        description="Optional structured memory candidate proposed during single-call evaluation",
    )
    recalled_memories: List[str] = Field(
        default_factory=list,
        description="Recalled persistent operational rules applied in this turn",
    )
    guardrail_interventions: List[GuardrailInterventionSchema] = Field(
        default_factory=list,
        description="Guardrail blocks or mandatory redirections triggered during this turn",
    )
    resolved_country: Optional[Literal["US", "ES"]] = Field(
        default=None,
        description="Authoritative operating country resolved for the inquiry",
    )
    trace_id: str = Field(
        ..., description="Unique execution trace UUID for audit and state inspection"
    )
    node_sequence: List[str] = Field(
        default_factory=list,
        description="Chronological sequence of LangGraph nodes executed",
    )
    execution_time_ms: float = Field(
        ..., ge=0.0, description="Total workflow execution duration in milliseconds"
    )


class AgentTraceResponseSchema(BaseModel):
    """Structured execution trace returned by GET /api/v1/agent/trace/{trace_id}."""

    trace_id: str = Field(..., description="Unique execution trace UUID")
    query: str = Field(..., description="Sanitized query executed in the run")
    node_sequence: List[str] = Field(
        ..., description="Chronological list of visited LangGraph nodes"
    )
    sources_consulted: List[str] = Field(
        default_factory=list,
        description="Ordered list of data sources consulted during the run",
    )
    fallback_triggered: bool = Field(
        default=False,
        description="Whether the tool_fallback node was traversed",
    )
    tool_calls: List[ToolCallTraceSchema] = Field(
        default_factory=list,
        description="Ordered summary of operational tool invocations",
    )
    step_latencies: Dict[str, float] = Field(
        ..., description="Per-node execution duration in milliseconds"
    )
    total_duration_ms: float = Field(
        ..., ge=0.0, description="Total end-to-end execution duration in milliseconds"
    )
    is_refusal: bool = Field(..., description="Whether the run ended in an honest refusal")
    final_answer: str = Field(..., description="Final answer or refusal message produced")
    source_count: int = Field(..., ge=0, description="Number of cited knowledge sources")
    node_outputs: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict,
        description="Structured output produced by each visited node during the run",
    )


class AgentHealthResponseSchema(BaseModel):
    """Health and compilation status returned by GET /api/v1/agent/health."""

    status: str = Field(..., description="Operational health status ('healthy')")
    compiled: bool = Field(..., description="Whether the LangGraph workflow is compiled")
    nodes: List[str] = Field(..., description="Registered workflow nodes")
    checkpointer: str = Field(..., description="Active state checkpointer implementation")


class SanitizedErrorResponse(BaseModel):
    """Sanitized error response payload preventing raw stack trace exposure."""

    detail: str = Field(
        ..., description="User-safe error explanation without internal tracebacks"
    )
    error_code: str = Field(..., description="Machine-readable error classification code")
    trace_id: Optional[str] = Field(
        default=None, description="Optional trace identifier if correlated to a workflow run"
    )


class ChatMessageSchema(BaseModel):
    """Conversation turn entity schema for thread history and rehydration responses (T007)."""

    turn_id: str = Field(..., description="Unique identifier for this conversational turn")
    thread_id: str = Field(..., description="Bound conversation thread identifier")
    session_id: str = Field(..., description="Bound session identifier")
    role: Literal["user", "assistant"] = Field(..., description="Author role of the turn")
    content: str = Field(
        ..., description="Full message text or accumulated partial text if interrupted"
    )
    status: Literal["streaming", "completed", "interrupted", "error"] = Field(
        default="completed", description="Lifecycle state of the turn"
    )
    parent_user_turn_id: Optional[str] = Field(
        default=None, description="Triggering user turn_id for assistant turns"
    )
    interrupted_reason: Optional[
        Literal["client_interrupt", "redirect_new_message", "client_disconnect"]
    ] = Field(default=None, description="Cause of interruption when status is 'interrupted'")
    is_refusal: bool = Field(default=False, description="Whether the turn was a refusal")
    fallback_triggered: bool = Field(
        default=False, description="Whether an operational tool triggered fallback"
    )
    trace_id: Optional[str] = Field(default=None, description="Correlated AgentTrace UUID")
    node_sequence: List[str] = Field(
        default_factory=list, description="Ordered LangGraph nodes executed for this turn"
    )
    execution_time_ms: float = Field(
        default=0.0, ge=0.0, description="Turn execution duration in milliseconds"
    )
    sources: List[KnowledgeSourceCitationSchema] = Field(
        default_factory=list, description="Grounded policy citations"
    )
    sources_consulted: List[str] = Field(
        default_factory=list, description="Data sources consulted during the turn"
    )
    tool_calls: List[ToolCallTraceSchema] = Field(
        default_factory=list, description="Operational tool call summaries"
    )
    memory_proposal: Optional[MemoryProposalSchema] = Field(
        default=None, description="Candidate operational memory proposed during this turn"
    )
    recalled_memories: List[str] = Field(
        default_factory=list, description="Confirmed cross-session rules recalled"
    )
    guardrail_interventions: List[GuardrailInterventionSchema] = Field(
        default_factory=list, description="Sanitized guardrail audit events"
    )
    resolved_country: Optional[Literal["US", "ES"]] = Field(
        default=None, description="Authoritative operating country resolved for the turn"
    )
    created_at: str = Field(..., description="ISO-8601 UTC timestamp when the turn started")
    updated_at: str = Field(
        ..., description="ISO-8601 UTC timestamp when the turn completed or was interrupted"
    )


class ChatThreadHistoryResponseSchema(BaseModel):
    """Response payload returned by GET /api/v1/agent/threads/{thread_id}/history (T007)."""

    thread_id: str = Field(..., description="Conversation thread identifier")
    session_id: str = Field(..., description="Session identifier")
    owner_user_id: str = Field(..., description="Authenticated operator user ID owning the thread")
    messages: List[ChatMessageSchema] = Field(
        default_factory=list, description="Ordered list of user and assistant turns"
    )
    pending_proposal: Optional[MemoryProposalSchema] = Field(
        default=None, description="Active pending MemoryProposal on this thread, if any"
    )
    latest_checkpoint_id: Optional[str] = Field(
        default=None, description="Most recent LangGraph checkpoint ID"
    )
    latest_sequence_id: int = Field(
        default=0, ge=0, description="Monotonically increasing per-thread event sequence counter"
    )
    checkpoint_count: int = Field(
        default=0, ge=0, description="Total LangGraph checkpoints recorded for this thread"
    )
    created_at: str = Field(..., description="ISO-8601 UTC thread creation timestamp")
    updated_at: str = Field(..., description="ISO-8601 UTC thread last-updated timestamp")


class ClientAuthenticateFrameSchema(BaseModel):
    """Client-to-server first-frame authentication command."""

    event: Literal["authenticate"] = "authenticate"
    token: str = Field(..., min_length=1)
    thread_id: Optional[str] = None
    session_id: Optional[str] = None


class ClientUserMessageFrameSchema(BaseModel):
    """Client-to-server user message command (or mid-stream redirecting prompt)."""

    event: Literal["user_message"] = "user_message"
    query: str = Field(..., min_length=1, max_length=1000)
    turn_id: Optional[str] = None
    thread_id: Optional[str] = None
    session_id: Optional[str] = None
    language: Literal["en", "es"] = "en"
    top_k: int = Field(default=3, ge=1, le=20)
    min_score: float = Field(default=0.62, ge=0.0, le=1.0)
    session_context: Optional[AuthenticatedSessionContextSchema] = None


class ClientInterruptFrameSchema(BaseModel):
    """Client-to-server mid-response interrupt command."""

    event: Literal["interrupt"] = "interrupt"
    turn_id: Optional[str] = None
    reason: Optional[str] = None


class ClientRehydrateFrameSchema(BaseModel):
    """Client-to-server rehydration request frame."""

    event: Literal["rehydrate"] = "rehydrate"
    last_sequence_id: Optional[int] = Field(default=None, ge=0)


class ClientPingFrameSchema(BaseModel):
    """Client-to-server heartbeat ping frame."""

    event: Literal["ping"] = "ping"
    timestamp: Optional[str] = None


class ServerSessionRehydratedEventSchema(BaseModel):
    """Server-to-client session_rehydrated WebSocket event."""

    event: Literal["session_rehydrated"] = "session_rehydrated"
    thread_id: str
    session_id: str
    owner_user_id: str
    messages: List[ChatMessageSchema] = Field(default_factory=list)
    pending_proposal: Optional[MemoryProposalSchema] = None
    latest_checkpoint_id: Optional[str] = None
    checkpoint_count: int = Field(default=0, ge=0)
    sequence_id: int = Field(..., ge=0)
    timestamp: str


class ServerGenerationStartedEventSchema(BaseModel):
    """Server-to-client generation_started WebSocket event."""

    event: Literal["generation_started"] = "generation_started"
    thread_id: str
    session_id: str
    turn_id: str
    user_turn_id: str
    query: str
    sequence_id: int = Field(..., ge=1)
    timestamp: str


class ServerTokenChunkEventSchema(BaseModel):
    """Server-to-client token_chunk WebSocket event."""

    event: Literal["token_chunk"] = "token_chunk"
    thread_id: str
    session_id: str
    turn_id: str
    chunk_index: int = Field(..., ge=0)
    delta: str
    accumulated_content: str
    sequence_id: int = Field(..., ge=1)
    timestamp: str


class ServerGenerationInterruptedEventSchema(BaseModel):
    """Server-to-client generation_interrupted WebSocket event."""

    event: Literal["generation_interrupted"] = "generation_interrupted"
    thread_id: str
    session_id: str
    turn_id: str
    partial_content: str
    status: Literal["interrupted"] = "interrupted"
    reason: Literal["client_interrupt", "redirect_new_message", "client_disconnect"]
    sequence_id: int = Field(..., ge=1)
    timestamp: str


class ServerGenerationCompletedEventSchema(BaseModel):
    """Server-to-client generation_completed WebSocket event."""

    event: Literal["generation_completed"] = "generation_completed"
    thread_id: str
    session_id: str
    turn_id: str
    query: str
    content: str
    status: Literal["completed"] = "completed"
    is_refusal: bool
    fallback_triggered: bool = False
    trace_id: str
    node_sequence: List[str] = Field(default_factory=list)
    execution_time_ms: float = Field(..., ge=0.0)
    sources: List[KnowledgeSourceCitationSchema] = Field(default_factory=list)
    sources_consulted: List[str] = Field(default_factory=list)
    tool_calls: List[ToolCallTraceSchema] = Field(default_factory=list)
    memory_proposal: Optional[MemoryProposalSchema] = None
    recalled_memories: List[str] = Field(default_factory=list)
    guardrail_interventions: List[GuardrailInterventionSchema] = Field(default_factory=list)
    resolved_country: Optional[Literal["US", "ES"]] = None
    sequence_id: int = Field(..., ge=1)
    timestamp: str


class ServerErrorEventSchema(BaseModel):
    """Server-to-client sanitized error WebSocket event."""

    event: Literal["error"] = "error"
    thread_id: str
    session_id: str
    turn_id: Optional[str] = None
    error_code: str
    detail: str
    sequence_id: int = Field(..., ge=1)
    timestamp: str


class ServerPongEventSchema(BaseModel):
    """Server-to-client heartbeat pong WebSocket event."""

    event: Literal["pong"] = "pong"
    thread_id: str
    session_id: str
    sequence_id: int = Field(..., ge=0)
    timestamp: str


class HITLReviewDecisionRequestSchema(BaseModel):
    """Supervisor review submission schema for HITL gates."""

    request_id: str = Field(description="UUID of pending review request")
    decision: Literal["APPROVE", "REJECT"] = Field(description="Supervisor decision")
    reviewer_id: Optional[str] = Field(
        default=None,
        description="Optional supervisor ID; ignored/overridden in favor of authenticated JWT user identity (email/id) to prevent spoofing.",
    )
    decision_notes: Optional[str] = Field(default=None, description="Operational justification notes")


class HITLApprovalResponseSchema(BaseModel):
    """Response returned upon supervisor review resolution."""

    request_id: str
    action_type: str
    entity_id: str
    requested_by_session: str
    requested_by_agent: str
    payload_snapshot: Dict[str, Any]
    monetary_impact_eur: Optional[float] = None
    status: str
    reviewer_id: Optional[str] = None
    decision_notes: Optional[str] = None
    created_at: str
    expires_at: str
    resolved_at: Optional[str] = None


__all__ = [
    "AgentHealthResponseSchema",
    "AgentQueryRequestSchema",
    "AgentQueryResponseSchema",
    "AgentTraceResponseSchema",
    "AuthenticatedSessionContextSchema",
    "ChatMessageSchema",
    "ChatThreadHistoryResponseSchema",
    "ClientAuthenticateFrameSchema",
    "ClientInterruptFrameSchema",
    "ClientPingFrameSchema",
    "ClientRehydrateFrameSchema",
    "ClientUserMessageFrameSchema",
    "ConsolidatedCarrierProfileResponseSchema",
    "GuardrailInterventionSchema",
    "GuardrailResetResponseSchema",
    "GuardrailSummaryResponseSchema",
    "HITLApprovalResponseSchema",
    "HITLReviewDecisionRequestSchema",
    "KnowledgeSourceCitationSchema",
    "MemoryAuditLogEntrySchema",
    "MemoryProposalFeedbackRequestSchema",
    "MemoryProposalFeedbackResponseSchema",
    "MemoryProposalResponseSchema",
    "MemoryProposalSchema",
    "SanitizedErrorResponse",
    "ServerErrorEventSchema",
    "ServerGenerationCompletedEventSchema",
    "ServerGenerationInterruptedEventSchema",
    "ServerGenerationStartedEventSchema",
    "ServerPongEventSchema",
    "ServerSessionRehydratedEventSchema",
    "ServerTokenChunkEventSchema",
    "ToolCallTraceSchema",
]
