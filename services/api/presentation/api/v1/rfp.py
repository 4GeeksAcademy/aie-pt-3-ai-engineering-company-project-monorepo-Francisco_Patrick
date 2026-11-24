"""FastAPI presentation router for RFP Intake & Analysis endpoints.

Conforms strictly to OpenAPI specification in `specs/031-rfp-intake/contracts/rfp-intake-api.yaml`.
"""

import asyncio
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import AsyncGenerator, List, Optional
from uuid import UUID, uuid5, uuid4, NAMESPACE_OID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from data.pipelines.rfp_intake import run_rfp_pipeline_background
from data.pipelines.rfp_intake.rfp_approval_service import (
    BranchNotInterruptedError,
    ResumeValidationError,
    RFPApprovalService,
)
from data.pipelines.rfp_intake.rfp_response_service import (
    RFPResponseGenerationService,
    run_rfp_response_generation_background,
)
from domain.models import User
from domain.rfp.entities import (
    DepartmentSection,
    IntakeTicket,
    ReadabilityScores,
    RFPMetadata,
    RFPTicketCreatedEvent,
    TicketStatus,
)
from domain.rfp.ports import IntakeTicketRepositoryPort, RFPNotificationBroadcasterPort
from infrastructure.persistence.sqlmodel.rfp_repository import SQLModelIntakeTicketRepository
from presentation.dependencies import (
    get_current_user,
    get_rfp_notification_broadcaster_dep,
    get_sqlmodel_session_dep,
)
from presentation.schemas.rfp import (
    ArbitrationLogListResponse,
    ArbitrationLogResponse,
    ComplianceEvaluationSchema,
    CreateRFPTicketRequest,
    DepartmentSectionResponse,
    ErrorResponse,
    EvaluationResultSchema,
    FinalDocumentResponse,
    IntakeHandoffPayloadResponse,
    IntakeTicketAcceptedResponse,
    IntakeTicketDetailResponse,
    IntakeTicketListResponse,
    IntakeTicketSummary,
    InternalContact,
    Part3DepartmentSectionBundleSchema,
    Part3HandoffPayloadResponse,
    ProposalGenerationAcceptedResponse,
    ReadabilityEvaluationSchema,
    ReadabilityScoresResponse,
    RelevanceEvaluationSchema,
    ResumeDecisionRequest,
    ResumeDecisionResponse,
    RFPMetadataResponse,
    RFPTicketCreatedEventSchema,
)

router = APIRouter(tags=["RFP Intake"])

# Resolve persistent raw directory in data/raw
_REPO_ROOT = Path(__file__).resolve().parents[5]
RAW_STORAGE_DIR = _REPO_ROOT / "data" / "raw"
RAW_STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def get_rfp_repository(
    session: Session = Depends(get_sqlmodel_session_dep),
) -> IntakeTicketRepositoryPort:
    """Dependency injection provider for RFP intake repository."""
    return SQLModelIntakeTicketRepository(session)


def _map_eval_dict_to_schema(eval_dict: dict) -> EvaluationResultSchema:
    """Convert serialized evaluation result dict into EvaluationResultSchema."""
    read_d = eval_dict.get("readability") or {}
    rel_d = eval_dict.get("relevance") or {}
    comp_d = eval_dict.get("compliance") or {}
    return EvaluationResultSchema(
        department_id=eval_dict["department_id"],
        iteration=int(eval_dict.get("iteration", 1)),
        readability=ReadabilityEvaluationSchema(
            pass_status=bool(read_d.get("pass_status", read_d.get("pass", False))),
            score=float(read_d.get("score", 0.0)),
            details=str(read_d.get("details", "")),
        ),
        relevance=RelevanceEvaluationSchema(
            pass_status=bool(rel_d.get("pass_status", rel_d.get("pass", False))),
            missing_aspects=list(rel_d.get("missing_aspects") or []),
        ),
        compliance=ComplianceEvaluationSchema(
            pass_status=bool(comp_d.get("pass_status", comp_d.get("pass", False))),
            rule_ids=list(comp_d.get("rule_ids") or []),
            violations=list(comp_d.get("violations") or []),
        ),
        overall_pass=bool(eval_dict.get("overall_pass", False)),
        feedback_for_generator=str(eval_dict.get("feedback_for_generator", "")),
        evaluated_at=eval_dict.get("evaluated_at") or datetime.now(timezone.utc),
    )


