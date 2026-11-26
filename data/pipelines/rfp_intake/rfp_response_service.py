"""Application service managing the Part 2 RFP Response Generation lifecycle.

Handles:
1. Validation and ingestion of Part 1 handoff state from PostgreSQL without re-parsing raw PDFs.
2. Initial ticket status transition from 'analisis_completo' to 'generando_borrador'.
3. Background execution of RFPResponseGenerationPipeline with defensive error handling.
"""

from __future__ import annotations

import logging
from pathlib import Path
import sys
from typing import Any, Dict, List, Literal, Optional, Tuple
from uuid import UUID

from sqlmodel import Session

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data.pipelines.rfp_response_generation.pipeline import (  # noqa: E402
    RFPResponseGenerationPipeline,
)
from domain.rfp.entities import (  # noqa: E402
    IntakeTicket,
    Part3HandoffPayload,
    TicketStatus,
)
from domain.rfp.ports import IntakeTicketRepositoryPort  # noqa: E402
from infrastructure.persistence.sqlmodel.client import get_engine  # noqa: E402
from infrastructure.persistence.sqlmodel.rfp_repository import (  # noqa: E402
    SQLModelIntakeTicketRepository,
)

logger = logging.getLogger("rfp_response_service")


class RFPResponseGenerationService:
    """Application service coordinating Part 2 proposal drafting and evaluation."""

    def __init__(self, repository: IntakeTicketRepositoryPort) -> None:
        self.repository = repository

    def initiate_proposal_generation(
        self, ticket_id: UUID
    ) -> Tuple[IntakeTicket, List[Literal["warehouse", "lastmile", "reverse"]]]:
        """Validate Part 1 completion and transition ticket to 'generando_borrador'.

        Args:
            ticket_id: UUID of the RFP ticket.

        Returns:
            Tuple of (updated IntakeTicket, list of active department IDs).

        Raises:
            LookupError: If the ticket does not exist.
            ValueError: If the ticket is not in a valid entry state (must be analisis_completo).
        """
        ticket = self.repository.get_ticket(ticket_id)
        if ticket is None:
            raise LookupError(f"Ticket '{ticket_id}' not found.")

        if ticket.status != TicketStatus.ANALISIS_COMPLETO:
            raise ValueError(
                f"Invalid ticket status '{ticket.status.value}'. Ticket must be in "
                f"'{TicketStatus.ANALISIS_COMPLETO.value}' to initiate proposal generation."
            )

        metadata = self.repository.get_metadata(ticket_id)
        if metadata is None:
            raise ValueError(
                f"Part 1 RFP metadata is missing for ticket '{ticket_id}'."
            )

        active_departments: List[Literal["warehouse", "lastmile", "reverse"]] = [
            d
            for d in metadata.departments_needed
            if d in ("warehouse", "lastmile", "reverse")
        ]

        ticket.mark_drafting()
        updated_ticket = self.repository.save_ticket(ticket)
        return updated_ticket, active_departments

    def execute_pipeline(
        self,
        ticket_id: UUID,
        max_attempts: int = 3,
    ) -> Part3HandoffPayload:
        """Execute the full Part 2 proposal generation and evaluation pipeline synchronously."""
        pipeline = RFPResponseGenerationPipeline(
            repository=self.repository,
            max_attempts=max_attempts,
        )
        return pipeline.execute_for_ticket(ticket_id)


def run_rfp_response_generation_background(ticket_id: UUID) -> None:
    """Entry point for FastAPI BackgroundTasks executing Part 2 proposal generation.

    Guarantees defensive error handling (Constitution Principle IV): any unexpected
    exception is logged internally and transitions the ticket to 'needs_human_review'
    with a sanitized diagnostic message rather than crashing or discarding the ticket.
    """
    engine = get_engine()
    with Session(engine) as session:
        repo = SQLModelIntakeTicketRepository(session)
        pipeline = RFPResponseGenerationPipeline(repository=repo)
        try:
            part3_payload = pipeline.execute_for_ticket(ticket_id)
            if part3_payload.overall_status != "needs_human_review":
                from data.pipelines.rfp_intake.rfp_approval_service import (
                    RFPApprovalService,
                )

                approval_service = RFPApprovalService(repository=repo)
                approval_service.enter_approval_milestone(ticket_id)
        except Exception as exc:
            logger.exception(
                "RFP Part 2 response generation failed for ticket %s: %s",
                ticket_id,
                exc,
            )
            ticket = repo.get_ticket(ticket_id)
            if ticket is not None:
                ticket.mark_needs_human_review(
                    error_message="Proposal generation encountered an internal processing error and requires human review."
                )
                repo.save_ticket(ticket)
