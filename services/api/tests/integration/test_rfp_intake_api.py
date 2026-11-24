"""Integration tests for asynchronous RFP ingestion endpoint and ticket retrieval."""

import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from main import create_app

REPO_ROOT = Path(__file__).resolve().parents[4]
SAMPLE_PDF_1 = REPO_ROOT / "docs" / "agentic-workflows" / "rfp-requests" / "trackflow-request-1.pdf"
SAMPLE_PDF_3 = REPO_ROOT / "docs" / "agentic-workflows" / "rfp-requests" / "trackflow-request-3.pdf"


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_upload_rfp_valid_pdf_returns_202(client: TestClient):
    """Verify uploading a valid PDF returns HTTP 202 with ticket details."""
    pdf_bytes = SAMPLE_PDF_1.read_bytes()
    files = {"file": ("trackflow-request-1.pdf", io.BytesIO(pdf_bytes), "application/pdf")}

    response = client.post("/api/v1/rfp/intake", files=files)

    assert response.status_code == 202
    data = response.json()
    assert "ticket_id" in data
    assert "ticket_number" in data
    assert data["status"] == "analizando"
    assert "created_at" in data

    ticket_id = data["ticket_id"]

    # Poll status immediately
    detail_res = client.get(f"/api/v1/rfp/tickets/{ticket_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["ticket_id"] == ticket_id
    assert detail["raw_pdf_filename"] == "trackflow-request-1.pdf"


def test_upload_rfp_rejects_non_pdf_file(client: TestClient):
    """Verify uploading a text file returns HTTP 400 Bad Request."""
    files = {"file": ("test.txt", io.BytesIO(b"Hello world plain text"), "text/plain")}

    response = client.post("/api/v1/rfp/intake", files=files)

    assert response.status_code == 400
    assert "only PDF documents (.pdf) are supported" in response.json()["detail"]


def test_upload_rfp_rejects_empty_file(client: TestClient):
    """Verify uploading an empty PDF returns HTTP 400 Bad Request."""
    files = {"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")}

    response = client.post("/api/v1/rfp/intake", files=files)

    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_get_ticket_not_found(client: TestClient):
    """Verify querying a non-existent UUID returns HTTP 404."""
    response = client.get("/api/v1/rfp/tickets/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_list_rfp_tickets(client: TestClient):
    """Verify listing recent tickets returns paginated items and total count."""
    response = client.get("/api/v1/rfp/tickets?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)
