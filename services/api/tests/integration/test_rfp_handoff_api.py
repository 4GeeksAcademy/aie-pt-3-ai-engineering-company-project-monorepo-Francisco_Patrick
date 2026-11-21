"""Integration tests for canonical Part 2 handoff payload endpoint."""

import io
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from application.agent.rfp_intake_pipeline import RFPIntakePipeline
from domain.rfp.entities import IntakeTicket, TicketStatus
from infrastructure.persistence.sqlmodel.client import get_engine
from infrastructure.persistence.sqlmodel.rfp_repository import SQLModelIntakeTicketRepository
from main import create_app

REPO_ROOT = Path(__file__).resolve().parents[4]
SAMPLE_PDF_1 = REPO_ROOT / "docs" / "agentic-workflows" / "rfp-requests" / "trackflow-request-1.pdf"


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_get_handoff_payload_for_completed_ticket(client: TestClient):
    """Verify that a completed ticket returns its full Part 2 handoff payload matching schema."""
    engine = get_engine()
    ticket_id = uuid4()
    with Session(engine) as session:
        repo = SQLModelIntakeTicketRepository(session)
        # Seed and synchronously process ticket using pipeline
        ticket = IntakeTicket.create(
            raw_pdf_path=str(SAMPLE_PDF_1),
            raw_pdf_filename="trackflow-request-1.pdf",
            file_size_bytes=SAMPLE_PDF_1.stat().st_size,
            ticket_id=ticket_id,
        )
        repo.save_ticket(ticket)

        pipeline = RFPIntakePipeline(repository=repo)
        pipeline.execute(ticket_id, str(SAMPLE_PDF_1))

    # Retrieve via API
    response = client.get(f"/api/v1/rfp/tickets/{ticket_id}/handoff")

    assert response.status_code == 200
    data = response.json()
    assert data["ticket_id"] == str(ticket_id)
    assert data["schema_version"] == "1.0.0"
    assert "executive_summary" in data
    assert "ModaViva" in data["executive_summary"]
    assert isinstance(data["flagged_contradictions"], list)
    assert isinstance(data["key_questions_for_prospect"], list)
    assert len(data["internal_contacts"]) >= 3
    assert "full_handoff_json" in data
    assert data["full_handoff_json"]["metadata"]["client_name"] == "ModaViva, S.L."


def test_get_handoff_payload_incomplete_ticket_returns_400(client: TestClient):
    """Verify that requesting handoff for a ticket still in 'analizando' returns HTTP 400."""
    engine = get_engine()
    ticket_id = uuid4()
    with Session(engine) as session:
        repo = SQLModelIntakeTicketRepository(session)
        ticket = IntakeTicket.create(
            raw_pdf_path=str(SAMPLE_PDF_1),
            raw_pdf_filename="trackflow-request-1.pdf",
            file_size_bytes=1000,
            ticket_id=ticket_id,
        )
        repo.save_ticket(ticket)

    response = client.get(f"/api/v1/rfp/tickets/{ticket_id}/handoff")
    assert response.status_code == 400
    assert "not yet completed" in response.json()["detail"].lower()
