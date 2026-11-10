"""Telemetry API router (canonical v1, also mounted at the legacy /telemetry prefix)."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from application.telemetry.report_service import TelemetryReportService
from application.telemetry.telemetry_service import TelemetryService
from domain.telemetry.models import IngestReceipt, RawTelemetryBatch
from domain.telemetry.report_models import TelemetryReportResponse
from infrastructure.queue.schemas import AsyncTaskAcceptedResponse
from presentation.dependencies import (
    get_telemetry_report_service_dep,
    get_telemetry_service_dep,
)

router = APIRouter(tags=["telemetry"])


@router.post(
    "/events",
    response_model=IngestReceipt,
    status_code=status.HTTP_200_OK,
    summary="Ingest batch of telemetry events",
)
def ingest_telemetry_events(
    batch: RawTelemetryBatch,
    service: TelemetryService = Depends(get_telemetry_service_dep),
) -> IngestReceipt:
    """Validate each event individually, dispatch valid events in bulk to the sink, and return a receipt."""
    return service.record_raw_batch(batch)


@router.get(
    "/report",
    response_model=AsyncTaskAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Get Operational Telemetry Report",
    description="Enqueues operational telemetry report generation and returns tracking ID.",
    responses={
        202: {
            "description": "Telemetry report task enqueued successfully.",
        },
        422: {
            "description": "Validation error (e.g. malformed date string or start_date > end_date)."
        },
        500: {
            "description": "Internal server error with sanitized error message."
        },
    },
)
def get_telemetry_report(
    response: Response,
    start_date: Optional[datetime] = Query(
        default=None,
        description="Start of reporting window in ISO 8601 format (inclusive).",
    ),
    end_date: Optional[datetime] = Query(
        default=None,
        description="End of reporting window in ISO 8601 format (inclusive).",
    ),
) -> AsyncTaskAcceptedResponse:
    """Enqueues operational telemetry report generation and returns tracking ID."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date must be before or equal to end_date",
        )

    from infrastructure.queue.celery_app import register_enqueued_task
    from infrastructure.queue.tasks import telemetry_report_task

    start_iso = start_date.isoformat() if start_date else None
    end_iso = end_date.isoformat() if end_date else None

    async_result = telemetry_report_task.delay(start_date=start_iso, end_date=end_iso)
    task_id = str(async_result.id)
    register_enqueued_task(task_id, "telemetry.generate_report")
    poll_url = f"/api/v1/tasks/{task_id}"
    response.headers["Location"] = poll_url

    return AsyncTaskAcceptedResponse(
        task_id=task_id,
        status="pending",
        message="Telemetry report generation task enqueued.",
        poll_url=poll_url,
    )
