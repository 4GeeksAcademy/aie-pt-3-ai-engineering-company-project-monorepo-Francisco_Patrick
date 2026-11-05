"""Tests for task lifecycle status polling and result retrieval API."""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_get_task_status_unknown_id_returns_404() -> None:
    """Querying an unknown/unregistered task ID returns HTTP 404."""
    unknown_id = "00000000-0000-0000-0000-000000000000"
    with patch("presentation.api.v1.tasks.get_enqueued_task_meta", return_value=None), \
         patch("presentation.api.v1.tasks.celery_app.AsyncResult") as mock_async_result:
        mock_res = MagicMock()
        mock_res.state = "PENDING"
        mock_res.ready.return_value = False
        mock_res.failed.return_value = False
        mock_async_result.return_value = mock_res

        response = client.get(f"/api/v1/tasks/{unknown_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == f"Task '{unknown_id}' not found."


def test_get_task_status_pending_state() -> None:
    """Registered pending task returns HTTP 200 with pending status."""
    task_id = "11111111-2222-3333-4444-555555555555"
    meta = {
        "task_id": task_id,
        "task_name": "inventory.list_products",
        "status": "pending",
        "enqueued_at": "2026-11-05T12:00:00Z",
    }
    with patch("presentation.api.v1.tasks.get_enqueued_task_meta", return_value=meta), \
         patch("presentation.api.v1.tasks.celery_app.AsyncResult") as mock_async_result:
        mock_res = MagicMock()
        mock_res.state = "PENDING"
        mock_res.ready.return_value = False
        mock_res.failed.return_value = False
        mock_async_result.return_value = mock_res

        response = client.get(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "pending"
        assert data["result"] is None
        assert data["error"] is None


def test_get_task_status_started_state() -> None:
    """Running task returns HTTP 200 with started status."""
    task_id = "22222222-3333-4444-5555-666666666666"
    meta = {
        "task_id": task_id,
        "task_name": "reporting.trigger_pipeline",
        "status": "pending",
        "enqueued_at": "2026-11-05T12:00:00Z",
    }
    with patch("presentation.api.v1.tasks.get_enqueued_task_meta", return_value=meta), \
         patch("presentation.api.v1.tasks.celery_app.AsyncResult") as mock_async_result:
        mock_res = MagicMock()
        mock_res.state = "STARTED"
        mock_res.ready.return_value = False
        mock_res.failed.return_value = False
        mock_async_result.return_value = mock_res

        response = client.get(f"/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "started"
        assert data["result"] is None


def test_get_task_status_success_state() -> None:
    """Finished task returns HTTP 200 with success status and computed result."""
    task_id = "33333333-4444-5555-6666-777777777777"
    meta = {
        "task_id": task_id,
        "task_name": "inventory.list_products",
        "status": "pending",
        "enqueued_at": "2026-11-05T12:00:00Z",
    }
    expected_result = [{"id": 1, "sku": "SKU-001", "current_stock": 50}]
    with patch("presentation.api.v1.tasks.get_enqueued_task_meta", return_value=meta), \
         patch("presentation.api.v1.tasks.celery_app.AsyncResult") as mock_async_result:
        mock_res = MagicMock()
        mock_res.state = "SUCCESS"
        mock_res.ready.return_value = True
        mock_res.result = expected_result
        mock_async_result.return_value = mock_res

        response = client.get(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "success"
        assert data["result"] == expected_result
        assert data["error"] is None
        assert data["completed_at"] is not None


def test_get_task_status_failure_state_sanitizes_error() -> None:
    """Failed task returns HTTP 200 with failure status and sanitized error string."""
    task_id = "44444444-5555-6666-7777-888888888888"
    meta = {
        "task_id": task_id,
        "task_name": "reporting.trigger_pipeline",
        "status": "pending",
        "enqueued_at": "2026-11-05T12:00:00Z",
    }
    with patch("presentation.api.v1.tasks.get_enqueued_task_meta", return_value=meta), \
         patch("presentation.api.v1.tasks.celery_app.AsyncResult") as mock_async_result:
        mock_res = MagicMock()
        mock_res.state = "FAILURE"
        mock_res.ready.return_value = True
        mock_res.failed.return_value = True
        mock_res.result = Exception("Database connection failure with password=secret123 and token=Bearer abc.123")
        mock_async_result.return_value = mock_res

        response = client.get(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "failure"
        assert data["result"] is None
        assert "secret123" not in data["error"]
        assert "password=***REDACTED***" in data["error"]
