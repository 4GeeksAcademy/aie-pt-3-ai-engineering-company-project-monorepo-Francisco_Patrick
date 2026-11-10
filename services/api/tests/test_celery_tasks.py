"""Unit tests for background Celery task functions."""

import os
from unittest.mock import MagicMock, patch
import pytest

from infrastructure.queue.tasks import (
    analyze_incidents_task,
    list_products_task,
    telemetry_report_task,
    trigger_pipeline_task,
)


def test_trigger_pipeline_task_executes_successfully() -> None:
    """Verify trigger_pipeline_task executes pipeline logic and returns payload."""
    mock_result = {
        "pipeline_run_id": "run-2026-11-05-01",
        "status": "COMPLETED",
        "kpis_computed": 4,
        "records_processed": 1420,
    }
    with patch(
        "infrastructure.queue.tasks.trigger_pipeline_run",
        return_value=mock_result,
    ) as mock_trigger:
        res = trigger_pipeline_task.run(period_start="2026-10-01T00:00:00Z", period_end="2026-10-31T23:59:59Z")
        assert res["status"] == "COMPLETED"
        assert res["kpis_computed"] == 4
        mock_trigger.assert_called_once()


def test_list_products_task_returns_serialized_products() -> None:
    """Verify list_products_task retrieves products and serializes them."""
    mock_product = MagicMock()
    mock_product.id = 1
    mock_product.sku = "SKU-PROD-001"
    mock_product.name = "Standard Component"
    mock_product.current_stock = 250
    mock_product.reorder_threshold = 50

    with patch(
        "infrastructure.queue.tasks.get_inventory_service",
    ) as mock_get_service:
        mock_service = MagicMock()
        mock_service.list_products.return_value = [mock_product]
        mock_get_service.return_value = mock_service

        products = list_products_task.run()
        assert len(products) == 1
        assert products[0]["sku"] == "SKU-PROD-001"
        assert products[0]["current_stock"] == 250


def test_telemetry_report_task_returns_report_dict() -> None:
    """Verify telemetry_report_task generates report payload."""
    mock_report = MagicMock()
    mock_report.model_dump.return_value = {
        "time_window": {"start": "2026-10-01T00:00:00Z", "end": "2026-10-31T23:59:59Z"},
        "metrics": {"total_events": 100, "error_rate": 0.0, "p95_duration_ms": 25.0},
    }

    with patch(
        "infrastructure.queue.tasks.get_telemetry_report_service",
    ) as mock_get_service:
        mock_service = MagicMock()
        mock_service.get_report.return_value = (mock_report, False)
        mock_get_service.return_value = mock_service

        report = telemetry_report_task.run()
        assert report["metrics"]["total_events"] == 100


def test_analyze_incidents_task_parses_csv_and_cleans_up(tmp_path) -> None:
    """Verify analyze_incidents_task processes staged CSV and deletes temporary file."""
    csv_file = tmp_path / "test_incident.csv"
    csv_file.write_text("id,origin,severity,status,created_at,resolved_at\n1,USER,CRITICAL,RESOLVED,2026-10-01,2026-10-02\n")

    mock_analysis = MagicMock()
    mock_analysis.model_dump.return_value = {
        "total_incidents": 1,
        "severity_counts": {"CRITICAL": 1},
        "mean_resolution_time_hours": 24.0,
    }

    with patch(
        "application.incidents.csv_report_service.IncidentCsvReportService",
    ) as mock_cls:
        instance = MagicMock()
        instance.analyze.return_value = mock_analysis
        mock_cls.return_value = instance

        res = analyze_incidents_task.run(file_path=str(csv_file), original_filename="test.csv")
        assert res["total_incidents"] == 1
        assert not os.path.exists(str(csv_file))
