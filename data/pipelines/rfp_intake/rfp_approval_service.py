"""Application service managing Part 3 Human-in-the-Loop Department Approvals, Resume & Final Synthesis.

Coordinates:
1. Entry into the Part 3 approval milestone (`esperando_aprobación`) with scoped branch interrupts.
2. Validation and execution of human reviewer decisions (`approve`, `reject`, `request_changes`).
3. Thread-isolated checkpointer resumption (`rfp-{ticket_id}:{department_id}`).
4. Deterministic conflict arbitration and automatic final proposal synthesis (`FinalDocument`)
   transitioning the ticket to `terminado` (`done`) upon 100% department approval.
"""

from __future__ import annotations

import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.pipelines.rfp_approval_completion.pipeline import (  # noqa: E402
    BranchNotInterruptedError,
    DEFAULT_MAX_REVISIONS,
    RFPApprovalCompletionPipeline,
    ResumeValidationError,
    validate_resume_decision,
)
from data.pipelines.rfp_approval_completion.state import (  # noqa: E402
    ApprovalDecisionLiteral,
    DepartmentIdLiteral,
    SqliteSaver,
    get_default_checkpointer,
)
from domain.rfp.entities import (  # noqa: E402
    ArbitrationLog,
    FinalDocument,
    IntakeTicket,
    TicketStatus,
)
from domain.rfp.ports import IntakeTicketRepositoryPort  # noqa: E402

logger = logging.getLogger("rfp_approval_service")


class RFPApprovalService:
    """Application service orchestrating Part 3 HITL department approvals, arbitration, and final synthesis."""

    def __init__(
        self,
        repository: IntakeTicketRepositoryPort,
        checkpointer: Optional[SqliteSaver] = None,
        max_revisions: int = DEFAULT_MAX_REVISIONS,
    ) -> None:
        self.repository = repository
        self.checkpointer = checkpointer or get_default_checkpointer()
        self.max_revisions = max_revisions
        self.pipeline = RFPApprovalCompletionPipeline(
            repository=self.repository,
            checkpointer=self.checkpointer,
            max_revisions=self.max_revisions,
        )

    def enter_approval_milestone(
        self,
        ticket_id: UUID,
        run_initial_arbitration: bool = True,
    ) -> Dict[str, Any]:
        """Transition ticket to `esperando_aprobación` and initialize scoped department interrupts."""
        ticket = self.repository.get_ticket(ticket_id)
        if ticket is None:
            raise LookupError(f"Ticket '{ticket_id}' not found.")

        return self.pipeline.start_approval_phase(
            ticket_id=ticket_id,
            run_initial_arbitration=run_initial_arbitration,
        )

    def resume_department_approval(
        self,
        ticket_id: UUID,
        department_id: DepartmentIdLiteral,
        decision: ApprovalDecisionLiteral,
        approver: str,
        feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate human decision and resume the paused department approval branch.

        Raises:
            LookupError: If the ticket or department section does not exist (HTTP 404).
            ResumeValidationError: If decision or feedback fails validation (HTTP 400 / 422).
            BranchNotInterruptedError: If the branch is already finalized or not paused (HTTP 409).
        """
        # 1. Validate decision payload first
        validated = validate_resume_decision(
            {
                "department_id": department_id,
                "decision": decision,
                "approver": approver,
                "feedback": feedback,
            }
        )

        # 2. Verify ticket and department section exist in repository
        ticket = self.repository.get_ticket(ticket_id)
        if ticket is None:
            raise LookupError(f"Ticket '{ticket_id}' not found.")

        section = self.repository.get_department_section(ticket_id, department_id)
        if section is None:
            raise LookupError(
                f"Department section '{department_id}' not found for ticket '{ticket_id}'."
            )

        # 3. Check if branch is already finalized in database (allow commercial resolution on rejected or escalated branches)
        if section.approval_status == "approved" or (
            section.approval_status == "rejected"
            and validated["decision"] not in ("request_changes", "approve")
        ):
            raise BranchNotInterruptedError(
                f"Department section '{department_id}' for ticket '{ticket_id}' is already finalized "
                f"with status '{section.approval_status}' and is not paused in an interrupt."
            )

        # 4. If checkpointer does not yet have an active snapshot for this pending branch
        #    (e.g. ticket was seeded directly in DB), initialize approval checkpoints for pending branches.
        snapshot = self.pipeline.get_branch_snapshot(ticket_id, department_id)
        if not snapshot or not snapshot.values:
            self._initialize_pending_branch_checkpoints(ticket_id)

        # 5. Resume the target branch via LangGraph Command(resume=...)
        return self.pipeline.resume_department_approval(
            ticket_id=ticket_id,
            department_id=validated["department_id"],
            decision=validated["decision"],
            approver=validated["approver"],
            feedback=validated["feedback"],
        )

    def _initialize_pending_branch_checkpoints(self, ticket_id: UUID) -> None:
        """Ensure any pending department section has an initialized interrupted checkpoint."""
        sections = self.repository.list_department_sections(ticket_id)
        meta_entity = self.repository.get_metadata(ticket_id)
        meta_dict: Dict[str, Any] = {}
        if meta_entity is not None:
            meta_dict = {
                "client_name": meta_entity.client_name,
                "client_country": meta_entity.client_country,
                "currency": meta_entity.currency,
                "services_requested": list(meta_entity.services_requested),
                "monthly_volume": meta_entity.monthly_volume,
                "deadline": meta_entity.deadline,
                "budget_range": meta_entity.budget_range,
                "departments_needed": list(meta_entity.departments_needed),
            }
        else:
            meta_dict = {
                "client_name": "Prospective Client",
                "client_country": "ES",
                "currency": "EUR",
                "departments_needed": [s.department_id for s in sections],
            }

        self.pipeline.start_approval_phase(
            ticket_id=ticket_id,
            rfp_metadata=meta_dict,
            run_initial_arbitration=True,
        )
        # Restore already-approved sections if any were previously recorded in DB
        for sec in sections:
            if sec.approval_status == "approved":
                snap = self.pipeline.get_branch_snapshot(ticket_id, sec.department_id)
                if snap and snap.next:
                    self.pipeline.resume_department_approval(
                        ticket_id=ticket_id,
                        department_id=sec.department_id,
                        decision="approve",
                        approver=sec.approver or sec.responsible_person,
                    )

    def list_arbitration_logs(self, ticket_id: UUID) -> List[ArbitrationLog]:
        """Return all deterministic arbitration logs for a ticket."""
        ticket = self.repository.get_ticket(ticket_id)
        if ticket is None:
            raise LookupError(f"Ticket '{ticket_id}' not found.")
        return self.repository.list_arbitration_logs(ticket_id)

    def get_final_document(self, ticket_id: UUID) -> FinalDocument:
        """Return the synthesized FinalDocument for a completed ticket."""
        ticket = self.repository.get_ticket(ticket_id)
        if ticket is None:
            raise LookupError(f"Ticket '{ticket_id}' not found.")
        final_doc = self.repository.get_final_document(ticket_id)
        if final_doc is None:
            raise LookupError(
                f"Final document has not been generated yet for ticket '{ticket_id}'."
            )
        return final_doc
