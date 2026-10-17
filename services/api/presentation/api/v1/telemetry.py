"""Telemetry API router (canonical v1, also mounted at the legacy /telemetry prefix)."""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from application.telemetry.report_service import TelemetryReportService
from application.telemetry.telemetry_service import TelemetryService
from domain.telemetry.models import IngestReceipt, RawTelemetryBatch
from domain.telemetry.report_models import TelemetryReportResponse
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
    response_model=TelemetryReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Operational Telemetry Report",
    description="Retrieves consolidated operational health metrics over a specified UTC time window.",
    responses={
        200: {
            "description": "Operational telemetry report successfully calculated or served from cache.",
            "headers": {
                "X-Cache": {
                    "description": "Cache status indicator (HIT or MISS).",
                    "schema": {"type": "string", "enum": ["HIT", "MISS"]},
                }
            },
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
    service: TelemetryReportService = Depends(get_telemetry_report_service_dep),
) -> TelemetryReportResponse:
    """Retrieve operational telemetry report with 60-second in-memory caching."""
    try:
        report, is_hit = service.get_report(start_date=start_date, end_date=end_date)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    response.headers["X-Cache"] = "HIT" if is_hit else "MISS"
    return report