def _map_section_to_response(s: DepartmentSection) -> DepartmentSectionResponse:
    """Project DepartmentSection domain entity to DepartmentSectionResponse DTO."""
    eval_schemas = [_map_eval_dict_to_schema(ed) for ed in (s.evaluation_results or [])]
    latest_eval = eval_schemas[-1] if eval_schemas else None
    return DepartmentSectionResponse(
        id=s.id,
        ticket_id=s.ticket_id,
        department_id=s.department_id,
        department_name=s.department_name,
        responsible_person=s.responsible_person,
        key_aspects=s.key_aspects,
        open_questions=s.open_questions,
        policy_warnings=s.policy_warnings,
        status=s.status,
        iteration=s.iteration,
        draft_content=s.draft_content,
        latest_evaluation=latest_eval,
        evaluation_results=eval_schemas,
        approval_status=s.approval_status,
        approver=s.approver,
        review_feedback=s.review_feedback,
        approved_at=s.approved_at,
    )


@router.post(
    "/intake",
    response_model=IntakeTicketAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a PDF RFP document for asynchronous intake and analysis",
    responses={
        202: {"model": IntakeTicketAcceptedResponse},
        400: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def upload_rfp_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    repository: IntakeTicketRepositoryPort = Depends(get_rfp_repository),
) -> IntakeTicketAcceptedResponse:
    """Accept an uploaded PDF RFP, store to raw storage, initiate analysis, and return HTTP 202."""
    filename = file.filename or "uploaded.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type: only PDF documents (.pdf) are supported.",
        )

    # Read content to validate size
    content = await file.read()
    file_size = len(content)
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded PDF file is empty.",
        )

    MAX_SIZE = 25 * 1024 * 1024  # 25 MB
    if file_size > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file exceeds the maximum allowed limit of 25MB.",
        )

    ticket_id = uuid4()
    sanitized_filename = Path(filename).name
    save_filename = f"{ticket_id}_{sanitized_filename}"
    target_path = RAW_STORAGE_DIR / save_filename

    # Save to disk
    with open(target_path, "wb") as f:
        f.write(content)

    ticket = IntakeTicket.create(
        raw_pdf_path=str(target_path),
        raw_pdf_filename=sanitized_filename,
        file_size_bytes=file_size,
        ticket_id=ticket_id,
    )

    saved_ticket = repository.save_ticket(ticket)

    # Queue background analysis pipeline
    background_tasks.add_task(run_rfp_pipeline_background, saved_ticket.id, str(target_path))

    return IntakeTicketAcceptedResponse(
        ticket_id=saved_ticket.id,
        ticket_number=saved_ticket.ticket_number,
        status=saved_ticket.status.value,
        message="Proposal accepted for analysis. Processing in background.",
        created_at=saved_ticket.created_at,
    )


