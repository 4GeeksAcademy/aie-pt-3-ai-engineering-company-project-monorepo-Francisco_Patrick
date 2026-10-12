import os
import logging
from datetime import datetime
from uuid import UUID
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, status
from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger("trackflow.telemetry")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

TELEMETRY_ENDPOINT_PATH = os.getenv("TELEMETRY_ENDPOINT", "/telemetry/events")

class TelemetryEvent(BaseModel):
    """
    Standard Telemetry Event Envelope conforming strictly to TrackFlow Telemetry Plan.
    """
    model_config = ConfigDict(extra="forbid")

    eventId: UUID = Field(
        ...,
        description="Globally unique UUIDv4 identifying this event instance."
    )
    timestamp: datetime = Field(
        ...,
        description="ISO 8601 UTC timestamp of the event capture."
    )
    sessionId: str = Field(
        ...,
        min_length=1,
        description="Unique session identifier grouping user activity."
    )
    userId: Optional[str] = Field(
        default=None,
        description="Pseudonymized user identifier or null if unauthenticated."
    )
    event_type: str = Field(
        ...,
        pattern=r"^[a-z0-9]+(_[a-z0-9]+)+$",
        description="Event taxonomy name in snake_case entity_action format."
    )
    schemaVersion: str = Field(
        ...,
        pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$",
        description="Semantic version string (e.g., 1.0.0)."
    )
    requestId: str = Field(
        ...,
        min_length=1,
        description="Distributed tracing correlation identifier."
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        description="Domain payload adhering to event allowlist."
    )


class TelemetryBatch(BaseModel):
    """
    Batch payload containing one or more enveloped telemetry events.
    """
    events: List[TelemetryEvent] = Field(
        ...,
        min_length=1,
        description="Array of enveloped telemetry events."
    )


class IngestReceipt(BaseModel):
    """
    Response model confirming receipt and validation of event batch.
    """
    received: int = Field(
        ...,
        description="Number of telemetry events successfully received and validated."
    )


router = APIRouter(tags=["telemetry"])


@router.post(
    "/telemetry/events",
    response_model=IngestReceipt,
    status_code=status.HTTP_200_OK,
    summary="Ingest batch of telemetry events"
)
@router.post(
    "/api/v1/telemetry/events",
    response_model=IngestReceipt,
    status_code=status.HTTP_200_OK,
    include_in_schema=False
)
def ingest_telemetry_events(batch: TelemetryBatch) -> IngestReceipt:
    """
    Stub endpoint to ingest and validate telemetry event batches.
    Validates standard envelope, logs event types, and returns receipt.
    """
    event_types = [event.event_type for event in batch.events]
    logger.info("Received %d telemetry events: %s", len(batch.events), event_types)
    return IngestReceipt(received=len(batch.events))
