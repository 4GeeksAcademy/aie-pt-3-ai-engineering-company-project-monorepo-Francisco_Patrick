"""FastAPI presentation router for the TrackFlow Support Agent with LangGraph (T046).

Adheres strictly to Monorepo Constitution Principles II & IV:
- Explicit Pydantic `response_model` on all endpoints
- Dependency injection via FastAPI `Depends`
- Non-blocking asynchronous execution via `run_in_threadpool`
- Defensive exception boundaries guaranteeing zero raw stack traces or internal file paths leak.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
import re
import uuid
from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from typing import Any, Dict, List, Optional, Tuple
from application.services.agent_action_policies import (
    get_agent_action_policies_service,
)
from application.services.user_service import UserService
from domain.agent.entities import (
    AgentQueryRequest,
    AuthenticatedSessionContext,
    ChatMessage,
    ChatThreadState,
)
from domain.agent.exceptions import (
    MemoryGuardrailViolationError,
    MemoryNotFoundError,
    ThreadOwnershipMismatchError,
    TraceNotFoundError,
    WorkflowExecutionError,
)
from domain.agent.ports import (
    AgentChatEventBrokerPort,
    AgentChatThreadRepositoryPort,
    GuardrailObservabilityPort,
    SupportAgentServicePort,
)
from domain.exceptions import AuthenticationError
from domain.knowledge.exceptions import KnowledgeBaseUnavailableException
from domain.models import User
from domain.ports import SecurityPort
from presentation.dependencies import (
    get_agent_chat_event_broker_dep,
    get_agent_chat_thread_repository_dep,
    get_agent_memory_service_dep,
    get_current_user,
    get_guardrail_observability_dep,
    get_security_adapter_dep,
    get_support_agent_service,
    get_user_service_dep,
    verify_llm_rate_limit,
)
from presentation.schemas.security_audit import (
    HumanApprovalDecisionRequest,
    HumanApprovalGateResponse,
)
from presentation.schemas.agent import (
    AgentHealthResponseSchema,
    AgentQueryRequestSchema,
    AgentQueryResponseSchema,
    AgentTraceResponseSchema,
    ChatMessageSchema,
    ChatThreadHistoryResponseSchema,
    ClientAuthenticateFrameSchema,
    ClientInterruptFrameSchema,
    ClientPingFrameSchema,
    ClientRehydrateFrameSchema,
    ClientUserMessageFrameSchema,
    GuardrailInterventionSchema,
    GuardrailResetResponseSchema,
    HITLApprovalResponseSchema,
    HITLReviewDecisionRequestSchema,
    GuardrailSummaryResponseSchema,
    KnowledgeSourceCitationSchema,
    MemoryProposalFeedbackRequestSchema,
    MemoryProposalFeedbackResponseSchema,
    MemoryProposalResponseSchema,
    MemoryProposalSchema,
    SanitizedErrorResponse,
    ServerErrorEventSchema,
    ServerGenerationCompletedEventSchema,
    ServerGenerationInterruptedEventSchema,
    ServerGenerationStartedEventSchema,
    ServerPongEventSchema,
    ServerSessionRehydratedEventSchema,
    ServerTokenChunkEventSchema,
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
    _rate_limit: None = Depends(verify_llm_rate_limit),
) -> AgentQueryResponseSchema | JSONResponse:
    """Execute the compiled LangGraph support agent workflow and return a grounded answer with trace metadata."""
    session_ctx: Optional[AuthenticatedSessionContext] = None
    if payload.session_context is not None:
        session_ctx = AuthenticatedSessionContext(
            session_id=payload.session_context.session_id,
            customer_id=payload.session_context.customer_id,
            customer_segment=payload.session_context.customer_segment,
            primary_operating_country=payload.session_context.primary_operating_country,
            authorized_order_ids=tuple(payload.session_context.authorized_order_ids),
            order_country_map=dict(payload.session_context.order_country_map),
        )

    domain_request = AgentQueryRequest(
        query=payload.query,
        top_k=payload.top_k,
        min_score=payload.min_score if payload.min_score is not None else 0.62,
        thread_id=payload.thread_id,
        language=payload.language or "en",
        session_context=session_ctx,
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

    guardrail_schemas = [
        GuardrailInterventionSchema(
            event_id=ev.event_id,
            timestamp=ev.timestamp.isoformat(),
            session_id=ev.session_id,
            trace_id=ev.trace_id,
            failure_type=ev.failure_type,
            layer=ev.layer,
            input_category=ev.input_category,
            reason_code=ev.reason_code,
            disposition=ev.disposition,
            redacted_preview=ev.redacted_preview,
        )
        for ev in getattr(result, "guardrail_interventions", [])
    ]

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
        guardrail_interventions=guardrail_schemas,
        resolved_country=getattr(result, "resolved_country", None),
        trace_id=result.trace_id,
        node_sequence=result.node_sequence,
        execution_time_ms=result.execution_time_ms,
    )


@router.get(
    "/guardrails/summary",
    response_model=GuardrailSummaryResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Retrieve aggregated guardrail trigger counts and recent sanitized audit events (FR-012)",
)
async def get_guardrail_summary(
    session_id: Optional[str] = Query(
        default=None,
        description="Optional session/thread ID filter to scope trigger counts to a specific test session",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of recent sanitized guardrail audit events to include",
    ),
    reset: bool = Query(
        default=False,
        description="When true, clear in-memory guardrail counters and events after returning summary",
    ),
    observability: GuardrailObservabilityPort = Depends(get_guardrail_observability_dep),
) -> GuardrailSummaryResponseSchema:
    """Return aggregated guardrail trigger counts by failure type ('structural', 'content', 'security') and layer."""
    report = await run_in_threadpool(observability.get_summary, session_id, limit)
    if reset:
        await run_in_threadpool(observability.clear)
    return GuardrailSummaryResponseSchema(
        total_evaluations=report.total_evaluations,
        total_interventions=report.total_interventions,
        by_failure_type=dict(report.by_failure_type),
        by_layer=dict(report.by_layer),
        by_input_category=dict(report.by_input_category),
        by_disposition=dict(report.by_disposition),
        window_start=report.window_start.isoformat() if report.window_start else None,
        window_end=report.window_end.isoformat() if report.window_end else None,
        recent_events=[
            GuardrailInterventionSchema(
                event_id=ev.event_id,
                timestamp=ev.timestamp.isoformat(),
                session_id=ev.session_id,
                trace_id=ev.trace_id,
                failure_type=ev.failure_type,
                layer=ev.layer,
                input_category=ev.input_category,
                reason_code=ev.reason_code,
                disposition=ev.disposition,
                redacted_preview=ev.redacted_preview,
            )
            for ev in report.recent_events
        ],
    )


@router.post(
    "/guardrails/reset",
    response_model=GuardrailResetResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Reset in-memory guardrail trigger counters and audit event history",
)
async def reset_guardrails(
    observability: GuardrailObservabilityPort = Depends(get_guardrail_observability_dep),
) -> GuardrailResetResponseSchema:
    """Clear all in-memory guardrail counters and audit events."""
    await run_in_threadpool(observability.clear)
    return GuardrailResetResponseSchema(
        status="cleared",
        message="Guardrail observability metrics and audit events cleared.",
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


def _project_chat_message_schema(msg: ChatMessage) -> ChatMessageSchema:
    """Project a ChatMessage domain entity into a validated ChatMessageSchema DTO."""
    tool_calls = [
        ToolCallTraceSchema(
            tool_name=(
                tc.get("tool_name")
                if tc.get("tool_name") in ("ticket_tool", "inventory_tool")
                else "ticket_tool"
            ),
            status=(
                tc.get("status")
                if tc.get("status") in ("success", "not_found", "timeout", "error")
                else "success"
            ),
            total_matched=int(tc.get("total_matched", 0)),
            returned_count=max(0, min(20, int(tc.get("returned_count", 0)))),
            latency_ms=max(0.0, float(tc.get("latency_ms", 0.0))),
            error_message=tc.get("error_message"),
        )
        for tc in msg.tool_calls
        if isinstance(tc, dict)
    ]
    proposal = msg.memory_proposal
    proposal_schema = (
        MemoryProposalSchema(
            proposal_id=proposal.proposal_id,
            category=proposal.category,
            target_entity=proposal.target_entity,
            country_code=proposal.country_code,
            summary=proposal.summary,
            status=proposal.status,
            confidence=proposal.confidence,
            created_at=proposal.created_at.isoformat(),
        )
        if proposal is not None
        else None
    )
    interventions = [
        GuardrailInterventionSchema(
            event_id=ev.event_id,
            timestamp=ev.timestamp.isoformat(),
            session_id=ev.session_id,
            trace_id=ev.trace_id,
            failure_type=ev.failure_type,
            layer=ev.layer,
            input_category=ev.input_category,
            reason_code=ev.reason_code,
            disposition=ev.disposition,
            redacted_preview=ev.redacted_preview,
        )
        for ev in msg.guardrail_interventions
    ]
    return ChatMessageSchema(
        turn_id=msg.turn_id,
        thread_id=msg.thread_id,
        session_id=msg.session_id,
        role=msg.role,
        content=msg.content,
        status=msg.status,
        parent_user_turn_id=msg.parent_user_turn_id,
        interrupted_reason=msg.interrupted_reason,
        is_refusal=bool(msg.is_refusal),
        fallback_triggered=bool(msg.fallback_triggered),
        trace_id=msg.trace_id,
        node_sequence=list(msg.node_sequence),
        execution_time_ms=max(0.0, float(msg.execution_time_ms)),
        sources=[
            KnowledgeSourceCitationSchema(
                source_document=s.source_document,
                section=s.section,
                similarity_score=s.similarity_score,
            )
            for s in msg.sources
        ],
        sources_consulted=list(msg.sources_consulted),
        tool_calls=tool_calls,
        memory_proposal=proposal_schema,
        recalled_memories=list(msg.recalled_memories),
        guardrail_interventions=interventions,
        resolved_country=msg.resolved_country,
        created_at=msg.created_at.isoformat(),
        updated_at=msg.updated_at.isoformat(),
    )


def _validate_and_serialize_outbound_frame(frame: Dict[str, Any]) -> Dict[str, Any]:
    """Validate outbound server-to-client WebSocket frame against its strict Pydantic schema (T035)."""
    event_name = frame.get("event")
    if event_name == "session_rehydrated":
        return ServerSessionRehydratedEventSchema.model_validate(frame).model_dump()
    if event_name == "generation_started":
        return ServerGenerationStartedEventSchema.model_validate(frame).model_dump()
    if event_name == "token_chunk":
        return ServerTokenChunkEventSchema.model_validate(frame).model_dump()
    if event_name == "generation_interrupted":
        return ServerGenerationInterruptedEventSchema.model_validate(frame).model_dump()
    if event_name == "generation_completed":
        return ServerGenerationCompletedEventSchema.model_validate(frame).model_dump()
    if event_name == "error":
        return ServerErrorEventSchema.model_validate(frame).model_dump()
    if event_name == "pong":
        return ServerPongEventSchema.model_validate(frame).model_dump()
    return dict(frame)


@router.get(
    "/threads/{thread_id}/history",
    response_model=ChatThreadHistoryResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Retrieve persisted conversation thread history, interrupted turns, and checkpoint state",
    responses={
        401: {"model": SanitizedErrorResponse, "description": "Missing, invalid, or expired Bearer JWT"},
        403: {"model": SanitizedErrorResponse, "description": "Thread belongs to a different authenticated user"},
        500: {"model": SanitizedErrorResponse, "description": "Sanitized internal error"},
    },
)
async def get_thread_history_endpoint(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    agent_service: SupportAgentServicePort = Depends(get_support_agent_service),
    thread_repository: AgentChatThreadRepositoryPort = Depends(
        get_agent_chat_thread_repository_dep
    ),
    broker: AgentChatEventBrokerPort = Depends(get_agent_chat_event_broker_dep),
) -> ChatThreadHistoryResponseSchema | JSONResponse:
    """Return persisted conversation thread history and checkpoint count for the authenticated operator."""
    owner_user_id = str(current_user.id)
    try:
        if hasattr(agent_service, "get_thread_history"):
            thread_state, checkpoint_count = await run_in_threadpool(
                getattr(agent_service, "get_thread_history"),
                thread_id,
                owner_user_id,
            )
        else:
            existing = await run_in_threadpool(thread_repository.get_thread, thread_id)
            if existing is not None:
                if existing.owner_user_id and existing.owner_user_id != owner_user_id:
                    raise ThreadOwnershipMismatchError(
                        thread_id=thread_id,
                        requester_user_id=owner_user_id,
                    )
                thread_state = existing
            else:
                now = datetime.now(timezone.utc)
                thread_state = ChatThreadState(
                    thread_id=thread_id,
                    session_id=thread_id,
                    owner_user_id=owner_user_id,
                    owner_email=current_user.email,
                    messages=[],
                    latest_sequence_id=broker.get_latest_sequence_id(thread_id),
                    created_at=now,
                    updated_at=now,
                )
            checkpoints = await run_in_threadpool(
                agent_service.get_checkpoints, thread_id
            )
            checkpoint_count = len(checkpoints)
    except ThreadOwnershipMismatchError:
        forbidden = SanitizedErrorResponse(
            detail=f"Conversation thread '{thread_id}' is bound to a different operator account.",
            error_code="THREAD_FORBIDDEN",
        )
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content=forbidden.model_dump(),
        )
    except Exception:
        logger.error(
            "Unhandled error while retrieving thread history for thread_id=%s",
            thread_id,
        )
        err = SanitizedErrorResponse(
            detail="An internal error occurred while retrieving conversation thread history.",
            error_code="INTERNAL_WORKFLOW_ERROR",
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=err.model_dump(),
        )

    pending = thread_state.pending_proposal
    pending_schema = (
        MemoryProposalSchema(
            proposal_id=pending.proposal_id,
            category=pending.category,
            target_entity=pending.target_entity,
            country_code=pending.country_code,
            summary=pending.summary,
            status=pending.status,
            confidence=pending.confidence,
            created_at=pending.created_at.isoformat(),
        )
        if pending is not None
        else None
    )

    return ChatThreadHistoryResponseSchema(
        thread_id=thread_state.thread_id,
        session_id=thread_state.session_id,
        owner_user_id=thread_state.owner_user_id,
        messages=[_project_chat_message_schema(m) for m in thread_state.messages],
        pending_proposal=pending_schema,
        latest_checkpoint_id=thread_state.latest_checkpoint_id,
        latest_sequence_id=thread_state.latest_sequence_id,
        checkpoint_count=checkpoint_count,
        created_at=thread_state.created_at.isoformat(),
        updated_at=thread_state.updated_at.isoformat(),
    )


def _sanitize_websocket_query_for_logging(raw_query_or_url: str) -> str:
    """Redact any `?token=<jwt>` or `&token=<jwt>` parameter before diagnostic logging.

    Note: Browser `new WebSocket(url)` cannot set custom `Authorization` headers, so FR-002
    supports both `?token=<jwt>` handshake authentication and first-frame `authenticate` messages.
    Reverse proxies and ASGI access loggers should redact `token` query parameters in production.
    """
    if not raw_query_or_url:
        return ""
    return re.sub(
        r"(?i)(^|[?&])token=[^&\s]+",
        r"\1token=[REDACTED]",
        raw_query_or_url,
    )


def _extract_handshake_bearer_token(websocket: WebSocket) -> Optional[str]:
    """Extract JWT token from `?token=` query param or `Authorization: Bearer <token>` header."""
    query_token = websocket.query_params.get("token")
    if query_token and query_token.strip():
        cleaned_q = query_token.strip()
        if cleaned_q.lower().startswith("bearer "):
            cleaned_q = cleaned_q[7:].strip()
        return cleaned_q

    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.strip():
        raw_hdr = auth_header.strip()
        if raw_hdr.lower().startswith("bearer "):
            return raw_hdr[7:].strip()
        return raw_hdr
    return None


def _verify_jwt_token_to_user(
    raw_token: str,
    security_adapter: SecurityPort,
    user_service: UserService,
) -> Optional[User]:
    """Decode JWT token and verify user exists and is active. Returns None if invalid."""
    if not raw_token or not raw_token.strip():
        return None
    try:
        user_id = security_adapter.decode_access_token(raw_token.strip())
    except (AuthenticationError, Exception):
        return None

    user = user_service.get_user_by_id(user_id)
    if user is None or not user.is_active:
        return None
    return user


async def _authenticate_websocket_connection(
    websocket: WebSocket,
    security_adapter: SecurityPort,
    user_service: UserService,
    first_frame_timeout_seconds: float = 5.0,
) -> Tuple[Optional[User], Optional[str], Optional[str], bool]:
    """Authenticate a WebSocket connection via handshake token or first-frame `authenticate` message.

    Returns:
        Tuple of `(authenticated_user, override_thread_id, override_session_id, was_accepted)`.
    """
    handshake_token = _extract_handshake_bearer_token(websocket)
    if handshake_token is not None:
        user = await run_in_threadpool(
            _verify_jwt_token_to_user,
            handshake_token,
            security_adapter,
            user_service,
        )
        if user is None:
            await websocket.accept()
            await websocket.close(code=4001, reason="UNAUTHORIZED")
            return (None, None, None, True)
        await websocket.accept()
        return (user, None, None, True)

    # No handshake token: accept connection and require an immediate first-frame {"event": "authenticate", "token": "..."}
    await websocket.accept()
    try:
        raw_text = await asyncio.wait_for(
            websocket.receive_text(), timeout=first_frame_timeout_seconds
        )
        data = json.loads(raw_text)
        if not isinstance(data, dict) or data.get("event") != "authenticate":
            await websocket.close(code=4001, reason="UNAUTHORIZED")
            return (None, None, None, True)
        auth_frame = ClientAuthenticateFrameSchema.model_validate(data)
    except WebSocketDisconnect:
        return (None, None, None, True)
    except Exception:
        await websocket.close(code=4001, reason="UNAUTHORIZED")
        return (None, None, None, True)

    user = await run_in_threadpool(
        _verify_jwt_token_to_user,
        auth_frame.token,
        security_adapter,
        user_service,
    )
    if user is None:
        await websocket.close(code=4001, reason="UNAUTHORIZED")
        return (None, None, None, True)

    return (user, auth_frame.thread_id, auth_frame.session_id, True)


@router.websocket("/ws")
async def support_agent_websocket_endpoint(
    websocket: WebSocket,
    agent_service: SupportAgentServicePort = Depends(get_support_agent_service),
    thread_repository: AgentChatThreadRepositoryPort = Depends(
        get_agent_chat_thread_repository_dep
    ),
    broker: AgentChatEventBrokerPort = Depends(get_agent_chat_event_broker_dep),
    security_adapter: SecurityPort = Depends(get_security_adapter_dep),
    user_service: UserService = Depends(get_user_service_dep),
) -> None:
    """Bidirectional WebSocket endpoint for real-time Support Agent token streaming & true generation abort (FR-001..FR-013)."""
    user, auth_thread_id, auth_session_id, _ = await _authenticate_websocket_connection(
        websocket=websocket,
        security_adapter=security_adapter,
        user_service=user_service,
    )
    if user is None:
        return

    owner_user_id = str(user.id)
    raw_thread_id = (
        auth_thread_id
        or websocket.query_params.get("thread_id")
        or auth_session_id
        or websocket.query_params.get("session_id")
        or ""
    ).strip()
    if not raw_thread_id:
        await websocket.close(code=1008, reason="MISSING_THREAD_OR_SESSION_ID")
        return
    thread_id = raw_thread_id
    raw_session_id = (
        auth_session_id
        or websocket.query_params.get("session_id")
        or thread_id
    ).strip()
    session_id = raw_session_id or thread_id

    # Verify per-operator thread ownership and load rehydration snapshot (FR-003, FR-012)
    try:
        if hasattr(agent_service, "rehydrate_thread"):
            rehydrated_payload = await run_in_threadpool(
                getattr(agent_service, "rehydrate_thread"),
                thread_id,
                session_id,
                owner_user_id,
                user.email,
            )
        else:
            existing = await run_in_threadpool(thread_repository.get_thread, thread_id)
            if (
                existing is not None
                and existing.owner_user_id
                and existing.owner_user_id != owner_user_id
            ):
                raise ThreadOwnershipMismatchError(
                    thread_id=thread_id,
                    requester_user_id=owner_user_id,
                )
            rehydrated_payload = {
                "owner_user_id": owner_user_id,
                "messages": (
                    [m.to_dict() for m in existing.messages]
                    if existing is not None
                    else []
                ),
                "pending_proposal": None,
                "latest_checkpoint_id": (
                    existing.latest_checkpoint_id if existing is not None else None
                ),
                "checkpoint_count": 0,
            }
    except ThreadOwnershipMismatchError:
        await websocket.close(code=4003, reason="THREAD_FORBIDDEN")
        return
    except Exception:
        logger.error("Failed to initialize thread state for thread_id=%s", thread_id)
        await websocket.close(code=1011, reason="INTERNAL_ERROR")
        return

    subscriber_queue = broker.subscribe(thread_id)
    send_lock = asyncio.Lock()

    async def _send_validated_frame(frame: Dict[str, Any]) -> None:
        validated = _validate_and_serialize_outbound_frame(frame)
        async with send_lock:
            await websocket.send_json(validated)

    async def _send_rehydration_snapshot() -> None:
        if hasattr(agent_service, "rehydrate_thread"):
            snapshot = await run_in_threadpool(
                getattr(agent_service, "rehydrate_thread"),
                thread_id,
                session_id,
                owner_user_id,
                user.email,
            )
        else:
            snapshot = rehydrated_payload
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        seq_id = broker.get_latest_sequence_id(thread_id)
        frame = {
            "event": "session_rehydrated",
            "thread_id": thread_id,
            "session_id": session_id,
            "owner_user_id": snapshot["owner_user_id"],
            "messages": snapshot["messages"],
            "pending_proposal": snapshot["pending_proposal"],
            "latest_checkpoint_id": snapshot["latest_checkpoint_id"],
            "checkpoint_count": snapshot["checkpoint_count"],
            "sequence_id": seq_id,
            "timestamp": now_iso,
        }
        await _send_validated_frame(frame)

    async def _broker_subscriber_writer_loop() -> None:
        """Forward pub/sub events from subscriber_queue to the connected WebSocket client."""
        while True:
            event = await subscriber_queue.get()
            frame_dict = event.to_frame_dict()
            await _send_validated_frame(frame_dict)

    async def _launch_generation_turn(
        user_msg_cmd: ClientUserMessageFrameSchema,
    ) -> None:
        """Start an asynchronous streaming generation task on the broker for `thread_id`."""
        # If a generation is already running on this thread, abort it first as a mid-stream redirect (FR-010)
        if broker.is_generating(thread_id):
            await broker.abort_active_generation(
                thread_id=thread_id,
                reason="redirect_new_message",
            )

        session_ctx: Optional[AuthenticatedSessionContext] = None
        if user_msg_cmd.session_context is not None:
            session_ctx = AuthenticatedSessionContext(
                session_id=user_msg_cmd.session_context.session_id,
                customer_id=user_msg_cmd.session_context.customer_id,
                customer_segment=user_msg_cmd.session_context.customer_segment,
                primary_operating_country=(
                    user_msg_cmd.session_context.primary_operating_country
                ),
                authorized_order_ids=tuple(
                    user_msg_cmd.session_context.authorized_order_ids
                ),
                order_country_map=dict(user_msg_cmd.session_context.order_country_map),
            )

        domain_req = AgentQueryRequest(
            query=user_msg_cmd.query,
            top_k=user_msg_cmd.top_k,
            min_score=user_msg_cmd.min_score,
            thread_id=thread_id,
            language=user_msg_cmd.language,
            session_context=session_ctx,
        )

        abort_event = asyncio.Event()
        assistant_turn_id = f"turn_{uuid.uuid4().hex[:12]}"
        user_turn_id = (
            user_msg_cmd.turn_id.strip()
            if user_msg_cmd.turn_id and user_msg_cmd.turn_id.strip()
            else f"usr_{uuid.uuid4().hex[:12]}"
        )

        async def _producer_runner() -> None:
            try:
                if hasattr(agent_service, "stream_query"):
                    await getattr(agent_service, "stream_query")(
                        request=domain_req,
                        owner_user_id=owner_user_id,
                        owner_email=user.email,
                        session_id=session_id,
                        user_turn_id=user_turn_id,
                        assistant_turn_id=assistant_turn_id,
                        abort_event=abort_event,
                        broker=broker,
                        thread_repository=thread_repository,
                    )
            except asyncio.CancelledError:
                raise
            except KnowledgeBaseUnavailableException:
                broker.publish(
                    thread_id=thread_id,
                    session_id=session_id,
                    event_name="error",
                    payload={
                        "turn_id": assistant_turn_id,
                        "error_code": "KNOWLEDGE_BASE_UNAVAILABLE",
                        "detail": "The TrackFlow knowledge base service is temporarily unavailable.",
                    },
                )
            except Exception:
                logger.error(
                    "Unhandled exception in streaming generation task for thread_id=%s",
                    thread_id,
                )
                broker.publish(
                    thread_id=thread_id,
                    session_id=session_id,
                    event_name="error",
                    payload={
                        "turn_id": assistant_turn_id,
                        "error_code": "INTERNAL_WORKFLOW_ERROR",
                        "detail": "An internal error occurred while processing the agent workflow.",
                    },
                )

        task = asyncio.create_task(_producer_runner())
        broker.register_generation_task(
            thread_id=thread_id,
            turn_id=assistant_turn_id,
            task=task,
            abort_event=abort_event,
        )

    async def _client_reader_loop() -> None:
        """Read and dispatch incoming client WebSocket commands concurrently while streaming."""
        while True:
            raw_text = await websocket.receive_text()
            try:
                parsed = json.loads(raw_text)
                if not isinstance(parsed, dict):
                    raise ValueError("WebSocket frame must be a JSON object.")
            except Exception:
                err_ev = broker.publish(
                    thread_id=thread_id,
                    session_id=session_id,
                    event_name="error",
                    payload={
                        "turn_id": None,
                        "error_code": "INVALID_JSON_FRAME",
                        "detail": "Incoming WebSocket frame must be a valid JSON object.",
                    },
                )
                _ = err_ev
                continue

            event_type = parsed.get("event")
            if event_type == "ping":
                try:
                    _ = ClientPingFrameSchema.model_validate(parsed)
                except Exception:
                    pass
                now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                pong_frame = {
                    "event": "pong",
                    "thread_id": thread_id,
                    "session_id": session_id,
                    "sequence_id": broker.get_latest_sequence_id(thread_id),
                    "timestamp": now_iso,
                }
                await _send_validated_frame(pong_frame)

            elif event_type == "interrupt":
                try:
                    interrupt_cmd = ClientInterruptFrameSchema.model_validate(parsed)
                except Exception:
                    interrupt_cmd = ClientInterruptFrameSchema()
                # Idempotent no-op if no active generation is running
                await broker.abort_active_generation(
                    thread_id=thread_id,
                    reason="client_interrupt",
                    turn_id=interrupt_cmd.turn_id,
                )

            elif event_type == "rehydrate":
                try:
                    _ = ClientRehydrateFrameSchema.model_validate(parsed)
                except Exception:
                    pass
                await _send_rehydration_snapshot()

            elif event_type == "user_message":
                try:
                    user_cmd = ClientUserMessageFrameSchema.model_validate(parsed)
                except Exception:
                    broker.publish(
                        thread_id=thread_id,
                        session_id=session_id,
                        event_name="error",
                        payload={
                            "turn_id": parsed.get("turn_id"),
                            "error_code": "INVALID_USER_MESSAGE",
                            "detail": "Query must be a non-empty string between 1 and 1000 characters.",
                        },
                    )
                    continue
                await _launch_generation_turn(user_cmd)

            elif event_type == "authenticate":
                # Already authenticated; re-emit rehydration snapshot idempotently
                await _send_rehydration_snapshot()

            else:
                broker.publish(
                    thread_id=thread_id,
                    session_id=session_id,
                    event_name="error",
                    payload={
                        "turn_id": None,
                        "error_code": "UNSUPPORTED_EVENT",
                        "detail": f"Unsupported client WebSocket event type: '{event_type}'.",
                    },
                )

    writer_task: Optional[asyncio.Task[None]] = None
    try:
        await _send_rehydration_snapshot()
        writer_task = asyncio.create_task(_broker_subscriber_writer_loop())
        await _client_reader_loop()
    except WebSocketDisconnect:
        pass
    except Exception:
        logger.debug("WebSocket session terminated for thread_id=%s", thread_id)
    finally:
        if writer_task is not None and not writer_task.done():
            writer_task.cancel()
            try:
                await writer_task
            except (asyncio.CancelledError, Exception):
                pass
        remaining_subscribers = broker.unsubscribe(thread_id, subscriber_queue)
        if remaining_subscribers == 0 and broker.is_generating(thread_id):
            await broker.abort_active_generation(
                thread_id=thread_id,
                reason="client_disconnect",
            )


# ---------------------------------------------------------------------------
# Human-In-The-Loop (HITL) Action Review Endpoints (FR-004, FR-007)
# ---------------------------------------------------------------------------

@router.get(
    "/actions/review",
    response_model=List[HumanApprovalGateResponse],
    status_code=status.HTTP_200_OK,
    summary="List actions pending human-in-the-loop operational review",
)
async def list_pending_agent_action_reviews(
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    policy_service: Any = Depends(get_agent_action_policies_service),
) -> List[HumanApprovalGateResponse]:
    """Retrieve all high-impact or irreversible agent actions waiting for operational review."""
    if current_user.role not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Supervisor or administrator role required.",
        )
    pending = await run_in_threadpool(policy_service.list_pending_reviews, limit)
    return [
        HumanApprovalGateResponse(
            request_id=r.request_id,
            action_type=r.action_type,
            entity_id=r.entity_id,
            requested_by_session=r.requested_by_session,
            payload_snapshot=r.payload_snapshot,
            requested_amount_eur=r.requested_amount_eur,
            status=r.status,
            reviewer_id=r.reviewer_id,
            decision_notes=r.decision_notes,
            created_at=r.created_at.isoformat(),
            reviewed_at=r.reviewed_at.isoformat() if r.reviewed_at else None,
        )
        for r in pending
    ]


@router.post(
    "/actions/review",
    response_model=HumanApprovalGateResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit Human Supervisor Review Decision for HITL Gate (NIST Contract)",
)
async def submit_supervisor_action_review(
    review_req: HITLReviewDecisionRequestSchema = Body(...),
    current_user: User = Depends(get_current_user),
    policy_service: Any = Depends(get_agent_action_policies_service),
) -> HumanApprovalGateResponse:
    """Submit human supervisor review decision conforming to contracts/nist-governance-api.openapi.json."""
    if current_user.role not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Supervisor or administrator role required.",
        )
    reviewer = current_user.email or current_user.id
    try:
        updated = await run_in_threadpool(
            policy_service.review_pending_request,
            request_id=review_req.request_id,
            reviewer_id=reviewer,
            approved=(review_req.decision == "APPROVE"),
            decision_notes=review_req.decision_notes,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review request '{review_req.request_id}' not found.",
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )

    return HumanApprovalGateResponse(
        request_id=updated.request_id,
        action_type=updated.action_type,
        entity_id=updated.entity_id,
        requested_by_session=updated.requested_by_session,
        payload_snapshot=updated.payload_snapshot,
        requested_amount_eur=updated.requested_amount_eur,
        status=updated.status,
        reviewer_id=updated.reviewer_id,
        decision_notes=updated.decision_notes,
        created_at=updated.created_at.isoformat(),
        reviewed_at=updated.reviewed_at.isoformat() if updated.reviewed_at else None,
    )


@router.post(
    "/actions/review/{request_id}",
    response_model=HumanApprovalGateResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve or reject a queued agent action with reviewer notes",
)
async def review_agent_action(
    request_id: str,
    decision_req: HumanApprovalDecisionRequest = Body(...),
    current_user: User = Depends(get_current_user),
    policy_service: Any = Depends(get_agent_action_policies_service),
) -> HumanApprovalGateResponse:
    """Submit human supervisor decision on a queued agent action."""
    if current_user.role not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions. Supervisor or administrator role required.",
        )
    reviewer_id = current_user.email or current_user.id
    try:
        updated = await run_in_threadpool(
            policy_service.review_pending_request,
            request_id=request_id,
            reviewer_id=reviewer_id,
            approved=bool(decision_req.approved),
            decision_notes=decision_req.decision_notes,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review request '{request_id}' not found.",
        )

    return HumanApprovalGateResponse(
        request_id=updated.request_id,
        action_type=updated.action_type,
        entity_id=updated.entity_id,
        requested_by_session=updated.requested_by_session,
        payload_snapshot=updated.payload_snapshot,
        requested_amount_eur=updated.requested_amount_eur,
        status=updated.status,
        reviewer_id=updated.reviewer_id,
        decision_notes=updated.decision_notes,
        created_at=updated.created_at.isoformat(),
        reviewed_at=updated.reviewed_at.isoformat() if updated.reviewed_at else None,
    )