@router.post(
    "/tickets",
    response_model=RFPTicketCreatedEventSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new RFP ticket in analyzing status and broadcast rfp_ticket_created (No LLM)",
    responses={
        201: {"model": RFPTicketCreatedEventSchema},
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
def create_rfp_ticket_and_notify(
    payload: CreateRFPTicketRequest,
    _current_user: User = Depends(get_current_user),
    repository: IntakeTicketRepositoryPort = Depends(get_rfp_repository),
    broadcaster: RFPNotificationBroadcasterPort = Depends(
        get_rfp_notification_broadcaster_dep
    ),
) -> RFPTicketCreatedEventSchema:
    """Persist a new RFP ticket with initial status analyzing and emit rfp_ticket_created via SSE.

    Operates strictly in the persistence and real-time notification layers with zero LLM calls.
    """
    now = datetime.now(timezone.utc)
    created_at_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    raw_ticket_id = (payload.ticket_id or "").strip()
    if raw_ticket_id:
        try:
            internal_uuid = UUID(raw_ticket_id)
        except ValueError:
            internal_uuid = uuid5(NAMESPACE_OID, f"rfp_ticket:{raw_ticket_id}")
        canonical_ticket_id = raw_ticket_id
    else:
        internal_uuid = uuid4()
        canonical_ticket_id = f"tkt_{str(internal_uuid.int)[:4]}"

    canonical_rfp_id = (payload.rfp_id or "").strip() or f"rfp_{str(internal_uuid.int)[4:8]}"

    # Store canonical display identifiers inside ticket_number / raw_pdf_path so GET /tickets can round-trip them
    ticket = IntakeTicket(
        id=internal_uuid,
        ticket_number=canonical_rfp_id,
        status=TicketStatus.ANALIZANDO,
        raw_pdf_path=f"sse://{canonical_ticket_id}",
        raw_pdf_filename=f"{canonical_rfp_id}.pdf",
        file_size_bytes=0,
        created_at=now,
        updated_at=now,
    )
    repository.save_ticket(ticket)

    currency = "USD" if payload.client_country == "US" else "EUR"
    metadata = RFPMetadata(
        id=uuid4(),
        ticket_id=internal_uuid,
        client_name=payload.client_name,
        client_country=payload.client_country,
        currency=currency,
        services_requested=list(payload.services_requested),
        monthly_volume=payload.monthly_volume,
        deadline=payload.deadline,
        budget_range=payload.budget_range,
        departments_needed=list(payload.services_requested),
        unsupported_services=[],
        readability_scores=ReadabilityScores(
            flesch_reading_ease=65.0,
            flesch_kincaid_grade=8.0,
            reading_level_label="Standard",
            word_count=0,
            sentence_count=0,
        ),
        created_at=now,
    )
    repository.save_metadata(metadata)

    event = RFPTicketCreatedEvent(
        ticket_id=canonical_ticket_id,
        rfp_id=canonical_rfp_id,
        client_name=payload.client_name,
        client_country=payload.client_country,
        services_requested=list(payload.services_requested),
        status="analyzing",
        created_at=created_at_iso,
    )
    broadcaster.publish_ticket_created(event)

    return RFPTicketCreatedEventSchema(
        ticket_id=event.ticket_id,
        rfp_id=event.rfp_id,
        client_name=event.client_name,
        client_country=event.client_country,
        services_requested=list(payload.services_requested),
        status="analyzing",
        created_at=event.created_at,
    )


async def _rfp_sse_event_generator(
    request: Request,
    broadcaster: RFPNotificationBroadcasterPort,
    last_event_id: Optional[str],
    heartbeat_interval: float,
    max_events: Optional[int],
) -> AsyncGenerator[str, None]:
    """Yield W3C Server-Sent Events frames (missed-event replay, live events, and `: keep-alive` comments)."""
    queue = broadcaster.subscribe()
    yielded_count = 0
    try:
        missed_envelopes = broadcaster.get_missed_events(last_event_id)
        for envelope in missed_envelopes:
            yield envelope.to_sse_frame()
            yielded_count += 1
            if max_events is not None and yielded_count >= max_events:
                return

        while True:
            if await request.is_disconnected():
                break
            try:
                envelope = await asyncio.wait_for(
                    queue.get(), timeout=heartbeat_interval
                )
                yield envelope.to_sse_frame()
                yielded_count += 1
            except asyncio.TimeoutError:
                yield broadcaster.format_keep_alive()
                yielded_count += 1

            if max_events is not None and yielded_count >= max_events:
                break
    finally:
        broadcaster.unsubscribe(queue)


@router.get(
    "/notifications/stream",
    summary="Subscribe to Real-Time RFP Ticket Notifications (SSE)",
    responses={
        200: {
            "description": "Active Server-Sent Events stream (text/event-stream)",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        },
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
@router.get(
    "/events",
    summary="Compatibility Alias for Real-Time RFP Ticket Notifications (SSE)",
    responses={
        200: {
            "description": "Active Server-Sent Events stream (text/event-stream)",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        },
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
    },
)
async def stream_rfp_notifications(
    request: Request,
    _current_user: User = Depends(get_current_user),
    broadcaster: RFPNotificationBroadcasterPort = Depends(
        get_rfp_notification_broadcaster_dep
    ),
    last_event_id_header: Optional[str] = Header(default=None, alias="Last-Event-ID"),
    last_event_id_query: Optional[str] = Query(default=None, alias="last_event_id"),
    heartbeat_interval: float = Query(default=15.0, ge=0.05, le=60.0),
    max_events: Optional[int] = Query(default=None, ge=1),
) -> StreamingResponse:
    """Establish an authenticated Server-Sent Events (`text/event-stream`) connection for RFP ticket arrivals."""
    effective_last_event_id = last_event_id_header or last_event_id_query
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(
        _rfp_sse_event_generator(
            request=request,
            broadcaster=broadcaster,
            last_event_id=effective_last_event_id,
            heartbeat_interval=heartbeat_interval,
            max_events=max_events,
        ),
        media_type="text/event-stream",
        headers=headers,
    )


@router.get(
    "/tickets",
    response_model=IntakeTicketListResponse,
    status_code=status.HTTP_200_OK,
    summary="List recent RFP intake tickets",
)
def list_rfp_tickets(
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    repository: IntakeTicketRepositoryPort = Depends(get_rfp_repository),
) -> IntakeTicketListResponse:
    """Retrieve paginated list of recent intake tickets."""
    st = None
    if status_filter:
        normalized_filter = (
            TicketStatus.ANALIZANDO.value
            if status_filter == "analyzing"
            else status_filter
        )
        try:
            st = TicketStatus(normalized_filter)
        except ValueError:
            pass

    tickets = repository.list_tickets(limit=limit, status=st)
    total = repository.count_tickets(status=st)

    items = []
    for t in tickets:
        meta = repository.get_metadata(t.id)
        display_ticket_id: UUID | str = t.id
        if t.raw_pdf_path and t.raw_pdf_path.startswith("sse://"):
            display_ticket_id = t.raw_pdf_path.removeprefix("sse://")
        items.append(
            IntakeTicketSummary(
                ticket_id=display_ticket_id,
                ticket_number=t.ticket_number,
                status=t.status.value,
                raw_pdf_filename=t.raw_pdf_filename,
                client_name=meta.client_name if meta else None,
                rejection_reason=t.rejection_reason,
                created_at=t.created_at,
                updated_at=t.updated_at,
                rfp_id=t.ticket_number,
                client_country=meta.client_country if meta else None,
                services_requested=list(meta.services_requested) if meta else [],
            )
        )

    return IntakeTicketListResponse(items=items, total=total)


@router.get(
    "/tickets/{ticket_id}",
    response_model=IntakeTicketDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get details, status, and analysis outputs for an intake ticket",
    responses={
        200: {"model": IntakeTicketDetailResponse},
        404: {"model": ErrorResponse},
    },
)
def get_rfp_ticket_by_id(
    ticket_id: UUID,
    repository: IntakeTicketRepositoryPort = Depends(get_rfp_repository),
) -> IntakeTicketDetailResponse:
    """Retrieve full details of an intake ticket including metadata, workers, and handoff."""
    ticket = repository.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Intake ticket '{ticket_id}' not found.",
        )

    meta_entity = repository.get_metadata(ticket.id)
    meta_response = None
    if meta_entity:
        meta_response = RFPMetadataResponse(
            client_name=meta_entity.client_name,
            client_country=meta_entity.client_country,
            currency=meta_entity.currency,
            services_requested=meta_entity.services_requested,
            monthly_volume=meta_entity.monthly_volume,
            deadline=meta_entity.deadline,
            budget_range=meta_entity.budget_range,
            departments_needed=list(meta_entity.departments_needed),
            unsupported_services=meta_entity.unsupported_services,
            readability_scores=ReadabilityScoresResponse(
                flesch_reading_ease=meta_entity.readability_scores.flesch_reading_ease,
                flesch_kincaid_grade=meta_entity.readability_scores.flesch_kincaid_grade,
                reading_level_label=meta_entity.readability_scores.reading_level_label,
                word_count=meta_entity.readability_scores.word_count,
                sentence_count=meta_entity.readability_scores.sentence_count,
            ),
        )

    sections_entities = repository.list_department_sections(ticket.id)
    sections_response = [_map_section_to_response(s) for s in sections_entities]

    handoff_entity = repository.get_handoff_payload(ticket.id)
    handoff_response = None
    if handoff_entity:
        handoff_response = IntakeHandoffPayloadResponse(
            ticket_id=handoff_entity.ticket_id,
            schema_version=handoff_entity.schema_version,
            executive_summary=handoff_entity.executive_summary,
            flagged_contradictions=handoff_entity.flagged_contradictions,
            key_questions_for_prospect=handoff_entity.key_questions_for_prospect,
            internal_contacts=[
                InternalContact(name=c.name, role=c.role, department=c.department)
                for c in handoff_entity.internal_contacts
            ],
            full_handoff_json=handoff_entity.full_handoff_json,
            created_at=handoff_entity.created_at,
        )

    arb_logs_entities = repository.list_arbitration_logs(ticket.id)
    arb_logs_response = [
        ArbitrationLogResponse(
            id=log.id,
            ticket_id=log.ticket_id,
            trigger_id=log.trigger_id,
            arbiter=log.arbiter,
            rule_applied=log.rule_applied,
            resolution_details=log.resolution_details,
            created_at=log.created_at,
        )
        for log in arb_logs_entities
    ]

    final_doc_entity = repository.get_final_document(ticket.id)
    final_doc_response = None
    if final_doc_entity:
        final_doc_response = FinalDocumentResponse(
            id=final_doc_entity.id,
            ticket_id=final_doc_entity.ticket_id,
            title=final_doc_entity.title,
            client_name=final_doc_entity.client_name,
            currency=final_doc_entity.currency,
            executive_summary=final_doc_entity.executive_summary,
            sections=final_doc_entity.sections,
            generated_at=final_doc_entity.generated_at,
        )

    return IntakeTicketDetailResponse(
        ticket_id=ticket.id,
        ticket_number=ticket.ticket_number,
        status=ticket.status.value,
        raw_pdf_filename=ticket.raw_pdf_filename,
        file_size_bytes=ticket.file_size_bytes,
        rejection_reason=ticket.rejection_reason,
        error_message=ticket.error_message,
        metadata=meta_response,
        department_sections=sections_response,
        handoff=handoff_response,
        arbitration_logs=arb_logs_response,
        final_document=final_doc_response,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


@router.get(
    "/tickets/{ticket_id}/handoff",
    response_model=IntakeHandoffPayloadResponse,
    status_code=status.HTTP_200_OK,
    summary="Get canonical Part 2 handoff payload for a completed intake ticket",
    responses={
        200: {"model": IntakeHandoffPayloadResponse},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def get_rfp_handoff_payload(
    ticket_id: UUID,
    repository: IntakeTicketRepositoryPort = Depends(get_rfp_repository),
) -> IntakeHandoffPayloadResponse:
    """Retrieve the canonical Part 2 handoff payload for a completed ticket."""
    ticket = repository.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' not found.",
        )

    if ticket.status != TicketStatus.ANALISIS_COMPLETO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ticket analysis is not yet completed or was discarded.",
        )

    handoff_entity = repository.get_handoff_payload(ticket.id)
    if not handoff_entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Handoff payload not found for this completed ticket.",
        )

    return IntakeHandoffPayloadResponse(
        ticket_id=handoff_entity.ticket_id,
        schema_version=handoff_entity.schema_version,
        executive_summary=handoff_entity.executive_summary,
        flagged_contradictions=handoff_entity.flagged_contradictions,
        key_questions_for_prospect=handoff_entity.key_questions_for_prospect,
        internal_contacts=[
            InternalContact(name=c.name, role=c.role, department=c.department)
            for c in handoff_entity.internal_contacts
        ],
        full_handoff_json=handoff_entity.full_handoff_json,
        created_at=handoff_entity.created_at,
    )


@router.post(
    "/{ticket_id}/generate-proposal",
    response_model=ProposalGenerationAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Proposal Draft Generation & Evaluation",
    responses={
        202: {"model": ProposalGenerationAcceptedResponse},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def generate_rfp_proposal(
    ticket_id: UUID,
    background_tasks: BackgroundTasks,
    repository: IntakeTicketRepositoryPort = Depends(get_rfp_repository),
) -> ProposalGenerationAcceptedResponse:
    """Initiate asynchronous department proposal generator agents and parallel evaluation loop."""
    service = RFPResponseGenerationService(repository)
    try:
        updated_ticket, active_departments = service.initiate_proposal_generation(ticket_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    background_tasks.add_task(run_rfp_response_generation_background, updated_ticket.id)

    return ProposalGenerationAcceptedResponse(
        ticket_id=updated_ticket.id,
        status=updated_ticket.status.value,
        message="Proposal draft generation pipeline initiated.",
        active_departments=active_departments,
    )


@router.get(
    "/{ticket_id}/sections",
    response_model=List[DepartmentSectionResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Department Proposal Sections & Status",
    responses={
        200: {"model": List[DepartmentSectionResponse]},
        404: {"model": ErrorResponse},
    },
)
def list_rfp_department_sections(
    ticket_id: UUID,
    repository: IntakeTicketRepositoryPort = Depends(get_rfp_repository),
) -> List[DepartmentSectionResponse]:
    """Return generated draft text, evaluation status, and iteration count for all active departments."""
    ticket = repository.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' not found.",
        )

    sections = repository.list_department_sections(ticket_id)
    return [_map_section_to_response(s) for s in sections]


@router.get(
    "/{ticket_id}/part3-handoff",
    response_model=Part3HandoffPayloadResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Part 3 Proposal Handoff Payload",
    responses={
        200: {"model": Part3HandoffPayloadResponse},
        404: {"model": ErrorResponse},
    },
)
def get_rfp_part3_handoff(
    ticket_id: UUID,
    repository: IntakeTicketRepositoryPort = Depends(get_rfp_repository),
) -> Part3HandoffPayloadResponse:
    """Return the compiled Part 3 proposal package including all department drafts and evaluations."""
    ticket = repository.get_ticket(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' not found.",
        )

    part3_entity = repository.get_part3_handoff_payload(ticket_id)
    if not part3_entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Part 3 handoff payload not found for ticket '{ticket_id}'.",
        )

    bundles: dict[str, Part3DepartmentSectionBundleSchema] = {}
    for dept_id, bundle_dict in (part3_entity.department_sections or {}).items():
        eval_dict = bundle_dict.get("evaluation_result") or {}
        bundles[dept_id] = Part3DepartmentSectionBundleSchema(
            draft_content=str(bundle_dict.get("draft_content", "")),
            status=bundle_dict.get("status", "needs_human_review"),
            iteration=int(bundle_dict.get("iteration", 1)),
            evaluation_result=_map_eval_dict_to_schema(eval_dict),
        )

    return Part3HandoffPayloadResponse(
        ticket_id=part3_entity.ticket_id,
        schema_version=part3_entity.schema_version,
        overall_status=part3_entity.overall_status,
        rfp_metadata=part3_entity.rfp_metadata,
        department_sections=bundles,
        emitted_at=part3_entity.emitted_at,
    )


def get_rfp_approval_service(
    repository: IntakeTicketRepositoryPort = Depends(get_rfp_repository),
) -> RFPApprovalService:
    """Dependency injection provider for Part 3 RFP Approval & Arbitration service."""
    return RFPApprovalService(repository=repository)


@router.post(
    "/tickets/{ticket_id}/resume-approval",
    response_model=ResumeDecisionResponse,
    status_code=status.HTTP_200_OK,
    summary="Resume an interrupted department approval branch",
    responses={
        200: {"model": ResumeDecisionResponse},
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
def resume_department_approval(
    ticket_id: UUID,
    payload: ResumeDecisionRequest,
    approval_service: RFPApprovalService = Depends(get_rfp_approval_service),
) -> ResumeDecisionResponse:
    """Validate human reviewer decision and resume the paused department approval branch."""
    try:
        result = approval_service.resume_department_approval(
            ticket_id=ticket_id,
            department_id=payload.department_id,
            decision=payload.decision,
            approver=payload.approver,
            feedback=payload.feedback,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ResumeValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except BranchNotInterruptedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    approved_at_raw = result.get("approved_at")
    approved_at_dt: Optional[datetime] = None
    if isinstance(approved_at_raw, str):
        approved_at_dt = datetime.fromisoformat(approved_at_raw)
    elif isinstance(approved_at_raw, datetime):
        approved_at_dt = approved_at_raw

    return ResumeDecisionResponse(
        ticket_id=UUID(str(result["ticket_id"])),
        department_id=result["department_id"],
        approval_status=result["approval_status"],
        ticket_status=result["ticket_status"],
        message=result["message"],
        approved_at=approved_at_dt,
    )


@router.get(
    "/tickets/{ticket_id}/arbitration-logs",
    response_model=ArbitrationLogListResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve all deterministic arbitration records for a ticket",
    responses={
        200: {"model": ArbitrationLogListResponse},
        404: {"model": ErrorResponse},
    },
)
def get_ticket_arbitration_logs(
    ticket_id: UUID,
    approval_service: RFPApprovalService = Depends(get_rfp_approval_service),
) -> ArbitrationLogListResponse:
    """Retrieve all deterministic conflict arbitration audit log entries for a ticket."""
    try:
        logs = approval_service.list_arbitration_logs(ticket_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    items = [
        ArbitrationLogResponse(
            id=log.id,
            ticket_id=log.ticket_id,
            trigger_id=log.trigger_id,
            arbiter=log.arbiter,
            rule_applied=log.rule_applied,
            resolution_details=log.resolution_details,
            created_at=log.created_at,
        )
        for log in logs
    ]
    return ArbitrationLogListResponse(items=items, total=len(items))


@router.get(
    "/tickets/{ticket_id}/final-document",
    response_model=FinalDocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve the finalized, synthesized commercial proposal document",
    responses={
        200: {"model": FinalDocumentResponse},
        404: {"model": ErrorResponse},
    },
)
def get_final_proposal_document(
    ticket_id: UUID,
    approval_service: RFPApprovalService = Depends(get_rfp_approval_service),
) -> FinalDocumentResponse:
    """Retrieve the consolidated final proposal document once 100% of active departments have approved."""
    try:
        doc = approval_service.get_final_document(ticket_id)
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return FinalDocumentResponse(
        id=doc.id,
        ticket_id=doc.ticket_id,
        title=doc.title,
        client_name=doc.client_name,
        currency=doc.currency,
        executive_summary=doc.executive_summary,
        sections=doc.sections,
        generated_at=doc.generated_at,
    )
