"""Contract and integration tests for Part 2 RFP Response Generation FastAPI endpoints (User Story 4 - T029)."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest
from sqlmodel import Session

from data.pipelines.rfp_intake.rfp_intake_pipeline import RFPIntakePipeline
from domain.rfp.entities import IntakeTicket
from infrastructure.persistence.sqlmodel.client import get_engine, init_db
from infrastructure.persistence.sqlmodel.rfp_repository import (
    SQLModelIntakeTicketRepository,
)
from main import create_app

REPO_ROOT = Path(__file__).resolve().parents[4]
SAMPLE_PDF_1 = (
    REPO_ROOT / "docs" / "agentic-workflows" / "rfp-requests" / "trackflow-request-1.pdf"
)


@pytest.fixture
def client() -> TestClient:
    init_db(get_engine())
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_generate_proposal_sections_and_part3_handoff_endpoints_e2e(
    client: TestClient,
) -> None:
    """Verify POST /generate-proposal, GET /sections, and GET /part3-handoff for ModaViva Spain."""
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

        # Complete Part 1 intake
        intake_pipeline = RFPIntakePipeline(repository=repo)
        intake_pipeline.execute(ticket_id, str(SAMPLE_PDF_1))

    # 1. Trigger Part 2 proposal generation via POST /api/v1/rfp/{ticket_id}/generate-proposal
    gen_resp = client.post(f"/api/v1/rfp/{ticket_id}/generate-proposal")
    assert gen_resp.status_code == 202
    gen_data = gen_resp.json()
    assert gen_data["ticket_id"] == str(ticket_id)
    assert gen_data["status"] == "generando_borrador"
    assert set(gen_data["active_departments"]) == {"warehouse", "reverse"}

    # 2. Retrieve department sections via GET /api/v1/rfp/{ticket_id}/sections
    sec_resp = client.get(f"/api/v1/rfp/{ticket_id}/sections")
    assert sec_resp.status_code == 200
    sections = sec_resp.json()
    assert len(sections) == 2
    by_dept = {s["department_id"]: s for s in sections}
    assert set(by_dept.keys()) == {"warehouse", "reverse"}

    for dept_id, sec in by_dept.items():
        assert sec["status"] == "passed"
        assert sec["iteration"] == 1
        assert sec["draft_content"] is not None
        assert "EUR" in sec["draft_content"]
        assert sec["latest_evaluation"] is not None
        assert sec["latest_evaluation"]["overall_pass"] is True
        assert sec["latest_evaluation"]["compliance"]["pass_status"] is True

    # 3. Retrieve Part 3 handoff package via GET /api/v1/rfp/{ticket_id}/part3-handoff
    handoff_resp = client.get(f"/api/v1/rfp/{ticket_id}/part3-handoff")
    assert handoff_resp.status_code == 200
    handoff_data = handoff_resp.json()
    assert handoff_data["ticket_id"] == str(ticket_id)
    assert handoff_data["schema_version"] == "2.0.0"
    assert handoff_data["overall_status"] == "passed"
    assert handoff_data["rfp_metadata"]["client_country"] == "ES"
    assert handoff_data["rfp_metadata"]["currency"] == "EUR"
    assert set(handoff_data["department_sections"].keys()) == {"warehouse", "reverse"}


def test_generate_proposal_returns_400_when_ticket_not_in_analisis_completo(
    client: TestClient,
) -> None:
    """Verify POST /generate-proposal rejects tickets still in 'analizando' state with HTTP 400."""
    engine = get_engine()
    ticket_id = uuid4()
    with Session(engine) as session:
        repo = SQLModelIntakeTicketRepository(session)
        ticket = IntakeTicket.create(
            raw_pdf_path=str(SAMPLE_PDF_1),
            raw_pdf_filename="trackflow-request-1.pdf",
            file_size_bytes=1024,
            ticket_id=ticket_id,
        )
        repo.save_ticket(ticket)

    resp = client.post(f"/api/v1/rfp/{ticket_id}/generate-proposal")
    assert resp.status_code == 400
    assert "analisis_completo" in resp.json()["detail"]


def test_generate_proposal_returns_404_for_missing_ticket(
    client: TestClient,
) -> None:
    """Verify POST /generate-proposal, GET /sections, and GET /part3-handoff return 404 for unknown ticket."""
    unknown_id = uuid4()
    assert client.post(f"/api/v1/rfp/{unknown_id}/generate-proposal").status_code == 404
    assert client.get(f"/api/v1/rfp/{unknown_id}/sections").status_code == 404
    assert client.get(f"/api/v1/rfp/{unknown_id}/part3-handoff").status_code == 404
