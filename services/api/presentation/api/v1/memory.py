"""FastAPI presentation router for Agent Memory carrier profiles, proposals, and audit logs (T037).

Adheres strictly to Monorepo Constitution Principles II & IV:
- Explicit Pydantic `response_model` on all endpoints
- Dependency injection via FastAPI `Depends`
- Non-blocking asynchronous execution via `run_in_threadpool`
- Sanitized error responses preventing raw stack trace exposure.
"""

import logging
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from domain.agent.exceptions import (
    MemoryGuardrailViolationError,
    MemoryNotFoundError,
)
from presentation.dependencies import get_agent_memory_service_dep
from presentation.schemas.agent import (
    ConsolidatedCarrierProfileResponseSchema,
    MemoryAuditLogEntrySchema,
    MemoryProposalFeedbackRequestSchema,
    MemoryProposalFeedbackResponseSchema,
    MemoryProposalResponseSchema,
    MemoryProposalSchema,
    SanitizedErrorResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Agent Memory"])


@router.get(
    "/proposals/pending",
    response_model=MemoryProposalResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Retrieve active pending memory proposal for a session/thread",
)
async def get_pending_memory_proposal(
    thread_id: str,
    memory_service: Any = Depends(get_agent_memory_service_dep),
) -> MemoryProposalResponseSchema:
    """Return active pending proposal for `thread_id`, or null if none pending."""
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
    summary="Submit explicit out-of-band feedback on an active memory proposal",
    responses={
        400: {"model": SanitizedErrorResponse, "description": "Guardrail violation"},
        404: {"model": SanitizedErrorResponse, "description": "Proposal not found"},
    },
)
async def submit_memory_proposal_feedback(
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
    "/carriers/{carrier}",
    response_model=ConsolidatedCarrierProfileResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Retrieve consolidated carrier operational profile by query parameter",
    responses={
        404: {"model": SanitizedErrorResponse, "description": "No active memories found for carrier"},
    },
)
async def get_carrier_profile_query(
    carrier: str,
    country_code: str = Query(default="ES", description="Country ISO code (ES, US)"),
    memory_service: Any = Depends(get_agent_memory_service_dep),
) -> ConsolidatedCarrierProfileResponseSchema | JSONResponse:
    """Retrieve consolidated operational rules for `(carrier, country_code)`."""
    profile = await run_in_threadpool(
        memory_service.get_consolidated_carrier_profile,
        carrier,
        country_code,
    )
    if profile is None:
        err = SanitizedErrorResponse(
            detail=f"No active operational memories found for carrier '{carrier}' in '{country_code}'.",
            error_code="CARRIER_PROFILE_NOT_FOUND",
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=err.model_dump(),
        )
    return ConsolidatedCarrierProfileResponseSchema(
        carrier=profile.carrier,
        country_code=profile.country_code,
        active_rules=list(profile.active_rules),
        memory_ids=list(profile.memory_ids),
        last_verified_at=profile.last_verified_at.isoformat(),
    )


@router.get(
    "/carriers/{carrier}/{country_code}",
    response_model=ConsolidatedCarrierProfileResponseSchema,
    status_code=status.HTTP_200_OK,
    summary="Retrieve consolidated carrier operational profile by path parameter (T037)",
    responses={
        404: {"model": SanitizedErrorResponse, "description": "No active memories found for carrier"},
    },
)
async def get_carrier_profile_path(
    carrier: str,
    country_code: str,
    memory_service: Any = Depends(get_agent_memory_service_dep),
) -> ConsolidatedCarrierProfileResponseSchema | JSONResponse:
    """Retrieve consolidated operational rules for `(carrier, country_code)`."""
    profile = await run_in_threadpool(
        memory_service.get_consolidated_carrier_profile,
        carrier,
        country_code,
    )
    if profile is None:
        err = SanitizedErrorResponse(
            detail=f"No active operational memories found for carrier '{carrier}' in '{country_code}'.",
            error_code="CARRIER_PROFILE_NOT_FOUND",
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=err.model_dump(),
        )
    return ConsolidatedCarrierProfileResponseSchema(
        carrier=profile.carrier,
        country_code=profile.country_code,
        active_rules=list(profile.active_rules),
        memory_ids=list(profile.memory_ids),
        last_verified_at=profile.last_verified_at.isoformat(),
    )


@router.get(
    "/audit-logs",
    response_model=List[MemoryAuditLogEntrySchema],
    status_code=status.HTTP_200_OK,
    summary="Query immutable memory lifecycle audit log entries (T037)",
)
async def list_memory_audit_logs(
    limit: int = Query(default=50, ge=1, le=100),
    event_type: Optional[str] = Query(default=None),
    proposal_id: Optional[str] = Query(default=None),
    memory_service: Any = Depends(get_agent_memory_service_dep),
) -> List[MemoryAuditLogEntrySchema]:
    """Return immutable audit log entries ordered newest first."""
    entries = await run_in_threadpool(
        memory_service.list_audit_logs,
        proposal_id,
        event_type,
        limit,
    )
    return [
        MemoryAuditLogEntrySchema(
            log_id=e.log_id,
            proposal_id=e.proposal_id,
            memory_id=e.memory_id,
            event_type=e.event_type,
            classified_intent=e.classified_intent,
            user_message=e.user_message,
            resulting_action=e.resulting_action,
            session_id=e.session_id,
            timestamp=e.timestamp.isoformat(),
            details=dict(e.details or {}),
        )
        for e in entries
    ]
