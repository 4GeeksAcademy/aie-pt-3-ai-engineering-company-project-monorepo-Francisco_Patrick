"""Domain entities, state contracts, and value objects for the TrackFlow Support Agent.

Defines the minimal, explicit `AgentState` TypedDict passed between LangGraph nodes,
strictly read-only operational tool input/output contracts (`TicketToolInput`,
`TicketRecordDTO`, `TicketToolOutput`, `InventoryToolInput`, `InventoryRecordDTO`,
`InventoryToolOutput`), and immutable audit models (`AgentTrace`, `AgentCheckpoint`).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, TypedDict

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


@dataclass(frozen=True)
class AgentQueryRequest:
    """Domain request object submitted to the SupportAgentService."""

    query: str
    top_k: int = 3
    min_score: float = 0.62
    thread_id: Optional[str] = None
    language: str = "en"


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


__all__ = [
    "AgentCheckpoint",
    "AgentQueryRequest",
    "AgentQueryResult",
    "AgentState",
    "AgentTrace",
    "AuditEventType",
    "ConsolidatedCarrierProfile",
    "IntentOutcome",
    "InventoryRecordDTO",
    "InventoryToolInput",
    "InventoryToolOutput",
    "KnowledgeChunk",
    "MemoryAuditLogEntry",
    "MemoryCategory",
    "MemoryGuardrailVerdict",
    "MemoryProposal",
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
