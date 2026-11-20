"""Pydantic request and response schemas for TrackFlow Support Agent endpoints (T044).

Conforms strictly to:
- `specs/027-support-agent-langgraph/contracts/agent-api.yaml`
- Monorepo Constitution Principle II (Public API Compatibility & Strict Contract Serialization)
- Monorepo Constitution Principle IV (Defensive Error Handling & Zero Sensitive Data Leaks).
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from presentation.schemas.knowledge import KnowledgeSourceCitationSchema


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
        description="Ordered list of data sources consulted during the run ('ticket_tool', 'inventory_tool', 'rag')",
    )
    tool_calls: List[ToolCallTraceSchema] = Field(
        default_factory=list,
        description="Ordered summary of operational tool invocations",
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


__all__ = [
    "AgentHealthResponseSchema",
    "AgentQueryRequestSchema",
    "AgentQueryResponseSchema",
    "AgentTraceResponseSchema",
    "KnowledgeSourceCitationSchema",
    "SanitizedErrorResponse",
    "ToolCallTraceSchema",
]
