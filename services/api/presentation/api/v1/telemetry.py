"""Telemetry API router (canonical v1, also mounted at the legacy /telemetry prefix)."""

from fastapi import APIRouter, Depends, status

from application.telemetry.telemetry_service import TelemetryService
from domain.telemetry.models import IngestReceipt, RawTelemetryBatch
from presentation.dependencies import get_telemetry_service_dep

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
