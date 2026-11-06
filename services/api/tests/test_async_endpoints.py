"""Integration tests verifying HTTP 202 Accepted and async task dispatch on target endpoints."""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def mock_celery_dispatch():
    """Mock Celery delay and apply_async to avoid needing a live Redis broker during test runs."""
    with patch("infrastructure.queue.tasks.trigger_pipeline_task.delay") as mock_trigger, \
         patch("infrastructure.queue.tasks.list_products_task.delay") as mock_list, \
         patch("infrastructure.queue.tasks.telemetry_report_task.delay") as mock_telemetry, \
         patch("infrastructure.queue.tasks.analyze_incidents_task.apply_async") as mock_analyze:

        mock_trigger.return_value = MagicMock(id="11111111-1111-1111-1111-111111111111")
        mock_list.return_value = MagicMock(id="22222222-2222-2222-2222-222222222222")
        mock_telemetry.return_value = MagicMock(id="33333333-3333-3333-3333-333333333333")
        mock_analyze.return_value = MagicMock(id="44444444-4444-4444-4444-444444444444")
        yield


def test_post_reporting_trigger_returns_202_accepted() -> None:
    """POST /reporting/trigger returns HTTP 202 with task_id and poll_url."""
    response = client.post(
        "/reporting/trigger",
        json={"period_start": "2026-10-01T00:00:00Z", "period_end": "2026-10-31T23:59:59Z"},
    )
    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "pending"
    assert "poll_url" in data
    assert response.headers.get("Location") == data["poll_url"]


def test_get_inventory_products_returns_202_accepted() -> None:
    """GET /inventory/products returns HTTP 202 with task_id and poll_url."""
    response = client.get("/inventory/products")
    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "pending"
    assert "poll_url" in data
    assert response.headers.get("Location") == data["poll_url"]


def test_get_telemetry_report_returns_202_accepted() -> None:
    """GET /telemetry/report returns HTTP 202 with task_id and poll_url."""
    response = client.get("/telemetry/report")
    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "pending"
    assert "poll_url" in data
    assert response.headers.get("Location") == data["poll_url"]


def test_post_incidents_analyze_valid_csv_returns_202_accepted(tmp_path) -> None:
    """POST /incidents/analyze accepts valid CSV and returns HTTP 202."""
    csv_bytes = b"id,origin,severity,status,created_at,resolved_at\n1,USER,CRITICAL,RESOLVED,2026-10-01,2026-10-02\n"
    response = client.post(
        "/api/incidents/analyze",
        files={"file": ("incident_data.csv", csv_bytes, "text/csv")},
    )
    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "pending"
    assert "poll_url" in data
    assert response.headers.get("Location") == data["poll_url"]


def test_post_incidents_analyze_invalid_extension_returns_400() -> None:
    """POST /incidents/analyze rejects non-csv files with HTTP 400."""
    response = client.post(
        "/api/incidents/analyze",
        files={"file": ("incident_data.txt", b"plain text", "text/plain")},
    )
    assert response.status_code == 400


def test_post_incidents_analyze_empty_file_returns_400() -> None:
    """POST /incidents/analyze rejects empty files with HTTP 400."""
    response = client.post(
        "/api/incidents/analyze",
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert response.status_code == 400

