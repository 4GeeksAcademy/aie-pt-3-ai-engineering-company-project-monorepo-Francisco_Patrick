"""Domain entities, state contracts, and value objects for the TrackFlow Support Agent.

Defines the minimal, explicit `AgentState` TypedDict passed between LangGraph nodes,
along with immutable audit models (`AgentTrace`, `AgentCheckpoint`) and service DTOs.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict

from domain.knowledge.entities import (
    KnowledgeChunk,
    RetrievedContext,
    SourceCitation,
)


class AgentState(TypedDict, total=False):
    """Minimal state dictionary transferred between LangGraph nodes during a single run.

    Excludes full historical conversational chat logs to preserve token efficiency
    and enforce strict, inspectable state boundaries (FR-001).
    """

    query: str
    language: str
    top_k: int
    min_score: float
    contexts: List[RetrievedContext]
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
    node_outputs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    checkpoints: List[AgentCheckpoint] = field(default_factory=list)


__all__ = [
    "AgentCheckpoint",
    "AgentQueryRequest",
    "AgentQueryResult",
    "AgentState",
    "AgentTrace",
    "KnowledgeChunk",
    "RetrievedContext",
    "SourceCitation",
]
