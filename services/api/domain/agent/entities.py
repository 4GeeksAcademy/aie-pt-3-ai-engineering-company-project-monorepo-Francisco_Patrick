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
ChatSessionStatus = Literal["active", "interrupted", "closed"]
FIRST_LINE_AGENT_ID = "first_line_cx"
UNASSIGNED_CLIENT_USER_ID = "unassigned"
LEGACY_AGENT_IDS: Tuple[str, ...] = ("trackflow-support-agent",)
_LEGACY_SESSION_STATUS_MAP: Dict[str, ChatSessionStatus] = {
    "streaming": "active",
    "disconnected": "interrupted",
}


def normalize_chat_session_status(raw: object) -> ChatSessionStatus:
    """Coerce a raw (possibly legacy) status into the briefing enum `active|interrupted|closed`.

    Legacy `streaming` maps to `active`, legacy `disconnected` maps to `interrupted`;
    unknown or missing values fall back to `active`.
    """
    if raw == "active" or raw == "interrupted" or raw == "closed":
        return raw
    if isinstance(raw, str) and raw in _LEGACY_SESSION_STATUS_MAP:
        return _LEGACY_SESSION_STATUS_MAP[raw]
    return "active"


def normalize_agent_id(raw: object) -> str:
    """Return the briefing agent id, mapping empty/legacy values to `first_line_cx`."""
    value = str(raw or "").strip()
    if not value or value in LEGACY_AGENT_IDS:
        return FIRST_LINE_AGENT_ID
    return value


def resolve_client_user_id(
    session_context: Optional["AuthenticatedSessionContext"] = None,
) -> str:
    """Resolve the chatting client `user_id` from domain `session_context.customer_id`.

    Falls back to `UNASSIGNED_CLIENT_USER_ID` (`"unassigned"`) when no customer context
    is bound to the thread, never exposing the back-office operator ID.
    """
    if session_context is not None:
        customer_id = str(session_context.customer_id or "").strip()
        if customer_id:
            return customer_id
    return UNASSIGNED_CLIENT_USER_ID


def merge_thread_session_context(
    existing_context: Optional["AuthenticatedSessionContext"],
    incoming_context: Optional["AuthenticatedSessionContext"],
) -> Optional["AuthenticatedSessionContext"]:
    """Lock the thread's customer identity to the first valid `session_context.customer_id` seen.

    Once a non-empty `customer_id` is bound on the thread, subsequent turns without a context
    or with a conflicting `customer_id` retain the original customer identity.
    """
    if existing_context is not None and str(existing_context.customer_id or "").strip():
        if incoming_context is None:
            return existing_context
        existing_cid = str(existing_context.customer_id).strip()
        incoming_cid = str(incoming_context.customer_id or "").strip()
        if not incoming_cid or incoming_cid != existing_cid:
            return existing_context
        return incoming_context
    if incoming_context is not None and str(incoming_context.customer_id or "").strip():
        return incoming_context
    return existing_context or incoming_context
