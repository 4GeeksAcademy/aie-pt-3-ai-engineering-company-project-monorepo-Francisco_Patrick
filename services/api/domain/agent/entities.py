"""Domain entities, state contracts, and value objects for the TrackFlow Support Agent.

Defines the minimal, explicit `AgentState` TypedDict passed between LangGraph nodes,
strictly read-only operational tool input/output contracts (`TicketToolInput`,
`TicketRecordDTO`, `TicketToolOutput`, `InventoryToolInput`, `InventoryRecordDTO`,
`InventoryToolOutput`), and immutable audit models (`AgentTrace`, `AgentCheckpoint`).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict

from domain.knowledge.entities import (
    KnowledgeChunk,
    RetrievedContext,
    SourceCitation,
)

ToolCallStatus = Literal["success", "not_found", "timeout", "error"]
MemoryCategory = Literal["carrier_rule", "incident_context", "b2b_preference"]
ProposalStatus = Literal["pending", "approved", "rejected", "edited", "discarded"]
IntentOutcome = Literal["approve", "reject", "edit", "unrelated_or_ambiguous"]
AuditEventType = Literal[
    "proposed", "approved", "rejected", "edited", "discarded", "evicted"
]
GuardrailLayer = Literal[
    "input_guard",
    "authorization_guard",
    "context_sanitizer",
    "output_guard",
]
GuardrailAction = Literal["allow", "redirect", "block", "deflect", "clarify"]
GuardrailFailureCategory = Literal["none", "structural", "content", "security"]
GuardrailFailureType = Literal["structural", "content", "security"]
GuardrailDisposition = Literal["blocked", "redirected", "deflected", "clarified"]
GuardrailInputCategory = Literal[
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
]
CustomerSegment = Literal["B2B", "B2C"]
OperatingCountry = Literal["US", "ES"]
ChatTurnRole = Literal["user", "assistant"]
ChatTurnStatus = Literal["streaming", "completed", "interrupted", "error"]
ChatInterruptedReason = Literal[
    "client_interrupt",
    "redirect_new_message",
    "client_disconnect",
]
AgentChatEventName = Literal[
    "session_rehydrated",
    "generation_started",
    "token_chunk",
    "generation_interrupted",
    "generation_completed",
    "error",
    "pong",
]


def _parse_iso_datetime(val: Any) -> datetime:
    """Parse an ISO-8601 datetime string or return existing datetime in UTC."""
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val
    if isinstance(val, str) and val.strip():
        cleaned = val.strip()
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class MemoryProposal:
    """In-flight, unconfirmed memory candidate produced during single-turn evaluation (FR-008, FR-010)."""

    proposal_id: str
    category: MemoryCategory
    target_entity: str
    summary: str
    status: ProposalStatus = "pending"
    country_code: Optional[str] = None
    source_message: str = ""
    confidence: float = 0.90
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    thread_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize proposal to a JSON-compatible dictionary."""
        return {
            "proposal_id": self.proposal_id,
            "category": self.category,
            "target_entity": self.target_entity,
            "country_code": self.country_code,
            "summary": self.summary,
            "status": self.status,
            "source_message": self.source_message,
            "confidence": round(float(self.confidence), 4),
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "thread_id": self.thread_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryProposal":
        """Reconstruct a MemoryProposal from a dictionary."""
        expires_raw = data.get("expires_at")
        return cls(
            proposal_id=str(data["proposal_id"]),
            category=data["category"],
            target_entity=str(data["target_entity"]),
            summary=str(data["summary"]),
            status=data.get("status", "pending"),
            country_code=data.get("country_code"),
            source_message=str(data.get("source_message") or ""),
            confidence=float(data.get("confidence", 0.90)),
            created_at=_parse_iso_datetime(data.get("created_at")),
            expires_at=_parse_iso_datetime(expires_raw) if expires_raw else None,
            thread_id=data.get("thread_id"),
        )


@dataclass(frozen=True)
class PersistentMemoryRecord:
    """Approved, committed operational memory stored in dedicated persistent storage (FR-006, FR-007)."""

    memory_id: str
    category: MemoryCategory
    target_entity: str
    content: str
    country_code: Optional[str] = None
    source_proposal_id: Optional[str] = None
    operator_confirmed_by: Optional[str] = None
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize persistent memory record to a JSON-compatible dictionary."""
        return {
            "memory_id": self.memory_id,
            "category": self.category,
            "target_entity": self.target_entity,
            "country_code": self.country_code,
            "content": self.content,
            "source_proposal_id": self.source_proposal_id,
            "operator_confirmed_by": self.operator_confirmed_by,
            "is_active": bool(self.is_active),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersistentMemoryRecord":
        """Reconstruct a PersistentMemoryRecord from a persisted dictionary."""
        expires_raw = data.get("expires_at")
        return cls(
            memory_id=str(data["memory_id"]),
            category=data["category"],
            target_entity=str(data["target_entity"]),
            content=str(data["content"]),
            country_code=data.get("country_code"),
            source_proposal_id=data.get("source_proposal_id"),
            operator_confirmed_by=data.get("operator_confirmed_by"),
            is_active=bool(data.get("is_active", True)),
            created_at=_parse_iso_datetime(data.get("created_at")),
            updated_at=_parse_iso_datetime(data.get("updated_at")),
            expires_at=_parse_iso_datetime(expires_raw) if expires_raw else None,
        )


@dataclass(frozen=True)
class ConsolidatedCarrierProfile:
    """Aggregated operational profile for a carrier in a specific country (FR-016)."""

    carrier: str
    country_code: str
    active_rules: List[str] = field(default_factory=list)
    memory_ids: List[str] = field(default_factory=list)
    last_verified_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize consolidated carrier profile to a dictionary."""
        return {
            "carrier": self.carrier,
            "country_code": self.country_code,
            "active_rules": list(self.active_rules),
            "memory_ids": list(self.memory_ids),
            "last_verified_at": self.last_verified_at.isoformat(),
        }


@dataclass(frozen=True)
class MemoryAuditLogEntry:
    """Immutable, append-only audit trail record for memory lifecycle transitions (FR-014)."""

    log_id: str
    event_type: str
    user_message: str
    resulting_action: str
    proposal_id: Optional[str] = None
    memory_id: Optional[str] = None
    classified_intent: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize audit log entry to a JSON-compatible dictionary."""
        return {
            "log_id": self.log_id,
            "proposal_id": self.proposal_id,
            "memory_id": self.memory_id,
            "event_type": self.event_type,
            "classified_intent": self.classified_intent,
            "user_message": self.user_message,
            "resulting_action": self.resulting_action,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "details": dict(self.details or {}),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryAuditLogEntry":
        """Reconstruct a MemoryAuditLogEntry from a persisted dictionary."""
        return cls(
            log_id=str(data["log_id"]),
            proposal_id=data.get("proposal_id"),
            memory_id=data.get("memory_id"),
            event_type=str(data["event_type"]),
            classified_intent=data.get("classified_intent"),
            user_message=str(data.get("user_message") or ""),
            resulting_action=str(data["resulting_action"]),
            session_id=data.get("session_id"),
            timestamp=_parse_iso_datetime(data.get("timestamp")),
            details=dict(data.get("details") or {}),
        )


@dataclass(frozen=True)
class UserIntentClassification:
    """Classification outcome for a user conversational turn following a memory proposal (FR-011)."""

    intent: IntentOutcome
    confidence: float
    refined_rule: Optional[str] = None
    residual_query: Optional[str] = None


@dataclass(frozen=True)
class MemoryGuardrailVerdict:
    """Validation result evaluating a candidate memory against enterprise anti-poisoning rules (FR-005, FR-017)."""

    allowed: bool
    violation_code: Optional[str] = None
    reason: Optional[str] = None


@dataclass(frozen=True)
class TicketToolInput:
    """Typed read-only request contract for querying live support incidents (FR-016)."""

    ticket_id: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    origin: Optional[str] = None
    branch: Optional[str] = None
    limit: int = 20

    def __post_init__(self) -> None:
        """Clamp limit between 1 and 20."""
        clamped_limit = max(1, min(20, int(self.limit if self.limit is not None else 20)))
        object.__setattr__(self, "limit", clamped_limit)

    def to_dict(self) -> Dict[str, Any]:
        """Return non-null filter criteria as a dictionary."""
        result: Dict[str, Any] = {"limit": self.limit}
        for key in ("ticket_id", "status", "category", "origin", "branch"):
            val = getattr(self, key)
            if val is not None:
                result[key] = val
        return result


@dataclass(frozen=True)
class TicketRecordDTO:
    """Immutable read-only projection of a live Incident Manager record (FR-016)."""

    id: str
    title: str
    description: str
    status: str
    category: str
    origin: str
    branch: str
    created_at: str
    updated_at: str

    def to_dict(self) -> Dict[str, Any]:
        """Serialize ticket record to a dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "category": self.category,
            "origin": self.origin,
            "branch": self.branch,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class TicketToolOutput:
    """Typed response contract returned by the Support Ticket Query Tool (FR-016)."""

    status: ToolCallStatus
    records: List[TicketRecordDTO] = field(default_factory=list)
    total_matched: int = 0
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    queried_criteria: Dict[str, Any] = field(default_factory=dict)

    def to_trace_summary(self) -> Dict[str, Any]:
        """Return compact audit metadata for AgentTrace.tool_calls."""
        return {
            "tool_name": "ticket_tool",
            "status": self.status,
            "total_matched": self.total_matched,
            "returned_count": len(self.records),
            "latency_ms": round(self.latency_ms, 3),
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class InventoryToolInput:
    """Typed read-only request contract for querying live warehouse inventory (FR-018)."""

    product_id: Optional[int] = None
    sku: Optional[str] = None
    search_query: Optional[str] = None
    low_stock_only: bool = False
    limit: int = 20

    def __post_init__(self) -> None:
        """Clamp limit between 1 and 20."""
        clamped_limit = max(1, min(20, int(self.limit if self.limit is not None else 20)))
        object.__setattr__(self, "limit", clamped_limit)

    def to_dict(self) -> Dict[str, Any]:
        """Return non-null filter criteria as a dictionary."""
        result: Dict[str, Any] = {
            "low_stock_only": bool(self.low_stock_only),
            "limit": self.limit,
        }
        for key in ("product_id", "sku", "search_query"):
            val = getattr(self, key)
            if val is not None:
                result[key] = val
        return result


@dataclass(frozen=True)
class InventoryRecordDTO:
    """Immutable read-only projection of a live Inventory Manager product record (FR-018)."""

    id: int
    sku: str
    name: str
    description: str
    stock: int
    min_threshold: int
    is_low_stock: bool
    warehouse_id: str = "central"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize inventory record to a dictionary."""
        return {
            "id": self.id,
            "sku": self.sku,
            "name": self.name,
            "description": self.description,
            "stock": self.stock,
            "min_threshold": self.min_threshold,
            "is_low_stock": self.is_low_stock,
            "warehouse_id": self.warehouse_id,
        }


@dataclass(frozen=True)
class InventoryToolOutput:
    """Typed response contract returned by the Inventory Stock Query Tool (FR-018)."""

    status: ToolCallStatus
    records: List[InventoryRecordDTO] = field(default_factory=list)
    total_matched: int = 0
    latency_ms: float = 0.0
    error_message: Optional[str] = None
    queried_criteria: Dict[str, Any] = field(default_factory=dict)

    def to_trace_summary(self) -> Dict[str, Any]:
        """Return compact audit metadata for AgentTrace.tool_calls."""
        return {
            "tool_name": "inventory_tool",
            "status": self.status,
            "total_matched": self.total_matched,
            "returned_count": len(self.records),
            "latency_ms": round(self.latency_ms, 3),
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class AuthenticatedSessionContext:
    """Represents the caller's verified identity, operational jurisdiction, and authorized order scope (FR-007, FR-008)."""

    session_id: str
    customer_id: str
    customer_segment: CustomerSegment = "B2C"
    primary_operating_country: OperatingCountry = "US"
    authorized_order_ids: Tuple[str, ...] = ()
    order_country_map: Dict[str, OperatingCountry] = field(default_factory=dict)
    brand_id: Optional[str] = None

    @staticmethod
    def normalize_order_id(raw_order_id: str) -> str:
        """Normalize an order or tracking ID (strip whitespace, leading '#', and uppercase)."""
        cleaned = (raw_order_id or "").strip().lstrip("#").strip().upper()
        return cleaned

    def is_order_authorized(self, order_id: str) -> bool:
        """Return True if the given order/tracking identifier belongs to this authenticated session."""
        target = self.normalize_order_id(order_id)
        if not target:
            return False
        normalized_authorized = {
            self.normalize_order_id(item) for item in self.authorized_order_ids if item
        }
        if target in normalized_authorized:
            return True
        # Also allow matching bare numeric ID against 'ORD-<digits>' or 'TRK-<digits>' if normalized
        for auth_id in normalized_authorized:
            if auth_id.endswith(f"-{target}") or target.endswith(f"-{auth_id}"):
                return True
        return False

    def resolve_order_country(
        self,
        order_id: Optional[str] = None,
        explicit_location_country: Optional[OperatingCountry] = None,
    ) -> OperatingCountry:
        """Resolve authoritative country ('US' or 'ES') for an inquiry (FR-008).

        Precedence:
        1. Referenced order's entry in `order_country_map`.
        2. Explicit fulfillment location in the request (`explicit_location_country`).
        3. Fallback to `primary_operating_country`.
        """
        if order_id:
            target = self.normalize_order_id(order_id)
            for key, country in (self.order_country_map or {}).items():
                norm_key = self.normalize_order_id(key)
                if norm_key == target or norm_key.endswith(f"-{target}") or target.endswith(f"-{norm_key}"):
                    if country in ("US", "ES"):
                        return country
        if explicit_location_country in ("US", "ES"):
            return explicit_location_country
        if self.primary_operating_country in ("US", "ES"):
            return self.primary_operating_country
        return "US"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session context to a JSON-compatible dictionary."""
        return {
            "session_id": self.session_id,
            "customer_id": self.customer_id,
            "customer_segment": self.customer_segment,
            "primary_operating_country": self.primary_operating_country,
            "authorized_order_ids": list(self.authorized_order_ids),
            "order_country_map": dict(self.order_country_map),
        }


@dataclass(frozen=True)
class GuardrailEvaluationResult:
    """Deterministic decision produced by an input, authorization, context-sanitization, or output guardrail layer (FR-003)."""

    layer: GuardrailLayer
    action: GuardrailAction
    failure_category: GuardrailFailureCategory
    input_category: GuardrailInputCategory
    reason_code: str
    message: Optional[str] = None
    sanitized_text: Optional[str] = None
    resolved_country: Optional[OperatingCountry] = None
    decision: Optional[GuardrailAction] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.decision is None:
            object.__setattr__(self, "decision", self.action)
        elif self.action is None:
            object.__setattr__(self, "action", self.decision)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize evaluation result to a dictionary."""
        return {
            "layer": self.layer,
            "action": self.action,
            "decision": self.decision or self.action,
            "failure_category": self.failure_category,
            "input_category": self.input_category,
            "reason_code": self.reason_code,
            "message": self.message,
            "sanitized_text": self.sanitized_text,
            "resolved_country": self.resolved_country,
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True)
class GuardrailAuditEvent:
    """Immutable structured observability record logged whenever a guardrail blocks or redirects (FR-011)."""

    event_id: str
    timestamp: datetime
    session_id: str
    failure_type: GuardrailFailureType
    layer: GuardrailLayer
    input_category: GuardrailInputCategory
    reason_code: str
    disposition: GuardrailDisposition
    redacted_preview: str
    trace_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize audit event to a JSON-compatible dictionary."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "failure_type": self.failure_type,
            "layer": self.layer,
            "input_category": self.input_category,
            "reason_code": self.reason_code,
            "disposition": self.disposition,
            "redacted_preview": self.redacted_preview,
            "metadata": dict(self.metadata or {}),
        }


@dataclass(frozen=True)
class GuardrailSummaryReport:
    """Aggregated observability metric view returned by REST and CLI summary interfaces (FR-012)."""

    total_evaluations: int
    total_interventions: int
    by_failure_type: Dict[str, int]
    by_layer: Dict[str, int]
    by_input_category: Dict[str, int]
    by_disposition: Dict[str, int]
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    recent_events: List[GuardrailAuditEvent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize summary report to a JSON-compatible dictionary."""
        return {
            "total_evaluations": self.total_evaluations,
            "total_interventions": self.total_interventions,
            "by_failure_type": dict(self.by_failure_type),
            "by_layer": dict(self.by_layer),
            "by_input_category": dict(self.by_input_category),
            "by_disposition": dict(self.by_disposition),
            "window_start": self.window_start.isoformat() if self.window_start else None,
            "window_end": self.window_end.isoformat() if self.window_end else None,
            "recent_events": [ev.to_dict() for ev in self.recent_events],
        }


class AgentState(TypedDict, total=False):
    """Minimal state dictionary transferred between LangGraph nodes during a single run.

    Excludes full historical conversational chat logs to preserve token efficiency
    and enforce strict, inspectable state boundaries (FR-001).
    """

    query: str
    language: str
    top_k: int
    min_score: float
    selected_sources: List[str]
    sources_consulted: List[str]
    ticket_tool_input: Optional[TicketToolInput]
    ticket_tool_output: Optional[TicketToolOutput]
    inventory_tool_input: Optional[InventoryToolInput]
    inventory_tool_output: Optional[InventoryToolOutput]
    contexts: List[RetrievedContext]
    fallback_triggered: bool
    fallback_messages: List[str]
    answer: str
    is_refusal: bool
    sources: List[SourceCitation]
    trace_id: str
    thread_id: Optional[str]
    node_history: List[str]
    step_latencies: Dict[str, float]
    node_outputs: Dict[str, Dict[str, Any]]
    error: Optional[str]
    pending_proposal: Optional[MemoryProposal]
    memory_proposal: Optional[MemoryProposal]
    recalled_memories: List[str]
    proposal_resolution: Optional[Dict[str, Any]]
    session_context: Optional[AuthenticatedSessionContext]
    resolved_country: Optional[OperatingCountry]
    guardrail_action: Optional[GuardrailAction]
    guardrail_failure_category: Optional[GuardrailFailureCategory]
    guardrail_reason_code: Optional[str]
    guardrail_message: Optional[str]
    casual_redirect_required: bool
    guardrail_events: List[GuardrailAuditEvent]


@dataclass(frozen=True)
class AgentQueryRequest:
    """Domain request object submitted to the SupportAgentService."""

    query: str
    top_k: int = 3
    min_score: float = 0.62
    thread_id: Optional[str] = None
    language: str = "en"
    session_context: Optional[AuthenticatedSessionContext] = None


@dataclass(frozen=True)
class AgentQueryResult:
    """Domain result returned after executing the compiled Support Agent workflow."""

    query: str
    answer: str
    is_refusal: bool
    sources: List[SourceCitation] = field(default_factory=list)
    trace_id: str = ""
    node_sequence: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0
    fallback_triggered: bool = False
    sources_consulted: List[str] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    memory_proposal: Optional[MemoryProposal] = None
    recalled_memories: List[str] = field(default_factory=list)
    guardrail_interventions: List[GuardrailAuditEvent] = field(default_factory=list)
    resolved_country: Optional[OperatingCountry] = None


@dataclass(frozen=True)
class AgentCheckpoint:
    """Point-in-time snapshot of AgentState captured at node boundaries."""

    thread_id: str
    checkpoint_id: str
    parent_checkpoint_id: Optional[str]
    node: str
    state_delta: Dict[str, Any]
    timestamp: str


@dataclass(frozen=True)
class AgentTrace:
    """Structured audit model representing the post-execution trace of an agent run."""

    trace_id: str
    query: str
    node_sequence: List[str]
    step_latencies: Dict[str, float]
    total_duration_ms: float
    is_refusal: bool
    final_answer: str
    source_count: int
    sources_consulted: List[str] = field(default_factory=list)
    fallback_triggered: bool = False
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    node_outputs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    checkpoints: List[AgentCheckpoint] = field(default_factory=list)


@dataclass(frozen=True)
class ChatMessage:
    """Represents a single user or assistant turn within a ChatThreadState timeline (FR-006..FR-010, FR-012)."""

    turn_id: str
    thread_id: str
    session_id: str
    role: ChatTurnRole
    content: str
    status: ChatTurnStatus = "completed"
    parent_user_turn_id: Optional[str] = None
    interrupted_reason: Optional[ChatInterruptedReason] = None
    is_refusal: bool = False
    fallback_triggered: bool = False
    trace_id: Optional[str] = None
    node_sequence: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0
    sources: List[SourceCitation] = field(default_factory=list)
    sources_consulted: List[str] = field(default_factory=list)
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    memory_proposal: Optional[MemoryProposal] = None
    recalled_memories: List[str] = field(default_factory=list)
    guardrail_interventions: List[GuardrailAuditEvent] = field(default_factory=list)
    resolved_country: Optional[OperatingCountry] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize ChatMessage to a JSON-compatible dictionary."""
        return {
            "turn_id": self.turn_id,
            "thread_id": self.thread_id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "status": self.status,
            "parent_user_turn_id": self.parent_user_turn_id,
            "interrupted_reason": self.interrupted_reason,
            "is_refusal": bool(self.is_refusal),
            "fallback_triggered": bool(self.fallback_triggered),
            "trace_id": self.trace_id,
            "node_sequence": list(self.node_sequence),
            "execution_time_ms": round(float(self.execution_time_ms), 3),
            "sources": [
                {
                    "source_document": s.source_document,
                    "section": s.section,
                    "similarity_score": round(float(s.similarity_score), 4),
                }
                for s in self.sources
            ],
            "sources_consulted": list(self.sources_consulted),
            "tool_calls": [dict(tc) for tc in self.tool_calls],
            "memory_proposal": (
                self.memory_proposal.to_dict()
                if self.memory_proposal is not None
                else None
            ),
            "recalled_memories": list(self.recalled_memories),
            "guardrail_interventions": [
                ev.to_dict() if hasattr(ev, "to_dict") else dict(ev)
                for ev in self.guardrail_interventions
            ],
            "resolved_country": self.resolved_country,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatMessage":
        """Reconstruct a ChatMessage from a persisted dictionary."""
        raw_sources = data.get("sources") or []
        sources: List[SourceCitation] = []
        for s in raw_sources:
            if isinstance(s, SourceCitation):
                sources.append(s)
            elif isinstance(s, dict):
                sources.append(
                    SourceCitation(
                        source_document=str(s.get("source_document") or ""),
                        section=str(s.get("section") or ""),
                        similarity_score=float(s.get("similarity_score", 0.0)),
                    )
                )

        raw_proposal = data.get("memory_proposal")
        memory_proposal: Optional[MemoryProposal] = None
        if isinstance(raw_proposal, MemoryProposal):
            memory_proposal = raw_proposal
        elif isinstance(raw_proposal, dict) and raw_proposal.get("proposal_id"):
            memory_proposal = MemoryProposal.from_dict(raw_proposal)

        raw_interventions = data.get("guardrail_interventions") or []
        interventions: List[GuardrailAuditEvent] = []
        for ev in raw_interventions:
            if isinstance(ev, GuardrailAuditEvent):
                interventions.append(ev)
            elif isinstance(ev, dict) and ev.get("event_id"):
                interventions.append(
                    GuardrailAuditEvent(
                        event_id=str(ev["event_id"]),
                        timestamp=_parse_iso_datetime(ev.get("timestamp")),
                        session_id=str(ev.get("session_id") or ""),
                        failure_type=ev.get("failure_type", "content"),
                        layer=ev.get("layer", "input_guard"),
                        input_category=ev.get("input_category", "out_of_domain"),
                        reason_code=str(ev.get("reason_code") or ""),
                        disposition=ev.get("disposition", "blocked"),
                        redacted_preview=str(ev.get("redacted_preview") or ""),
                        trace_id=ev.get("trace_id"),
                        metadata=dict(ev.get("metadata") or {}),
                    )
                )

        resolved_country_raw = data.get("resolved_country")
        resolved_country: Optional[OperatingCountry] = (
            resolved_country_raw if resolved_country_raw in ("US", "ES") else None
        )
        interrupted_reason_raw = data.get("interrupted_reason")
        interrupted_reason: Optional[ChatInterruptedReason] = (
            interrupted_reason_raw
            if interrupted_reason_raw
            in ("client_interrupt", "redirect_new_message", "client_disconnect")
            else None
        )

        return cls(
            turn_id=str(data["turn_id"]),
            thread_id=str(data["thread_id"]),
            session_id=str(data.get("session_id") or data["thread_id"]),
            role=data.get("role", "assistant"),
            content=str(data.get("content") or ""),
            status=data.get("status", "completed"),
            parent_user_turn_id=data.get("parent_user_turn_id"),
            interrupted_reason=interrupted_reason,
            is_refusal=bool(data.get("is_refusal", False)),
            fallback_triggered=bool(data.get("fallback_triggered", False)),
            trace_id=data.get("trace_id"),
            node_sequence=[str(n) for n in (data.get("node_sequence") or [])],
            execution_time_ms=float(data.get("execution_time_ms", 0.0)),
            sources=sources,
            sources_consulted=[str(sc) for sc in (data.get("sources_consulted") or [])],
            tool_calls=[
                dict(tc) for tc in (data.get("tool_calls") or []) if isinstance(tc, dict)
            ],
            memory_proposal=memory_proposal,
            recalled_memories=[str(m) for m in (data.get("recalled_memories") or [])],
            guardrail_interventions=interventions,
            resolved_country=resolved_country,
            created_at=_parse_iso_datetime(data.get("created_at")),
            updated_at=_parse_iso_datetime(data.get("updated_at")),
        )


@dataclass(frozen=True)
class ChatThreadState:
    """Represents a persistent, multi-turn TrackFlow support agent conversation bound to an authenticated operator (FR-003, FR-012)."""

    thread_id: str
    session_id: str
    owner_user_id: str
    owner_email: Optional[str] = None
    messages: List[ChatMessage] = field(default_factory=list)
    pending_proposal: Optional[MemoryProposal] = None
    session_context: Optional[AuthenticatedSessionContext] = None
    latest_checkpoint_id: Optional[str] = None
    latest_sequence_id: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Serialize ChatThreadState to a JSON-compatible dictionary."""
        return {
            "thread_id": self.thread_id,
            "session_id": self.session_id,
            "owner_user_id": self.owner_user_id,
            "owner_email": self.owner_email,
            "messages": [m.to_dict() for m in self.messages],
            "pending_proposal": (
                self.pending_proposal.to_dict()
                if self.pending_proposal is not None
                else None
            ),
            "session_context": (
                self.session_context.to_dict()
                if self.session_context is not None
                else None
            ),
            "latest_checkpoint_id": self.latest_checkpoint_id,
            "latest_sequence_id": int(self.latest_sequence_id),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatThreadState":
        """Reconstruct a ChatThreadState from a persisted dictionary."""
        raw_messages = data.get("messages") or []
        messages = [
            m if isinstance(m, ChatMessage) else ChatMessage.from_dict(dict(m))
            for m in raw_messages
            if isinstance(m, (ChatMessage, dict))
        ]
        raw_pending = data.get("pending_proposal")
        pending_proposal: Optional[MemoryProposal] = None
        if isinstance(raw_pending, MemoryProposal):
            pending_proposal = raw_pending
        elif isinstance(raw_pending, dict) and raw_pending.get("proposal_id"):
            pending_proposal = MemoryProposal.from_dict(raw_pending)

        raw_session_ctx = data.get("session_context")
        session_context: Optional[AuthenticatedSessionContext] = None
        if isinstance(raw_session_ctx, AuthenticatedSessionContext):
            session_context = raw_session_ctx
        elif isinstance(raw_session_ctx, dict) and raw_session_ctx.get("session_id"):
            session_context = AuthenticatedSessionContext(
                session_id=str(raw_session_ctx["session_id"]),
                customer_id=str(raw_session_ctx.get("customer_id") or "default"),
                customer_segment=raw_session_ctx.get("customer_segment", "B2C"),
                primary_operating_country=raw_session_ctx.get(
                    "primary_operating_country", "US"
                ),
                authorized_order_ids=tuple(
                    str(x) for x in (raw_session_ctx.get("authorized_order_ids") or [])
                ),
                order_country_map=dict(raw_session_ctx.get("order_country_map") or {}),
            )

        thread_id = str(data["thread_id"])
        return cls(
            thread_id=thread_id,
            session_id=str(data.get("session_id") or thread_id),
            owner_user_id=str(data["owner_user_id"]),
            owner_email=data.get("owner_email"),
            messages=messages,
            pending_proposal=pending_proposal,
            session_context=session_context,
            latest_checkpoint_id=data.get("latest_checkpoint_id"),
            latest_sequence_id=int(data.get("latest_sequence_id", 0)),
            created_at=_parse_iso_datetime(data.get("created_at")),
            updated_at=_parse_iso_datetime(data.get("updated_at")),
        )


@dataclass(frozen=True)
class AgentChatStreamEvent:
    """Structured pub/sub & WebSocket event envelope emitted on a conversation thread channel (FR-004, FR-005)."""

    event: AgentChatEventName
    thread_id: str
    session_id: str
    sequence_id: int
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_frame_dict(self) -> Dict[str, Any]:
        """Serialize event into a flat discriminated WebSocket frame dictionary."""
        ts_iso = (
            self.timestamp.isoformat().replace("+00:00", "Z")
            if self.timestamp.tzinfo is not None
            else f"{self.timestamp.isoformat()}Z"
        )
        base: Dict[str, Any] = {
            "event": self.event,
            "thread_id": self.thread_id,
            "session_id": self.session_id,
        }
        for key, val in self.payload.items():
            if key not in ("event", "thread_id", "session_id", "sequence_id", "timestamp"):
                base[key] = val
        base["sequence_id"] = int(self.sequence_id)
        base["timestamp"] = ts_iso
        return base


# ---------------------------------------------------------------------------
# OWASP Top 10 Security Audit, Governance & Action Policy Entities (FR-001..FR-007)
# ---------------------------------------------------------------------------

ComponentCategory = Literal["BACKEND", "FRONTEND", "AGENTIC", "HOST"]
OWASPCategory = Literal[
    "A01_BROKEN_ACCESS_CONTROL",
    "A02_CRYPTOGRAPHIC_FAILURES",
    "A03_INJECTION",
    "A04_INSECURE_DESIGN",
    "A05_SECURITY_MISCONFIGURATION",
    "A06_VULNERABLE_COMPONENTS",
    "A07_AUTH_FAILURES",
    "A08_INTEGRITY_FAILURES",
    "A09_LOGGING_MONITORING_FAILURES",
    "A10_SSRF",
]
SeverityLevel = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"]
ApplicabilityVerdict = Literal["APPLIES", "DOES_NOT_APPLY"]
VerificationStatus = Literal["OPEN", "IN_PROGRESS", "VERIFIED_RESOLVED", "MITIGATED"]
DataClassification = Literal[
    "RESTRICTED_PII",
    "CONFIDENTIAL_B2B",
    "INTERNAL_OPERATIONAL",
    "PUBLIC",
    "PUBLIC_TRANSIT",
]
RegulatoryFramework = Literal["GDPR_EU", "CCPA_CPRA_US"]

AgentActionType = Literal[
    "RETURN_APPROVAL",
    "HIGH_VALUE_DISPATCH",
    "CARRIER_REASSIGNMENT",
    "ORDER_LOOKUP",
    "BRAND_METRIC_QUERY",
    "CROSS_BRAND_METRIC_SHARE",
]
ApprovalStatus = Literal[
    "AUTONOMOUSLY_APPROVED",
    "PENDING_HUMAN_APPROVAL",
    "HUMAN_APPROVED",
    "HUMAN_REJECTED",
    "EXPIRED_FAIL_SECURE",
    "BLOCKED_SECURITY_VIOLATION",
    "REFUSED_OUT_OF_SCOPE",
]

AISystemArchitecture = Literal[
    "AUTONOMOUS_AGENT",
    "DECISION_ENGINE",
    "RAG_PIPELINE",
    "MCP_SERVER_TOOL",
]

VendorCategory = Literal[
    "FOUNDATION_MODEL_API",
    "VECTOR_DATABASE_CLOUD",
    "COURIER_CARRIER_INTEGRATION",
]

DataRetentionPolicy = Literal[
    "ZERO_RETENTION_EPHEMERAL",
    "PERSISTENT_ENCRYPTED_30_DAYS",
    "TENANT_ISOLATED_INDEX",
]

NISTFunctionCategory = Literal[
    "GOVERN",
    "IDENTIFY",
    "PROTECT",
    "DETECT",
    "RESPOND",
    "RECOVER",
]

RiskSeverity = Literal["CRITICAL", "HIGH", "MEDIUM", "LOW"]
RiskStatus = Literal["ACCEPTED_TEMPORARY", "REMEDIATION_SCHEDULED", "REMEDIATED"]


@dataclass(frozen=True)
class SecurityFinding:
    """Audited vulnerability or hardening item evaluated against OWASP Top 10."""

    id: str
    component: ComponentCategory
    category: OWASPCategory
    title: str
    location: str
    severity: SeverityLevel
    applicability: ApplicabilityVerdict
    description: str = ""
    gdpr_implications: bool = False
    ccpa_implications: bool = False
    remediation_plan: str = ""
    verification_status: VerificationStatus = "OPEN"
    verification_proof: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert finding to dictionary representation."""
        return {
            "id": self.id,
            "component": self.component,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "location": self.location,
            "severity": self.severity,
            "applicability": self.applicability,
            "gdpr_implications": self.gdpr_implications,
            "ccpa_implications": self.ccpa_implications,
            "remediation_plan": self.remediation_plan,
            "verification_status": self.verification_status,
            "verification_proof": self.verification_proof,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SecurityFinding":
        """Reconstruct SecurityFinding from dictionary."""
        return cls(
            id=str(data["id"]),
            component=data["component"],
            category=data["category"],
            title=str(data["title"]),
            description=str(data.get("description", "")),
            location=str(data["location"]),
            severity=data["severity"],
            applicability=data["applicability"],
            gdpr_implications=bool(data.get("gdpr_implications", False)),
            ccpa_implications=bool(data.get("ccpa_implications", False)),
            remediation_plan=str(data.get("remediation_plan", "")),
            verification_status=data.get("verification_status", "OPEN"),
            verification_proof=str(data.get("verification_proof", "")),
        )


@dataclass(frozen=True)
class AuditScopeRecord:
    """Subsystem under security audit scope."""

    service_id: str
    service_name: str
    repository_path: str
    data_classification: DataClassification
    engineering_owner: str
    regulatory_scope: List[RegulatoryFramework] = field(default_factory=lambda: ["GDPR_EU"])
    runtime_environment: str = "production"

    def to_dict(self) -> Dict[str, Any]:
        """Convert scope record to dictionary representation."""
        return {
            "service_id": self.service_id,
            "service_name": self.service_name,
            "repository_path": self.repository_path,
            "data_classification": self.data_classification,
            "engineering_owner": self.engineering_owner,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuditScopeRecord":
        """Reconstruct AuditScopeRecord from dictionary."""
        return cls(
            service_id=str(data["service_id"]),
            service_name=str(data["service_name"]),
            repository_path=str(data["repository_path"]),
            data_classification=data["data_classification"],
            engineering_owner=str(data["engineering_owner"]),
        )


@dataclass(frozen=True)
class AgentActionPolicy:
    """Policy rules governing autonomous actions vs. human-in-the-loop authorization gates."""

    action_type: AgentActionType
    max_autonomous_amount_eur: float = 100.00
    allowed_autonomous_statuses: List[str] = field(default_factory=lambda: ["PENDING", "PROCESSING", "DELIVERED"])
    require_session_binding: bool = True
    enforce_human_approval_gate: bool = True


@dataclass(frozen=True)
class HumanApprovalGateRecord:
    """Immutable audit record for actions undergoing human-in-the-loop operational review."""

    request_id: str
    action_type: AgentActionType
    entity_id: str
    requested_by_session: str
    payload_snapshot: Dict[str, Any] = field(default_factory=dict)
    requested_amount_eur: float = 0.0
    status: ApprovalStatus = "PENDING_HUMAN_APPROVAL"
    reviewer_id: Optional[str] = None
    decision_notes: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert approval gate record to dictionary representation."""
        return {
            "request_id": self.request_id,
            "action_type": self.action_type,
            "entity_id": self.entity_id,
            "requested_by_session": self.requested_by_session,
            "payload_snapshot": self.payload_snapshot,
            "requested_amount_eur": self.requested_amount_eur,
            "status": self.status,
            "reviewer_id": self.reviewer_id,
            "decision_notes": self.decision_notes,
            "created_at": self.created_at.isoformat(),
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


@dataclass(frozen=True)
class SecurityAuditLogEntry:
    """Structured, tamper-evident audit record capturing agent decisions and guardrail outcomes."""

    event_id: str
    timestamp: datetime
    agent_id: str
    session_id: str
    tenant_id: str
    event_category: str
    action_attempted: str
    input_parameters_redacted: Dict[str, Any]
    policy_rules_evaluated: List[str]
    decision_outcome: str
    reasoning_rationale: str
    client_ip: Optional[str] = None


@dataclass(frozen=True)
class AISystemRecord:
    """Authoritative inventory record of an operational AI component."""

    system_id: str
    name: str
    description: str
    repository_path: str
    architecture_type: AISystemArchitecture
    custodian_team: str
    technical_lead: str
    data_classification: DataClassification
    input_attack_surfaces: List[str]
    requires_hitl_gates: bool
    rate_limiting_enabled: bool
    last_audited_at: datetime


@dataclass(frozen=True)
class SharedResponsibilityRecord:
    """Security boundary definition between TrackFlow and a third-party AI provider."""

    provider_id: str
    provider_name: str
    vendor_category: VendorCategory
    service_scope: str
    trackflow_responsibilities: List[str]
    vendor_responsibilities: List[str]
    zero_data_retention_active: bool
    transit_encryption_enforced: bool
    governing_dpa_reference: str


@dataclass(frozen=True)
class HITLApprovalRequest:
    """Irreversible action intercepted for operational human-in-the-loop review."""

    request_id: str
    action_type: str
    entity_id: str
    requested_by_session: str
    requested_by_agent: str
    payload_snapshot: Dict[str, Any]
    status: ApprovalStatus
    created_at: datetime
    expires_at: datetime
    monetary_impact_eur: Optional[float] = None
    reviewer_id: Optional[str] = None
    decision_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None


@dataclass(frozen=True)
class ResidualRiskRecord:
    """Documented security limitation with compensatory controls and remediation milestone."""

    risk_id: str
    nist_function: NISTFunctionCategory
    description: str
    severity: RiskSeverity
    business_impact: str
    compensatory_controls: List[str]
    target_remediation_milestone: str
    risk_owner: str
    status: RiskStatus


@dataclass(frozen=True)
class NISTControlAction:
    """Concrete operational security control mapped to a NIST CSF 2.0 category."""

    control_id: str
    category_code: str
    title: str
    concrete_operational_action: str
    verification_mechanism: str
    implementation_location: str
    priority: Literal["P1", "P2", "P3"]


__all__ = [
    "AISystemArchitecture",
    "AISystemRecord",
    "AgentActionPolicy",
    "AgentActionType",
    "AgentChatEventName",
    "AgentChatStreamEvent",
    "AgentCheckpoint",
    "AgentQueryRequest",
    "AgentQueryResult",
    "AgentState",
    "AgentTrace",
    "ApplicabilityVerdict",
    "ApprovalStatus",
    "AuditEventType",
    "AuditScopeRecord",
    "AuthenticatedSessionContext",
    "ChatInterruptedReason",
    "ChatMessage",
    "ChatThreadState",
    "ChatTurnRole",
    "ChatTurnStatus",
    "ComponentCategory",
    "ConsolidatedCarrierProfile",
    "CustomerSegment",
    "DataClassification",
    "DataRetentionPolicy",
    "GuardrailAction",
    "GuardrailAuditEvent",
    "GuardrailDisposition",
    "GuardrailEvaluationResult",
    "GuardrailFailureCategory",
    "GuardrailFailureType",
    "GuardrailInputCategory",
    "GuardrailLayer",
    "GuardrailSummaryReport",
    "HITLApprovalRequest",
    "HumanApprovalGateRecord",
    "IntentOutcome",
    "InventoryRecordDTO",
    "InventoryToolInput",
    "InventoryToolOutput",
    "KnowledgeChunk",
    "MemoryAuditLogEntry",
    "MemoryCategory",
    "MemoryGuardrailVerdict",
    "MemoryProposal",
    "NISTControlAction",
    "NISTFunctionCategory",
    "OperatingCountry",
    "OWASPCategory",
    "PersistentMemoryRecord",
    "ProposalStatus",
    "RegulatoryFramework",
    "ResidualRiskRecord",
    "RetrievedContext",
    "RiskSeverity",
    "RiskStatus",
    "SecurityAuditLogEntry",
    "SecurityFinding",
    "SeverityLevel",
    "SharedResponsibilityRecord",
    "SourceCitation",
    "TicketRecordDTO",
    "TicketToolInput",
    "TicketToolOutput",
    "ToolCallStatus",
    "UserIntentClassification",
    "VendorCategory",
    "VerificationStatus",
]
