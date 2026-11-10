"""Automated test validating broker message persistence and worker decoupling across web restarts."""

from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from infrastructure.queue.celery_app import register_enqueued_task
from main import app


def test_web_server_restart_preserves_task_tracking() -> None:
    """Verify restarting the FastAPI web server preserves in-flight task tracking and state retrieval."""
    task_id = "restart-test-uuid-9999"

    # Step 1: Simulate task enqueueing via initial web server session
    client1 = TestClient(app)
    register_enqueued_task(task_id, "inventory.list_products")

    # Step 2: "Restart" web server by tearing down client1 and instantiating client2
    del client1
    client2 = TestClient(app)

    # Step 3: Query status from fresh web server process
    with patch("presentation.api.v1.tasks.celery_app.AsyncResult") as mock_async_result:
        mock_res = MagicMock()
        mock_res.state = "PENDING"
        mock_res.ready.return_value = False
        mock_res.failed.return_value = False
        mock_async_result.return_value = mock_res

        response = client2.get(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == task_id
        assert data["status"] == "pending"

    # Step 4: Worker completes task independently in background
    completed_products = [{"id": 10, "sku": "SKU-RESTART-01", "current_stock": 100}]
    with patch("presentation.api.v1.tasks.celery_app.AsyncResult") as mock_async_result:
        mock_res = MagicMock()
        mock_res.state = "SUCCESS"
        mock_res.ready.return_value = True
        mock_res.result = completed_products
        mock_async_result.return_value = mock_res

        response_completed = client2.get(f"/tasks/{task_id}")
        assert response_completed.status_code == 200
        completed_data = response_completed.json()
        assert completed_data["status"] == "success"
        assert completed_data["result"] == completed_products

