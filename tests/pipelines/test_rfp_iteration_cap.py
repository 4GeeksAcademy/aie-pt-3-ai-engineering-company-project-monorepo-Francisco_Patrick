"""Unit and integration tests for iteration cap exhaustion escalating to needs_human_review (User Story 3 - T025)."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Dict, Optional
from uuid import uuid4

from sqlmodel import Session

REPO_ROOT = Path(__file__).resolve().parents[2]
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from application.agent.rfp_generator_agents import (  # noqa: E402
    BaseDepartmentGeneratorAgent,
    WarehouseGeneratorAgent,
)
from data.pipelines.rfp_response_generation.pipeline import (  # noqa: E402
    RFPResponseGenerationPipeline,
)
from domain.rfp.entities import (  # noqa: E402
    DepartmentSection,
    IntakeTicket,
    ReadabilityScores,
    RFPMetadata,
    TicketStatus,
)
from infrastructure.persistence.sqlmodel.client import get_engine, init_db  # noqa: E402
from infrastructure.persistence.sqlmodel.rfp_repository import (  # noqa: E402
    SQLModelIntakeTicketRepository,
)


class _AlwaysNonCompliantReverseGenerator(BaseDepartmentGeneratorAgent):
    """Generator fixture that persistently promises 24h returns across all 3 attempts."""

    department_id = "reverse"  # type: ignore[assignment]
    department_name = "Reverse Logistics"
    responsible_person = "Sofía Ramos"

    def __init__(self) -> None:
        super().__init__()
        self.call_count = 0

    def generate(
        self,
        rfp_metadata: Dict[str, Any],
        section_context: Dict[str, Any],
        feedback_for_generator: Optional[str] = None,
        iteration: int = 1,
    ) -> str:
        self.call_count += 1
        return (
            f"## Reverse Logistics Proposal (Attempt {iteration})\n"
            "We offer a 30 days return window for an estimated return rate of 15.0% "
            "with manual quality inspection and disposition flow: reventa, reacondicionamiento, descarte.\n"
            "We promise same-day return processing in 24 hours from receipt.\n"
            "TrackFlow commits to a 99.0% on-time SLA.\n"
            "Inspection rate: 2.40 EUR per unit.\n\n"
            "### Volume Discount Table\n"
            "| Volume Tier | Discount |\n"
            "|---|---|\n"
            "| 1-2500 orders | 0% |\n"
            "| 2501+ orders | 10% |\n"
        )


def test_iteration_cap_exhaustion_escalates_to_needs_human_review_in_db() -> None:
    """Verify 3 failed attempts terminate the loop, mark section and ticket as needs_human_review, and retain artifacts."""
    engine = get_engine()
    init_db(engine)
    ticket_id = uuid4()

    stubborn_gen = _AlwaysNonCompliantReverseGenerator()

    with Session(engine) as session:
        repo = SQLModelIntakeTicketRepository(session)
        ticket = IntakeTicket.create(
            raw_pdf_path="data/raw/mock_modaviva.pdf",
            raw_pdf_filename="trackflow-request-1.pdf",
            file_size_bytes=2048,
            ticket_id=ticket_id,
        )
        ticket.mark_complete()
        repo.save_ticket(ticket)

        meta = RFPMetadata(
            id=uuid4(),
            ticket_id=ticket_id,
            client_name="ModaViva, S.L.",
            client_country="ES",
            currency="EUR",
            services_requested=["warehousing", "returns"],
            monthly_volume=3500,
            deadline="2026-12-15",
            budget_range=None,
            departments_needed=["warehouse", "reverse"],
            unsupported_services=[],
            readability_scores=ReadabilityScores(
                flesch_reading_ease=62.0,
                flesch_kincaid_grade=8.5,
                reading_level_label="Standard",
                word_count=350,
                sentence_count=20,
            ),
        )
        repo.save_metadata(meta)

        repo.save_department_section(
            DepartmentSection(
                id=uuid4(),
                ticket_id=ticket_id,
                department_id="warehouse",
                department_name="Operaciones de Almacén",
                responsible_person="Ana Whitfield",
                key_aspects={"warehouse_location_preference": "Zaragoza", "sku_count": 300},
                open_questions=[],
                policy_warnings=[],
            )
        )
        repo.save_department_section(
            DepartmentSection(
                id=uuid4(),
                ticket_id=ticket_id,
                department_id="reverse",
                department_name="Logística Inversa",
                responsible_person="Sofía Ramos",
                key_aspects={
                    "return_window_days": 30,
                    "estimated_return_rate": 0.15,
                    "inspection_required": True,
                    "disposition_flow": ["reventa", "reacondicionamiento", "descarte"],
                },
                open_questions=[],
                policy_warnings=[],
            )
        )

        pipeline = RFPResponseGenerationPipeline(
            repository=repo,
            generators={
                "warehouse": WarehouseGeneratorAgent(),
                "reverse": stubborn_gen,
            },
            max_attempts=3,
        )
        part3_handoff = pipeline.execute_for_ticket(ticket_id)

        # Loop called generator strictly 3 times (initial + 2 revisions)
        assert stubborn_gen.call_count == 3
        assert part3_handoff.overall_status == "needs_human_review"

        # Verify ticket status in DB is needs_human_review (NOT descartado)
        updated_ticket = repo.get_ticket(ticket_id)
        assert updated_ticket is not None
        assert updated_ticket.status == TicketStatus.NEEDS_HUMAN_REVIEW
        assert updated_ticket.status != TicketStatus.DESCARTADO

        # Verify reverse section in DB retained latest draft and 3 evaluation records
        rev_section = repo.get_department_section(ticket_id, "reverse")
        assert rev_section is not None
        assert rev_section.status == "needs_human_review"
        assert rev_section.iteration == 3
        assert rev_section.draft_content is not None
        assert "Attempt 3" in rev_section.draft_content
        assert len(rev_section.evaluation_results) == 3
        assert "RULE-RETURNS-TIME" in rev_section.evaluation_results[-1]["compliance"]["rule_ids"]

        # Verify warehouse section passed on iteration 1 independently
        wh_section = repo.get_department_section(ticket_id, "warehouse")
        assert wh_section is not None
        assert wh_section.status == "passed"
        assert wh_section.iteration == 1
