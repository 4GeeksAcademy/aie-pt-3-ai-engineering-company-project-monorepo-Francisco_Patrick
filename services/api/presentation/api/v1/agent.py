"""FastAPI presentation router for the TrackFlow Support Agent with LangGraph (T046).

Adheres strictly to Monorepo Constitution Principles II & IV:
- Explicit Pydantic `response_model` on all endpoints
- Dependency injection via FastAPI `Depends`
- Non-blocking asynchronous execution via `run_in_threadpool`
- Defensive exception boundaries guaranteeing zero raw stack traces or internal file paths leak.
"""

import logging
from fastapi import APIRouter, Depends, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from typing import Any
from domain.agent.entities import AgentQueryRequest
from domain.agent.exceptions import (
    MemoryGuardrailViolationError,
    MemoryNotFoundError,
    TraceNotFoundError,
    WorkflowExecutionError,
)
from domain.agent.ports import SupportAgentServicePort
from domain.knowledge.exceptions import KnowledgeBaseUnavailableException
from presentation.dependencies import (
    get_agent_memory_service_dep,
    get_support_agent_service,
)
from presentation.schemas.agent import (
    AgentHealthResponseSchema,
    AgentQueryRequestSchema,
    AgentQueryResponseSchema,
    AgentTraceResponseSchema,
    KnowledgeSourceCitationSchema,
    MemoryProposalFeedbackRequestSchema,
    MemoryProposalFeedbackResponseSchema,
    MemoryProposalResponseSchema,
    MemoryProposalSchema,
    SanitizedErrorResponse,
    ToolCallTraceSchema,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Support Agent"])


@router.post(
    "/query",
    response_model=AgentQueryResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Submit operational query to LangGraph support agent",
    responses={
        500: {"model": SanitizedErrorResponse, "description": "Sanitized internal workflow error"},
    },
)
async def query_support_agent(
    payload: AgentQueryRequestSchema,
    agent_service: SupportAgentServicePort = Depends(get_support_agent_service),
) -> AgentQueryResponseSchema | JSONResponse:
    """Execute the compiled LangGraph support agent workflow and return a grounded answer with trace metadata."""
    domain_request = AgentQueryRequest(
        query=payload.query,
        top_k=payload.top_k,
        min_score=payload.min_score if payload.min_score is not None else 0.62,
        thread_id=payload.thread_id,
        language=payload.language or "en",
    )

    try:
        result = await run_in_threadpool(agent_service.query, domain_request)
    except KnowledgeBaseUnavailableException:
        raise
    except WorkflowExecutionError as exc:
        logger.error(
            "WorkflowExecutionError during support agent query (trace_id=%s)",
            exc.trace_id,
        )
        err_payload = SanitizedErrorResponse(
            detail="An internal error occurred while processing the agent workflow.",
            error_code="INTERNAL_WORKFLOW_ERROR",
            trace_id=exc.trace_id,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=err_payload.model_dump(),
        )
    except Exception:
        logger.error("Unhandled exception during support agent query execution.")
        err_payload = SanitizedErrorResponse(
            detail="An internal error occurred while processing the agent workflow.",
            error_code="INTERNAL_WORKFLOW_ERROR",
            trace_id=payload.thread_id,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=err_payload.model_dump(),
        )

    tool_call_schemas = [
        ToolCallTraceSchema(
            tool_name=tc.get("tool_name", "ticket_tool"),
            status=tc.get("status", "success"),
            total_matched=int(tc.get("total_matched", 0)),
            returned_count=int(tc.get("returned_count", 0)),
            latency_ms=float(tc.get("latency_ms", 0.0)),
            error_message=tc.get("error_message"),
        )
        for tc in getattr(result, "tool_calls", [])
        if isinstance(tc, dict)
    ]

    proposal_obj = getattr(result, "memory_proposal", None)
    proposal_schema = (
        MemoryProposalSchema(
            proposal_id=proposal_obj.proposal_id,
            category=proposal_obj.category,
            target_entity=proposal_obj.target_entity,
            country_code=proposal_obj.country_code,
            summary=proposal_obj.summary,
            status=proposal_obj.status,
            confidence=proposal_obj.confidence,
            created_at=proposal_obj.created_at.isoformat(),
        )
        if proposal_obj is not None
        else None
    )

    return AgentQueryResponseSchema(
        query=result.query,
        answer=result.answer,
        is_refusal=result.is_refusal,
        fallback_triggered=bool(getattr(result, "fallback_triggered", False)),
        sources=[
            KnowledgeSourceCitationSchema(
                source_document=src.source_document,
                section=src.section,
                similarity_score=src.similarity_score,
            )
            for src in result.sources
        ],
        sources_consulted=list(getattr(result, "sources_consulted", [])),
        tool_calls=tool_call_schemas,
        memory_proposal=proposal_schema,
        recalled_memories=list(getattr(result, "recalled_memories", [])),
        trace_id=result.trace_id,
        node_sequence=result.node_sequence,
        execution_time_ms=result.execution_time_ms,
    )


@router.get(
    "/proposals/pending",
    response_model=MemoryProposalResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Retrieve active pending memory proposal for a session/thread",
)
async def get_pending_proposal(
    thread_id: str,
    memory_service: Any = Depends(get_agent_memory_service_dep),
) -> MemoryProposalResponseSchema:
    """Return the active pending memory proposal for `thread_id`, or null if none is active."""
    proposal = await run_in_threadpool(memory_service.get_pending_proposal, thread_id)
    if proposal is None:
        return MemoryProposalResponseSchema(proposal=None)
    return MemoryProposalResponseSchema(
        proposal=MemoryProposalSchema(
            proposal_id=proposal.proposal_id,
            category=proposal.category,
            target_entity=proposal.target_entity,
            country_code=proposal.country_code,
            summary=proposal.summary,
            status=proposal.status,
            confidence=proposal.confidence,
            created_at=proposal.created_at.isoformat(),
        )
    )


@router.post(
    "/proposals/{proposal_id}/feedback",
    response_model=MemoryProposalFeedbackResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Submit explicit feedback on an active memory proposal (T024)",
    responses={
        400: {"model": SanitizedErrorResponse, "description": "Guardrail violation"},
        404: {"model": SanitizedErrorResponse, "description": "Proposal not found"},
    },
)
async def submit_proposal_feedback(
    proposal_id: str,
    payload: MemoryProposalFeedbackRequestSchema,
    memory_service: Any = Depends(get_agent_memory_service_dep),
) -> MemoryProposalFeedbackResponseSchema | JSONResponse:
    """Apply explicit out-of-band operator feedback (approve, reject, edit) to a memory proposal."""
    try:
        outcome = await run_in_threadpool(
            memory_service.apply_explicit_feedback,
            proposal_id,
            payload.action,
            payload.refined_content,
            payload.operator_id,
        )
    except MemoryNotFoundError:
        err = SanitizedErrorResponse(
            detail=f"Active memory proposal '{proposal_id}' was not found.",
            error_code="PROPOSAL_NOT_FOUND",
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=err.model_dump(),
        )
    except MemoryGuardrailViolationError as exc:
        err = SanitizedErrorResponse(
            detail=exc.reason,
            error_code=exc.violation_code,
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=err.model_dump(),
        )

    return MemoryProposalFeedbackResponseSchema(
        proposal_id=str(outcome["proposal_id"]),
        status=outcome["status"],
        resulting_action=str(outcome["resulting_action"]),
        committed_memory_id=outcome.get("committed_memory_id"),
    )


@router.get(
    "/trace/{trace_id}",
    response_model=AgentTraceResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Query execution trace for an agent run",
    responses={
        404: {"model": SanitizedErrorResponse, "description": "Trace not found"},
        500: {"model": SanitizedErrorResponse, "description": "Sanitized internal error"},
    },
)
async def get_agent_trace(
    trace_id: str,
    agent_service: SupportAgentServicePort = Depends(get_support_agent_service),
) -> AgentTraceResponseSchema | JSONResponse:
    """Retrieve the structured execution trace including node sequence, consulted sources, latencies, and metadata."""
    try:
        trace = await run_in_threadpool(agent_service.get_trace, trace_id)
    except TraceNotFoundError:
        not_found_payload = SanitizedErrorResponse(
            detail=f"Execution trace '{trace_id}' was not found.",
            error_code="TRACE_NOT_FOUND",
            trace_id=trace_id,
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=not_found_payload.model_dump(),
        )
    except KnowledgeBaseUnavailableException:
        raise
    except Exception:
        logger.error("Unhandled exception while retrieving agent trace_id=%s", trace_id)
        err_payload = SanitizedErrorResponse(
            detail="An internal error occurred while retrieving the execution trace.",
            error_code="INTERNAL_WORKFLOW_ERROR",
            trace_id=trace_id,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=err_payload.model_dump(),
        )

    tool_call_schemas = [
        ToolCallTraceSchema(
            tool_name=tc.get("tool_name", "ticket_tool"),
            status=tc.get("status", "success"),
            total_matched=int(tc.get("total_matched", 0)),
            returned_count=int(tc.get("returned_count", 0)),
            latency_ms=float(tc.get("latency_ms", 0.0)),
            error_message=tc.get("error_message"),
        )
        for tc in getattr(trace, "tool_calls", [])
        if isinstance(tc, dict)
    ]

    return AgentTraceResponseSchema(
        trace_id=trace.trace_id,
        query=trace.query,
        node_sequence=trace.node_sequence,
        sources_consulted=list(getattr(trace, "sources_consulted", [])),
        fallback_triggered=bool(getattr(trace, "fallback_triggered", False)),
        tool_calls=tool_call_schemas,
        step_latencies=trace.step_latencies,
        total_duration_ms=trace.total_duration_ms,
        is_refusal=trace.is_refusal,
        final_answer=trace.final_answer,
        source_count=trace.source_count,
        node_outputs=trace.node_outputs,
    )


@router.get(
    "/health",
    response_model=AgentHealthResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Health check for compiled agent workflow",
)
async def get_agent_health(
    agent_service: SupportAgentServicePort = Depends(get_support_agent_service),
) -> AgentHealthResponseSchema:
    """Confirm graph compilation state and checkpointer readiness."""
    health_data = await run_in_threadpool(agent_service.get_health)
    return AgentHealthResponseSchema(
        status=str(health_data.get("status", "healthy")),
        compiled=bool(health_data.get("compiled", True)),
        nodes=[str(n) for n in health_data.get("nodes", [])],
        checkpointer=str(health_data.get("checkpointer", "MemorySaver")),
    )
