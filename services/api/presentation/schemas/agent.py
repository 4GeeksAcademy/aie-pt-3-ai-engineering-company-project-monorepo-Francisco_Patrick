"""Pydantic request and response schemas for TrackFlow Support Agent endpoints (T033).

Conforms strictly to:
- `specs/027-support-agent-langgraph/contracts/agent-api.yaml`
- Monorepo Constitution Principle II (Public API Compatibility & Strict Contract Serialization)
- Monorepo Constitution Principle IV (Defensive Error Handling & Zero Sensitive Data Leaks).
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from presentation.schemas.knowledge import KnowledgeSourceCitationSchema


class AgentQueryRequestSchema(BaseModel):
    """Request payload for submitting operational inquiries to the LangGraph support agent."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Customer inquiry or policy question",
    )
    top_k: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Maximum number of knowledge chunks to retrieve",
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


class AgentQueryResponseSchema(BaseModel):
    """Response payload returned by POST /api/v1/agent/query."""

    query: str = Field(..., description="Echoed sanitized customer inquiry")
    answer: str = Field(
        ..., description="Synthesized grounded answer or standardized honest refusal"
    )
    is_refusal: bool = Field(
        ..., description="Whether the inquiry was refused due to out-of-scope or low similarity"
    )
    sources: List[KnowledgeSourceCitationSchema] = Field(
        default_factory=list,
        description="List of cited policy documents and sections",
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


__all__ = [
    "AgentHealthResponseSchema",
    "AgentQueryRequestSchema",
    "AgentQueryResponseSchema",
    "AgentTraceResponseSchema",
    "KnowledgeSourceCitationSchema",
    "SanitizedErrorResponse",
]
