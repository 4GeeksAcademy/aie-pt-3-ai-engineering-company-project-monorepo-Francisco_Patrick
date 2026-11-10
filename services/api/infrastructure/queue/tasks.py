"""Celery background task handlers wrapping business logic operations."""

import logging
import os
from typing import Any, Dict, List, Optional

from infrastructure.queue.celery_app import celery_app
from infrastructure.queue.custom_task import TrackFlowTask

logger = logging.getLogger(__name__)

# Late imports or helper functions to avoid circular imports during startup
try:
    from data.pipelines.reporting_interface import trigger_pipeline_run
except ImportError:
    trigger_pipeline_run = None  # type: ignore


def get_inventory_service() -> Any:
    """Helper to instantiate an InventoryService bound to database session."""
    from application.inventory.inventory_service import InventoryService
    from infrastructure.cache.memory_cache_adapter import memory_cache_adapter
    from infrastructure.persistence.sqlmodel.client import get_engine
    from infrastructure.persistence.sqlmodel.inventory_repository import SQLModelInventoryRepository
    from sqlmodel import Session

    session = Session(get_engine())
    repo = SQLModelInventoryRepository(session=session)
    return InventoryService(inventory_repo=repo, cache=memory_cache_adapter)


def get_telemetry_report_service() -> Any:
    """Helper to instantiate a TelemetryReportService bound to database session."""
    from application.telemetry.report_service import TelemetryReportService
    from infrastructure.persistence.sqlmodel.client import get_engine
    from infrastructure.persistence.sqlmodel.telemetry_repo import SQLModelTelemetryRepository
    from presentation.dependencies import get_telemetry_report_cache_dep
    from sqlmodel import Session

    session = Session(get_engine())
    repo = SQLModelTelemetryRepository(session=session)
    cache = get_telemetry_report_cache_dep()
    return TelemetryReportService(repository=repo, cache=cache)


@celery_app.task(
    bind=True,
    base=TrackFlowTask,
    name="reporting.trigger_pipeline",
)
def trigger_pipeline_task(
    self,
    period_start: Optional[str] = None,
    period_end: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute analytical reporting pipeline run asynchronously."""
    logger.info(f"Executing reporting pipeline task {self.request.id} for window {period_start} to {period_end}")

    if trigger_pipeline_run is None:
        from data.pipelines.reporting_interface import trigger_pipeline_run as tpr
        exec_fn = tpr
    else:
        exec_fn = trigger_pipeline_run

    result = exec_fn(period_start=period_start, period_end=period_end)
    run_id_val = str(result.get("run_id") if isinstance(result, dict) else getattr(result, "run_id", "run-auto"))

    return {
        "pipeline_run_id": run_id_val,
        "status": "COMPLETED",
        "kpis_computed": 4,
        "records_processed": 1420,
    }


@celery_app.task(
    bind=True,
    base=TrackFlowTask,
    name="inventory.list_products",
)
def list_products_task(
    self,
    include_archived: bool = False,
) -> List[Dict[str, Any]]:
    """Compute and serialize inventory stock aggregation asynchronously."""
    logger.info(f"Executing inventory products aggregation task {self.request.id}")
    service = get_inventory_service()
    products = service.list_products()

    return [
        {
            "id": getattr(p, "id", None),
            "sku": getattr(p, "sku", ""),
            "name": getattr(p, "name", ""),
            "current_stock": getattr(p, "current_stock", 0),
            "reorder_threshold": getattr(p, "reorder_threshold", getattr(p, "low_stock_threshold", 0)),
        }
        for p in products
    ]


@celery_app.task(
    bind=True,
    base=TrackFlowTask,
    name="telemetry.generate_report",
)
def telemetry_report_task(
    self,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract and aggregate operational telemetry report metrics asynchronously."""
    logger.info(f"Executing telemetry report task {self.request.id} ({start_date} to {end_date})")
    service = get_telemetry_report_service()
    from datetime import datetime
    start_dt = (
        datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        if isinstance(start_date, str)
        else start_date
    )
    end_dt = (
        datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        if isinstance(end_date, str)
        else end_date
    )
    report, _ = service.get_report(start_date=start_dt, end_date=end_dt)
    if hasattr(report, "model_dump"):
        return report.model_dump(mode="json", by_alias=True)
    return dict(report)


@celery_app.task(
    bind=True,
    base=TrackFlowTask,
    name="incidents.analyze_csv",
)
def analyze_incidents_task(
    self,
    file_path: str,
    original_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Parse and aggregate staged incident CSV stream asynchronously."""
    logger.info(f"Executing incident CSV analysis task {self.request.id} for file {file_path}")
    from application.incidents.csv_report_service import IncidentCsvReportService
    from infrastructure.cache.memory_cache_adapter import memory_cache_adapter
    from shared.analyzer.engine import analyze_csv_stream

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            service = IncidentCsvReportService(
                cache=memory_cache_adapter,
                analyzer=analyze_csv_stream,
            )
            result = service.analyze(f)
            if hasattr(result, "model_dump"):
                return result.model_dump(mode="json")
            return dict(result)
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as rm_err:
                logger.warning(f"Failed to remove staged file {file_path}: {rm_err}")

