"""End-to-end verification script for Quickstart scenarios 1, 2, and 3."""

from pathlib import Path
from uuid import uuid4
import pytest
from sqlmodel import Session

from application.agent.rfp_intake_pipeline import RFPIntakePipeline
from domain.rfp.entities import IntakeTicket, TicketStatus
from infrastructure.persistence.sqlmodel.client import get_engine
from infrastructure.persistence.sqlmodel.rfp_repository import SQLModelIntakeTicketRepository

REPO_ROOT = Path(__file__).resolve().parents[4]
SAMPLE_PDF_1 = REPO_ROOT / "docs" / "agentic-workflows" / "rfp-requests" / "trackflow-request-1.pdf"
SAMPLE_PDF_2 = REPO_ROOT / "docs" / "agentic-workflows" / "rfp-requests" / "trackflow-request-2.pdf"
SAMPLE_PDF_3 = REPO_ROOT / "docs" / "agentic-workflows" / "rfp-requests" / "trackflow-request-3.pdf"


def test_quickstart_scenario_1_carrier_pitch_rejection():
    """Scenario 1: Carrier rate pitch (trackflow-request-3.pdf) is cleanly discarded with logged reason."""
    engine = get_engine()
    ticket_id = uuid4()
    with Session(engine) as session:
        repo = SQLModelIntakeTicketRepository(session)
        ticket = IntakeTicket.create(
            raw_pdf_path=str(SAMPLE_PDF_3),
            raw_pdf_filename="trackflow-request-3.pdf",
            file_size_bytes=SAMPLE_PDF_3.stat().st_size,
            ticket_id=ticket_id,
        )
        repo.save_ticket(ticket)

        pipeline = RFPIntakePipeline(repository=repo)
        result = pipeline.execute(ticket_id, str(SAMPLE_PDF_3))

        updated_ticket = repo.get_ticket(ticket_id)
        assert updated_ticket is not None
        assert updated_ticket.status == TicketStatus.DESCARTADO
        assert updated_ticket.rejection_reason is not None
        assert any(
            w in updated_ticket.rejection_reason.lower()
            for w in ["carrier", "transportista", "vendor", "solicitation", "pitch"]
        )

        sections = repo.list_department_sections(ticket_id)
        assert len(sections) == 0
        handoff = repo.get_handoff_payload(ticket_id)
        assert handoff is None


def test_quickstart_scenario_2_modaviva_spain_analysis_and_handoff():
    """Scenario 2: Valid Spain RFP (ModaViva) scopes warehouse + reverse, omits last mile, and generates handoff."""
    engine = get_engine()
    ticket_id = uuid4()
    with Session(engine) as session:
        repo = SQLModelIntakeTicketRepository(session)
        ticket = IntakeTicket.create(
            raw_pdf_path=str(SAMPLE_PDF_1),
            raw_pdf_filename="trackflow-request-1.pdf",
            file_size_bytes=SAMPLE_PDF_1.stat().st_size,
            ticket_id=ticket_id,
        )
        repo.save_ticket(ticket)

        pipeline = RFPIntakePipeline(repository=repo)
        pipeline.execute(ticket_id, str(SAMPLE_PDF_1))

        updated_ticket = repo.get_ticket(ticket_id)
        assert updated_ticket is not None
        assert updated_ticket.status == TicketStatus.ANALISIS_COMPLETO

        meta = repo.get_metadata(ticket_id)
        assert meta is not None
        assert meta.client_name == "ModaViva, S.L."
        assert meta.client_country == "ES"
        assert meta.currency == "EUR"
        assert "warehouse" in meta.departments_needed
        assert "reverse" in meta.departments_needed
        assert "lastmile" not in meta.departments_needed

        sections = repo.list_department_sections(ticket_id)
        sec_ids = {s.department_id for s in sections}
        assert "warehouse" in sec_ids
        assert "reverse" in sec_ids
        assert "lastmile" not in sec_ids

        # Check Zero Hallucination: pallet storage missing recorded in open questions
        wh_section = next(s for s in sections if s.department_id == "warehouse")
        assert wh_section.key_aspects["pallet_storage_required"] is None
        assert len(wh_section.open_questions) > 0

        handoff = repo.get_handoff_payload(ticket_id)
        assert handoff is not None
        assert handoff.schema_version == "1.0.0"
        assert "ModaViva" in handoff.executive_summary


def test_quickstart_scenario_3_luna_cosmetics_us_analysis():
    """Scenario 3: Valid US RFP (Luna Cosmetics) scopes warehouse + lastmile, extracts volume 5000, USD."""
    engine = get_engine()
    ticket_id = uuid4()
    with Session(engine) as session:
        repo = SQLModelIntakeTicketRepository(session)
        ticket = IntakeTicket.create(
            raw_pdf_path=str(SAMPLE_PDF_2),
            raw_pdf_filename="trackflow-request-2.pdf",
            file_size_bytes=SAMPLE_PDF_2.stat().st_size,
            ticket_id=ticket_id,
        )
        repo.save_ticket(ticket)

        pipeline = RFPIntakePipeline(repository=repo)
        pipeline.execute(ticket_id, str(SAMPLE_PDF_2))

        updated_ticket = repo.get_ticket(ticket_id)
        assert updated_ticket is not None
        assert updated_ticket.status == TicketStatus.ANALISIS_COMPLETO

        meta = repo.get_metadata(ticket_id)
        assert meta is not None
        assert meta.client_name == "Luna Cosmetics"
        assert meta.client_country == "US"
        assert meta.currency == "USD"
        assert meta.monthly_volume == 5000
        assert "warehouse" in meta.departments_needed
        assert "lastmile" in meta.departments_needed
