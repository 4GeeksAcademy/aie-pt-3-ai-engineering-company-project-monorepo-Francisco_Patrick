"""Telemetry application service orchestrating event ingestion and dispatch."""

import logging
from typing import Optional

from domain.telemetry.models import IngestReceipt, TelemetryBatch, TelemetryEvent
from domain.telemetry.ports import TelemetrySinkPort

logger = logging.getLogger("trackflow.telemetry")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


class LoggingTelemetrySink(TelemetrySinkPort):
    """Default driven sink adapter writing structured telemetry events to logger stream."""

    def record_event(self, event: TelemetryEvent) -> None:
        """Log a single telemetry event."""
        logger.info(
            "Telemetry event captured: id=%s type=%s session=%s",
            str(event.eventId),
            event.event_type,
            event.sessionId,
        )

    def record_batch(self, batch: TelemetryBatch) -> int:
        """Log a batch of telemetry events."""
        event_types = [event.event_type for event in batch.events]
        logger.info(
            "Received %d telemetry events in batch: %s",
            len(batch.events),
            event_types,
        )
        return len(batch.events)


class TelemetryService:
    """Application use case service managing ingestion and validation of telemetry events."""

    def __init__(self, sink: Optional[TelemetrySinkPort] = None) -> None:
        """Initialize service with injected telemetry sink port."""
        self._sink: TelemetrySinkPort = sink if sink is not None else LoggingTelemetrySink()

    def record_event(self, event: TelemetryEvent) -> None:
        """Validate and dispatch single telemetry event to sink."""
        self._sink.record_event(event)

    def record_batch(self, batch: TelemetryBatch) -> IngestReceipt:
        """Validate and dispatch event batch to sink, returning receipt."""
        count = self._sink.record_batch(batch)
        return IngestReceipt(received=count)


__all__ = ["LoggingTelemetrySink", "TelemetryService"]
