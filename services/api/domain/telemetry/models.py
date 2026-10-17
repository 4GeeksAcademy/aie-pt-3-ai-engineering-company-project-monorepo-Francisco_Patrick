"""Telemetry domain models and envelopes.

Pure business entities conforming strictly to TrackFlow Telemetry Plan with zero framework or database dependencies.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class RawTelemetryBatch(BaseModel):
    """Batch container for raw telemetry events allowing per-item evaluation."""

    model_config = ConfigDict(extra="forbid")

    events: List[Dict[str, Any]] = Field(
        ...,
        description="Array of raw event objects for individual envelope validation.",
    )


class IngestReceipt(BaseModel):
    """Response receipt confirming ingestion and validation of telemetry events."""

    model_config = ConfigDict(extra="forbid")

    received: int = Field(
        ...,
        ge=0,
        description="Total events evaluated.",
    )
    stored: int = Field(
        default=0,
        ge=0,
        description="Events successfully validated and persisted in storage.",
    )
    rejected: int = Field(
        default=0,
        ge=0,
        description="Events failing schema validation.",
    )

    @model_validator(mode="after")
    def validate_receipt_invariants(self) -> "IngestReceipt":
        """Enforce invariant: received must equal stored + rejected."""
        if self.received != self.stored + self.rejected:
            raise ValueError(
                f"IngestReceipt invariant violated: received ({self.received}) "
                f"must equal stored ({self.stored}) + rejected ({self.rejected})"
            )
        return self


__all__ = ["IngestReceipt", "RawTelemetryBatch", "TelemetryBatch", "TelemetryEvent"]
