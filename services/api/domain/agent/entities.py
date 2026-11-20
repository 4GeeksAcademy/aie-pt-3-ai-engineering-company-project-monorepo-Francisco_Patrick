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
    node_history: List[str]
    step_latencies: Dict[str, float]
    node_outputs: Dict[str, Dict[str, Any]]
    error: Optional[str]


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
    "InventoryRecordDTO",
    "InventoryToolInput",
    "InventoryToolOutput",
    "KnowledgeChunk",
    "RetrievedContext",
    "SourceCitation",
    "TicketRecordDTO",
    "TicketToolInput",
    "TicketToolOutput",
    "ToolCallStatus",
]
