"""FastAPI presentation router for the TrackFlow Support Agent with LangGraph (T035).

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

from domain.agent.entities import AgentQueryRequest
from domain.agent.exceptions import TraceNotFoundError, WorkflowExecutionError
from domain.agent.ports import SupportAgentServicePort
from domain.knowledge.exceptions import KnowledgeBaseUnavailableException
from presentation.dependencies import get_support_agent_service
from presentation.schemas.agent import (
    AgentHealthResponseSchema,
    AgentQueryRequestSchema,
    AgentQueryResponseSchema,
    AgentTraceResponseSchema,
    KnowledgeSourceCitationSchema,
    SanitizedErrorResponse,
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

    return AgentQueryResponseSchema(
        query=result.query,
        answer=result.answer,
        is_refusal=result.is_refusal,
        sources=[
            KnowledgeSourceCitationSchema(
                source_document=src.source_document,
                section=src.section,
                similarity_score=src.similarity_score,
            )
            for src in result.sources
        ],
        trace_id=result.trace_id,
        node_sequence=result.node_sequence,
        execution_time_ms=result.execution_time_ms,
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
    """Retrieve the structured execution trace including node sequence, latencies, and metadata."""
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

    return AgentTraceResponseSchema(
        trace_id=trace.trace_id,
        query=trace.query,
        node_sequence=trace.node_sequence,
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
