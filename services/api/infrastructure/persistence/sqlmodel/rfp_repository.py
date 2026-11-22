"""SQLModel implementation of IntakeTicketRepositoryPort."""

from dataclasses import asdict
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from sqlmodel import Session, select

from domain.rfp.entities import (
    ArbitrationLog,
    DepartmentSection,
    EvaluationResult,
    FinalDocument,
    IntakeHandoffPayload,
    IntakeTicket,
    InternalContact,
    Part3HandoffPayload,
    ReadabilityScores,
    RFPMetadata,
    TicketStatus,
)
from domain.rfp.ports import IntakeTicketRepositoryPort
from infrastructure.persistence.sqlmodel.models import (
    ArbitrationLogTable,
    DepartmentSectionTable,
    FinalDocumentTable,
    IntakeHandoffPayloadTable,
    IntakeTicketTable,
    Part3HandoffPayloadTable,
    RFPMetadataTable,
)


class SQLModelIntakeTicketRepository(IntakeTicketRepositoryPort):
    """Adapter persisting RFP intake and Part 2 proposal generation entities via SQLModel."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with active database session."""
        self.session = session

    # ---------------------------------------------------------
    # Ticket Operations
    # ---------------------------------------------------------

    def save_ticket(self, ticket: IntakeTicket) -> IntakeTicket:
        """Persist or update an intake ticket."""
        db_record = self.session.get(IntakeTicketTable, ticket.id)
        if db_record is None:
            db_record = IntakeTicketTable(
                id=ticket.id,
                ticket_number=ticket.ticket_number,
                status=(
                    ticket.status.value
                    if isinstance(ticket.status, TicketStatus)
                    else str(ticket.status)
                ),
                raw_pdf_path=ticket.raw_pdf_path,
                raw_pdf_filename=ticket.raw_pdf_filename,
                file_size_bytes=ticket.file_size_bytes,
                rejection_reason=ticket.rejection_reason,
                error_message=ticket.error_message,
                created_at=ticket.created_at,
                updated_at=ticket.updated_at,
            )
            self.session.add(db_record)
        else:
            db_record.status = (
                ticket.status.value
                if isinstance(ticket.status, TicketStatus)
                else str(ticket.status)
            )
            db_record.rejection_reason = ticket.rejection_reason
            db_record.error_message = ticket.error_message
            db_record.updated_at = ticket.updated_at
            self.session.add(db_record)

        self.session.commit()
        self.session.refresh(db_record)
        return self._to_domain_ticket(db_record)

    def get_ticket(self, ticket_id: UUID) -> Optional[IntakeTicket]:
        """Retrieve an intake ticket by UUID."""
        record = self.session.get(IntakeTicketTable, ticket_id)
        if record is None:
            return None
        return self._to_domain_ticket(record)

    def get_ticket_by_number(self, ticket_number: str) -> Optional[IntakeTicket]:
        """Retrieve an intake ticket by human-readable reference code."""
        statement = select(IntakeTicketTable).where(
            IntakeTicketTable.ticket_number == ticket_number
        )
        record = self.session.exec(statement).first()
        if record is None:
            return None
        return self._to_domain_ticket(record)

    def list_tickets(
        self, limit: int = 20, status: Optional[TicketStatus] = None
    ) -> List[IntakeTicket]:
        """List recent intake tickets optionally filtered by status."""
        statement = select(IntakeTicketTable)
        if status is not None:
            status_val = status.value if isinstance(status, TicketStatus) else str(status)
            statement = statement.where(IntakeTicketTable.status == status_val)
        statement = statement.order_by(IntakeTicketTable.created_at.desc()).limit(limit)
        records = self.session.exec(statement).all()
        return [self._to_domain_ticket(r) for r in records]

    def count_tickets(self, status: Optional[TicketStatus] = None) -> int:
        """Count total intake tickets optionally filtered by status."""
        statement = select(IntakeTicketTable)
        if status is not None:
            status_val = status.value if isinstance(status, TicketStatus) else str(status)
            statement = statement.where(IntakeTicketTable.status == status_val)
        return len(self.session.exec(statement).all())

    # ---------------------------------------------------------
    # Metadata Operations
    # ---------------------------------------------------------

    def save_metadata(self, metadata: RFPMetadata) -> RFPMetadata:
        """Persist or update extracted commercial metadata for a ticket."""
        db_record = self.session.get(RFPMetadataTable, metadata.id)
        if db_record is None:
            stmt = select(RFPMetadataTable).where(
                RFPMetadataTable.ticket_id == metadata.ticket_id
            )
            db_record = self.session.exec(stmt).first()
        scores_dict = asdict(metadata.readability_scores)
        if db_record is None:
            db_record = RFPMetadataTable(
                id=metadata.id,
                ticket_id=metadata.ticket_id,
                client_name=metadata.client_name,
                client_country=metadata.client_country,
                currency=metadata.currency,
                services_requested=list(metadata.services_requested),
                monthly_volume=metadata.monthly_volume,
                deadline=metadata.deadline,
                budget_range=metadata.budget_range,
                departments_needed=list(metadata.departments_needed),
                unsupported_services=list(metadata.unsupported_services),
                readability_scores=scores_dict,
                created_at=metadata.created_at,
            )
            self.session.add(db_record)
        else:
            db_record.client_name = metadata.client_name
            db_record.client_country = metadata.client_country
            db_record.currency = metadata.currency
            db_record.services_requested = list(metadata.services_requested)
            db_record.monthly_volume = metadata.monthly_volume
            db_record.deadline = metadata.deadline
            db_record.budget_range = metadata.budget_range
            db_record.departments_needed = list(metadata.departments_needed)
            db_record.unsupported_services = list(metadata.unsupported_services)
            db_record.readability_scores = scores_dict
            self.session.add(db_record)

        self.session.commit()
        self.session.refresh(db_record)
        return self._to_domain_metadata(db_record)

    def get_metadata(self, ticket_id: UUID) -> Optional[RFPMetadata]:
        """Retrieve extracted commercial metadata for a ticket."""
        statement = select(RFPMetadataTable).where(RFPMetadataTable.ticket_id == ticket_id)
        record = self.session.exec(statement).first()
        if record is None:
            return None
        return self._to_domain_metadata(record)

    # ---------------------------------------------------------
    # Department Section Operations
    # ---------------------------------------------------------

    def save_department_section(self, section: DepartmentSection) -> DepartmentSection:
        """Persist or update a department analysis section."""
        statement = select(DepartmentSectionTable).where(
            DepartmentSectionTable.ticket_id == section.ticket_id,
            DepartmentSectionTable.department_id == section.department_id,
        )
        db_record = self.session.exec(statement).first()
        now = datetime.now(timezone.utc)
        if db_record is None:
            db_record = DepartmentSectionTable(
                id=section.id,
                ticket_id=section.ticket_id,
                department_id=section.department_id,
                department_name=section.department_name,
                responsible_person=section.responsible_person,
                key_aspects=section.key_aspects,
                open_questions=list(section.open_questions),
                policy_warnings=list(section.policy_warnings),
                draft_content=section.draft_content,
                iteration=section.iteration,
                status=section.status,
                evaluation_results=list(section.evaluation_results),
                approval_status=section.approval_status,
                approver=section.approver,
                review_feedback=section.review_feedback,
                approved_at=section.approved_at,
                created_at=section.created_at,
                updated_at=section.updated_at or now,
            )
            self.session.add(db_record)
        else:
            db_record.department_name = section.department_name
            db_record.responsible_person = section.responsible_person
            db_record.key_aspects = section.key_aspects
            db_record.open_questions = list(section.open_questions)
            db_record.policy_warnings = list(section.policy_warnings)
            db_record.draft_content = section.draft_content
            db_record.iteration = section.iteration
            db_record.status = section.status
            db_record.evaluation_results = list(section.evaluation_results)
            db_record.approval_status = section.approval_status
            db_record.approver = section.approver
            db_record.review_feedback = section.review_feedback
            db_record.approved_at = section.approved_at
            db_record.updated_at = now
            self.session.add(db_record)

        self.session.commit()
        self.session.refresh(db_record)
        return self._to_domain_section(db_record)

    def get_department_section(
        self, ticket_id: UUID, department_id: str
    ) -> Optional[DepartmentSection]:
        """Retrieve a specific department section by ticket_id and department_id."""
        statement = select(DepartmentSectionTable).where(
            DepartmentSectionTable.ticket_id == ticket_id,
            DepartmentSectionTable.department_id == department_id,
        )
        record = self.session.exec(statement).first()
        if record is None:
            return None
        return self._to_domain_section(record)

    def update_department_section_draft(
        self,
        ticket_id: UUID,
        department_id: str,
        draft_content: Optional[str],
        iteration: int,
        status: str,
        evaluation_result: Optional[EvaluationResult] = None,
    ) -> Optional[DepartmentSection]:
        """Update draft content, iteration counter, status, and evaluation history for a department section."""
        statement = select(DepartmentSectionTable).where(
            DepartmentSectionTable.ticket_id == ticket_id,
            DepartmentSectionTable.department_id == department_id,
        )
        db_record = self.session.exec(statement).first()
        if db_record is None:
            return None

        if draft_content is not None:
            db_record.draft_content = draft_content
        db_record.iteration = iteration
        db_record.status = status
        if evaluation_result is not None:
            history = list(db_record.evaluation_results or [])
            history.append(evaluation_result.to_schema_dict())
            db_record.evaluation_results = history
        db_record.updated_at = datetime.now(timezone.utc)

        self.session.add(db_record)
        self.session.commit()
        self.session.refresh(db_record)
        return self._to_domain_section(db_record)

    def list_department_sections(self, ticket_id: UUID) -> List[DepartmentSection]:
        """List all department analysis sections for a ticket."""
        statement = select(DepartmentSectionTable).where(
            DepartmentSectionTable.ticket_id == ticket_id
        )
        records = self.session.exec(statement).all()
        return [self._to_domain_section(r) for r in records]

    def update_department_section_approval(
        self,
        ticket_id: UUID,
        department_id: str,
        approval_status: str,
        approver: Optional[str] = None,
        review_feedback: Optional[str] = None,
        iteration: Optional[int] = None,
        draft_content: Optional[str] = None,
        approved_at: Optional[datetime] = None,
    ) -> Optional[DepartmentSection]:
        """Update Part 3 human approval status, approver, feedback, and timestamp for a department section."""
        statement = select(DepartmentSectionTable).where(
            DepartmentSectionTable.ticket_id == ticket_id,
            DepartmentSectionTable.department_id == department_id,
        )
        db_record = self.session.exec(statement).first()
        if db_record is None:
            return None

        db_record.approval_status = approval_status
        if approver is not None:
            db_record.approver = approver
        if review_feedback is not None:
            db_record.review_feedback = review_feedback
        elif approval_status == "approved":
            db_record.review_feedback = None
        if iteration is not None:
            db_record.iteration = iteration
        if draft_content is not None:
            db_record.draft_content = draft_content
        if approved_at is not None:
            db_record.approved_at = approved_at
        elif approval_status == "approved" and db_record.approved_at is None:
            db_record.approved_at = datetime.now(timezone.utc)
        elif approval_status != "approved":
            db_record.approved_at = None

        db_record.updated_at = datetime.now(timezone.utc)
        self.session.add(db_record)
        self.session.commit()
        self.session.refresh(db_record)
        return self._to_domain_section(db_record)

    # ---------------------------------------------------------
    # Part 3 Arbitration Log & Final Document Operations
    # ---------------------------------------------------------

    def save_arbitration_log(self, log: ArbitrationLog) -> ArbitrationLog:
        """Persist a deterministic conflict arbitration audit log entry."""
        db_record = self.session.get(ArbitrationLogTable, log.id)
        if db_record is None:
            db_record = ArbitrationLogTable(
                id=log.id,
                ticket_id=log.ticket_id,
                trigger_id=log.trigger_id,
                arbiter=log.arbiter,
                rule_applied=log.rule_applied,
                resolution_details=dict(log.resolution_details),
                created_at=log.created_at,
            )
            self.session.add(db_record)
        else:
            db_record.trigger_id = log.trigger_id
            db_record.arbiter = log.arbiter
            db_record.rule_applied = log.rule_applied
            db_record.resolution_details = dict(log.resolution_details)
            self.session.add(db_record)

        self.session.commit()
        self.session.refresh(db_record)
        return self._to_domain_arbitration_log(db_record)

    def list_arbitration_logs(self, ticket_id: UUID) -> List[ArbitrationLog]:
        """Retrieve all arbitration audit log entries for a ticket ordered chronologically."""
        statement = (
            select(ArbitrationLogTable)
            .where(ArbitrationLogTable.ticket_id == ticket_id)
            .order_by(ArbitrationLogTable.created_at.asc())
        )
        records = self.session.exec(statement).all()
        return [self._to_domain_arbitration_log(r) for r in records]

    def save_final_document(self, document: FinalDocument) -> FinalDocument:
        """Persist or update the synthesized final proposal document for a ticket."""
        statement = select(FinalDocumentTable).where(
            FinalDocumentTable.ticket_id == document.ticket_id
        )
        db_record = self.session.exec(statement).first()
        if db_record is None:
            db_record = FinalDocumentTable(
                id=document.id,
                ticket_id=document.ticket_id,
                title=document.title,
                client_name=document.client_name,
                currency=document.currency,
                executive_summary=document.executive_summary,
                sections=dict(document.sections),
                generated_at=document.generated_at,
            )
            self.session.add(db_record)
        else:
            db_record.title = document.title
            db_record.client_name = document.client_name
            db_record.currency = document.currency
            db_record.executive_summary = document.executive_summary
            db_record.sections = dict(document.sections)
            db_record.generated_at = document.generated_at
            self.session.add(db_record)

        self.session.commit()
        self.session.refresh(db_record)
        return self._to_domain_final_document(db_record)

    def get_final_document(self, ticket_id: UUID) -> Optional[FinalDocument]:
        """Retrieve the synthesized final proposal document for a ticket."""
        statement = select(FinalDocumentTable).where(
            FinalDocumentTable.ticket_id == ticket_id
        )
        record = self.session.exec(statement).first()
        if record is None:
            return None
        return self._to_domain_final_document(record)

    # ---------------------------------------------------------
    # Handoff Payload Operations (Part 1 -> Part 2 & Part 2 -> Part 3)
    # ---------------------------------------------------------

    def save_handoff_payload(self, payload: IntakeHandoffPayload) -> IntakeHandoffPayload:
        """Persist or update the Part 2 handoff payload."""
        db_record = self.session.get(IntakeHandoffPayloadTable, payload.id)
        if db_record is None:
            stmt = select(IntakeHandoffPayloadTable).where(
                IntakeHandoffPayloadTable.ticket_id == payload.ticket_id
            )
            db_record = self.session.exec(stmt).first()
        contacts_dict = [asdict(c) for c in payload.internal_contacts]
        if db_record is None:
            db_record = IntakeHandoffPayloadTable(
                id=payload.id,
                ticket_id=payload.ticket_id,
                schema_version=payload.schema_version,
                executive_summary=payload.executive_summary,
                flagged_contradictions=list(payload.flagged_contradictions),
                key_questions_for_prospect=list(payload.key_questions_for_prospect),
                internal_contacts=contacts_dict,
                full_handoff_json=payload.full_handoff_json,
                created_at=payload.created_at,
            )
            self.session.add(db_record)
        else:
            db_record.schema_version = payload.schema_version
            db_record.executive_summary = payload.executive_summary
            db_record.flagged_contradictions = list(payload.flagged_contradictions)
            db_record.key_questions_for_prospect = list(payload.key_questions_for_prospect)
            db_record.internal_contacts = contacts_dict
            db_record.full_handoff_json = payload.full_handoff_json
            self.session.add(db_record)

        self.session.commit()
        self.session.refresh(db_record)
        return self._to_domain_handoff(db_record)

    def get_handoff_payload(self, ticket_id: UUID) -> Optional[IntakeHandoffPayload]:
        """Retrieve the canonical Part 2 handoff payload for a ticket."""
        statement = select(IntakeHandoffPayloadTable).where(
            IntakeHandoffPayloadTable.ticket_id == ticket_id
        )
        record = self.session.exec(statement).first()
        if record is None:
            return None
        return self._to_domain_handoff(record)

    def save_part3_handoff_payload(self, payload: Part3HandoffPayload) -> Part3HandoffPayload:
        """Persist or update the canonical Part 3 handoff payload."""
        statement = select(Part3HandoffPayloadTable).where(
            Part3HandoffPayloadTable.ticket_id == payload.ticket_id
        )
        db_record = self.session.exec(statement).first()
        if db_record is None:
            db_record = Part3HandoffPayloadTable(
                id=payload.id,
                ticket_id=payload.ticket_id,
                schema_version=payload.schema_version,
                overall_status=payload.overall_status,
                rfp_metadata=dict(payload.rfp_metadata),
                department_sections=dict(payload.department_sections),
                emitted_at=payload.emitted_at,
            )
            self.session.add(db_record)
        else:
            db_record.schema_version = payload.schema_version
            db_record.overall_status = payload.overall_status
            db_record.rfp_metadata = dict(payload.rfp_metadata)
            db_record.department_sections = dict(payload.department_sections)
            db_record.emitted_at = payload.emitted_at
            self.session.add(db_record)

        self.session.commit()
        self.session.refresh(db_record)
        return self._to_domain_part3_handoff(db_record)

    def get_part3_handoff_payload(self, ticket_id: UUID) -> Optional[Part3HandoffPayload]:
        """Retrieve the canonical Part 3 handoff payload for a ticket."""
        statement = select(Part3HandoffPayloadTable).where(
            Part3HandoffPayloadTable.ticket_id == ticket_id
        )
        record = self.session.exec(statement).first()
        if record is None:
            return None
        return self._to_domain_part3_handoff(record)

    # ---------------------------------------------------------
    # Entity Mapping Helpers
    # ---------------------------------------------------------

    def _to_domain_ticket(self, record: IntakeTicketTable) -> IntakeTicket:
        return IntakeTicket(
            id=record.id,
            ticket_number=record.ticket_number,
            status=TicketStatus(record.status),
            raw_pdf_path=record.raw_pdf_path,
            raw_pdf_filename=record.raw_pdf_filename,
            file_size_bytes=record.file_size_bytes,
            rejection_reason=record.rejection_reason,
            error_message=record.error_message,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def _to_domain_metadata(self, record: RFPMetadataTable) -> RFPMetadata:
        scores_data = record.readability_scores or {}
        scores = ReadabilityScores(
            flesch_reading_ease=float(scores_data.get("flesch_reading_ease", 0.0)),
            flesch_kincaid_grade=float(scores_data.get("flesch_kincaid_grade", 0.0)),
            reading_level_label=str(scores_data.get("reading_level_label", "Standard")),
            word_count=int(scores_data.get("word_count", 0)),
            sentence_count=int(scores_data.get("sentence_count", 0)),
        )
        return RFPMetadata(
            id=record.id,
            ticket_id=record.ticket_id,
            client_name=record.client_name,
            client_country=record.client_country,  # type: ignore
            currency=record.currency,  # type: ignore
            services_requested=record.services_requested or [],
            monthly_volume=record.monthly_volume,
            deadline=record.deadline,
            budget_range=record.budget_range,
            departments_needed=record.departments_needed or [],  # type: ignore
            unsupported_services=record.unsupported_services or [],
            readability_scores=scores,
            created_at=record.created_at,
        )

    def _to_domain_section(self, record: DepartmentSectionTable) -> DepartmentSection:
        return DepartmentSection(
            id=record.id,
            ticket_id=record.ticket_id,
            department_id=record.department_id,  # type: ignore
            department_name=record.department_name,
            responsible_person=record.responsible_person,
            key_aspects=record.key_aspects or {},
            open_questions=record.open_questions or [],
            policy_warnings=record.policy_warnings or [],
            draft_content=getattr(record, "draft_content", None),
            iteration=int(getattr(record, "iteration", 0) or 0),
            status=str(getattr(record, "status", "pending") or "pending"),
            evaluation_results=list(getattr(record, "evaluation_results", None) or []),
            approval_status=str(getattr(record, "approval_status", "pending") or "pending"),
            approver=getattr(record, "approver", None),
            review_feedback=getattr(record, "review_feedback", None),
            approved_at=getattr(record, "approved_at", None),
            created_at=record.created_at,
            updated_at=getattr(record, "updated_at", None) or record.created_at,
        )

    def _to_domain_arbitration_log(self, record: ArbitrationLogTable) -> ArbitrationLog:
        return ArbitrationLog(
            id=record.id,
            ticket_id=record.ticket_id,
            trigger_id=record.trigger_id,  # type: ignore
            arbiter=record.arbiter,  # type: ignore
            rule_applied=record.rule_applied,
            resolution_details=record.resolution_details or {},
            created_at=record.created_at,
        )

    def _to_domain_final_document(self, record: FinalDocumentTable) -> FinalDocument:
        return FinalDocument(
            id=record.id,
            ticket_id=record.ticket_id,
            title=record.title,
            client_name=record.client_name,
            currency=record.currency,  # type: ignore
            executive_summary=record.executive_summary,
            sections=record.sections or {},
            generated_at=record.generated_at,
        )

    def _to_domain_handoff(self, record: IntakeHandoffPayloadTable) -> IntakeHandoffPayload:
        raw_contacts = record.internal_contacts or []
        contacts = [
            InternalContact(
                name=c.get("name", ""),
                role=c.get("role", ""),
                department=c.get("department", ""),
            )
            for c in raw_contacts
        ]
        return IntakeHandoffPayload(
            id=record.id,
            ticket_id=record.ticket_id,
            schema_version=record.schema_version,
            executive_summary=record.executive_summary,
            flagged_contradictions=record.flagged_contradictions or [],
            key_questions_for_prospect=record.key_questions_for_prospect or [],
            internal_contacts=contacts,
            full_handoff_json=record.full_handoff_json or {},
            created_at=record.created_at,
        )

    def _to_domain_part3_handoff(self, record: Part3HandoffPayloadTable) -> Part3HandoffPayload:
        return Part3HandoffPayload(
            id=record.id,
            ticket_id=record.ticket_id,
            schema_version=record.schema_version,
            overall_status=record.overall_status,  # type: ignore
            rfp_metadata=record.rfp_metadata or {},
            department_sections=record.department_sections or {},
            emitted_at=record.emitted_at,
        )