ChatInterruptedReason = Literal[
    "client_interrupt",
    "redirect_new_message",
    "client_disconnect",
]
AgentChatEventName = Literal[
    "session_snapshot",
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
class ChatSession:
    """Represents an active or persisted Support Agent chat session; `user_id` is the chatting client."""

    session_id: str
    thread_id: str
    user_id: str = UNASSIGNED_CLIENT_USER_ID
    agent_id: str = FIRST_LINE_AGENT_ID
    client_id: str = "trackflow-backoffice"
    status: ChatSessionStatus = "active"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def owner_user_id(self) -> str:
        """Backward-compatible alias for user_id."""
        return self.user_id

    def to_dict(self) -> Dict[str, Any]:
        """Serialize ChatSession to a JSON-compatible dictionary."""
        return {
            "session_id": self.session_id,
            "thread_id": self.thread_id,
            "agent_id": self.agent_id,
            "client_id": self.client_id,
            "user_id": self.user_id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatSession":
        """Reconstruct a ChatSession from a dictionary."""
        session_id = str(data.get("session_id") or data.get("thread_id") or "default")
        thread_id = str(data.get("thread_id") or session_id)
        user_id = str(data.get("user_id") or "").strip() or UNASSIGNED_CLIENT_USER_ID
        status_val = normalize_chat_session_status(data.get("status"))
        return cls(
            session_id=session_id,
            thread_id=thread_id,
            agent_id=normalize_agent_id(data.get("agent_id")),
            client_id=str(data.get("client_id") or "trackflow-backoffice"),
            user_id=user_id,
            status=status_val,
            created_at=_parse_iso_datetime(data.get("created_at")),
            updated_at=_parse_iso_datetime(data.get("updated_at")),
        )


@dataclass(frozen=True)
class ChatThreadState:
    """Represents a persistent, multi-turn TrackFlow support agent conversation bound to an authenticated operator (FR-003, FR-012)."""

    thread_id: str
    session_id: str
    user_id: str = UNASSIGNED_CLIENT_USER_ID
    owner_user_id: Optional[str] = None
    owner_email: Optional[str] = None
    agent_id: str = FIRST_LINE_AGENT_ID
    client_id: str = "trackflow-backoffice"
    status: ChatSessionStatus = "active"
    messages: List[ChatMessage] = field(default_factory=list)
    pending_proposal: Optional[MemoryProposal] = None
    session_context: Optional[AuthenticatedSessionContext] = None
    latest_checkpoint_id: Optional[str] = None
    latest_sequence_id: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        raw_owner = str(self.owner_user_id or "").strip()
        raw_user = str(self.user_id or "").strip()
        resolved_client = resolve_client_user_id(self.session_context)
        if (
            not raw_owner
            and raw_user
            and raw_user != UNASSIGNED_CLIENT_USER_ID
            and raw_user != resolved_client
        ):
            raw_owner = raw_user
        object.__setattr__(self, "owner_user_id", raw_owner or None)
        object.__setattr__(self, "user_id", resolved_client)

    @property
    def session(self) -> ChatSession:
        """Project the canonical ChatSession metadata for this thread."""
        derived_status: ChatSessionStatus = normalize_chat_session_status(self.status)
        if self.messages:
            last_msg = self.messages[-1]
            if (
                last_msg.role == "assistant"
                and last_msg.status == "interrupted"
                and derived_status == "active"
            ):
                derived_status = "interrupted"
        return ChatSession(
            session_id=self.session_id,
            thread_id=self.thread_id,
            agent_id=normalize_agent_id(self.agent_id),
            client_id=self.client_id,
            user_id=resolve_client_user_id(self.session_context),
            status=derived_status,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize ChatThreadState to a JSON-compatible dictionary."""
        session_obj = self.session
        return {
            "thread_id": self.thread_id,
            "session_id": self.session_id,
            "user_id": session_obj.user_id,
            "owner_user_id": self.owner_user_id,
            "owner_email": self.owner_email,
            "agent_id": self.agent_id,
            "client_id": self.client_id,
            "status": session_obj.status,
            "session": session_obj.to_dict(),
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
                customer_id=str(raw_session_ctx.get("customer_id") or "").strip(),
                customer_segment=raw_session_ctx.get("customer_segment", "B2C"),
                primary_operating_country=raw_session_ctx.get(
                    "primary_operating_country", "US"
                ),
                authorized_order_ids=tuple(
                    str(x) for x in (raw_session_ctx.get("authorized_order_ids") or [])
                ),
                order_country_map=dict(raw_session_ctx.get("order_country_map") or {}),
            )

        raw_session = data.get("session") if isinstance(data.get("session"), dict) else {}
        thread_id = str(data["thread_id"])
        resolved_client = resolve_client_user_id(session_context)
        raw_owner = str(data.get("owner_user_id") or "").strip()
        raw_user = str(
            data.get("user_id") or raw_session.get("user_id") or ""
        ).strip()
        # Legacy persisted threads stored the operator id in `user_id` without `owner_user_id`.
        if (
            not raw_owner
            and raw_user
            and raw_user != UNASSIGNED_CLIENT_USER_ID
            and raw_user != resolved_client
        ):
            raw_owner = raw_user
        status_val = normalize_chat_session_status(
            data.get("status") or raw_session.get("status")
        )
        return cls(
            thread_id=thread_id,
            session_id=str(data.get("session_id") or raw_session.get("session_id") or thread_id),
            user_id=resolved_client,
            owner_user_id=raw_owner or None,
            owner_email=data.get("owner_email"),
            agent_id=normalize_agent_id(
                data.get("agent_id") or raw_session.get("agent_id")
            ),
            client_id=str(
                data.get("client_id")
                or raw_session.get("client_id")
                or "trackflow-backoffice"
            ),
            status=status_val,
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


__all__ = [
    "AgentChatEventName",
    "AgentChatStreamEvent",
    "AgentCheckpoint",
    "AgentQueryRequest",
    "AgentQueryResult",
    "AgentState",
    "AgentTrace",
    "AuditEventType",
    "AuthenticatedSessionContext",
    "ChatInterruptedReason",
    "ChatMessage",
    "ChatSession",
    "ChatSessionStatus",
    "ChatThreadState",
    "ChatTurnRole",
    "ChatTurnStatus",
    "ConsolidatedCarrierProfile",
    "CustomerSegment",
    "GuardrailAction",
    "GuardrailAuditEvent",
    "GuardrailDisposition",
    "GuardrailEvaluationResult",
    "GuardrailFailureCategory",
    "GuardrailFailureType",
    "GuardrailInputCategory",
    "GuardrailLayer",
    "GuardrailSummaryReport",
    "IntentOutcome",
    "InventoryRecordDTO",
    "InventoryToolInput",
    "InventoryToolOutput",
    "KnowledgeChunk",
    "MemoryAuditLogEntry",
    "MemoryCategory",
    "MemoryGuardrailVerdict",
    "MemoryProposal",
    "OperatingCountry",
    "PersistentMemoryRecord",
    "ProposalStatus",
    "RetrievedContext",
    "SourceCitation",
    "TicketRecordDTO",
    "TicketToolInput",
    "TicketToolOutput",
    "ToolCallStatus",
    "UserIntentClassification",
]
