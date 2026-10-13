"""Telemetry domain models and envelopes.

Pure business entities conforming strictly to TrackFlow Telemetry Plan with zero framework or database dependencies.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class TelemetryEvent(BaseModel):
    """Standard Telemetry Event Envelope conforming to TrackFlow Telemetry Plan."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    eventId: UUID = Field(
        ...,
        alias="event_id",
        description="Globally unique UUIDv4 identifying this event instance.",
    )
    timestamp: datetime = Field(
        ...,
        description="ISO 8601 UTC timestamp of the event capture.",
    )
    sessionId: str = Field(
        ...,
        alias="session_id",
        min_length=1,
        description="Unique session identifier grouping user activity.",
    )
    userId: Optional[str] = Field(
        default=None,
        alias="user_id",
        description="Pseudonymized user identifier or null if unauthenticated.",
    )
    event_type: str = Field(
        ...,
        pattern=r"^[a-z0-9]+(_[a-z0-9]+)+$",
        description="Event taxonomy name in snake_case entity_action format.",
    )
    schemaVersion: str = Field(
        ...,
        alias="schema_version",
        pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$",
        description="Semantic version string (e.g. 1.0.0).",
    )
    requestId: str = Field(
        ...,
        alias="request_id",
        min_length=1,
        description="Distributed tracing correlation identifier.",
    )
    properties: Dict[str, Any] = Field(
        default_factory=dict,
        alias="payload",
        description="Domain payload adhering to event allowlist.",
    )


class TelemetryBatch(BaseModel):
    """Batch container for enveloped telemetry events."""

    events: List[TelemetryEvent] = Field(
        ...,
        min_length=1,
        description="Array of enveloped telemetry events.",
    )


class IngestReceipt(BaseModel):
    """Response receipt confirming ingestion and validation of telemetry events."""

    received: int = Field(
        ...,
        description="Count of telemetry events accepted.",
    )


__all__ = ["IngestReceipt", "TelemetryBatch", "TelemetryEvent"]
