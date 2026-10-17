"""Telemetry application service orchestrating event ingestion and dispatch."""

import logging
import re
from typing import List, Optional, Union
from pydantic import ValidationError

from domain.telemetry.models import (
    IngestReceipt,
    RawTelemetryBatch,
    TelemetryBatch,
    TelemetryEvent,
)
from domain.telemetry.ports import TelemetrySinkPort

logger = logging.getLogger("trackflow.telemetry")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


def _sanitize_diagnostic_message(msg: str) -> str:
    """Mask potential PII patterns (email, SSN) from diagnostic messages as defense-in-depth."""
    # Mask email patterns
    msg = re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "[REDACTED_EMAIL]", msg)
    # Mask SSN patterns
    msg = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]", msg)
    # Mask payment card patterns
    msg = re.sub(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b", "[REDACTED_CARD]", msg)
    return msg


def _format_sanitized_validation_error(err: ValidationError) -> str:
    """Extract and sanitize validation error details without leaking input values or sensitive data.

    Only field locations and sanitized error message templates are included; raw input values
    are strictly omitted to prevent credential or PII leakage into application logs.
    """
    error_items: List[str] = []
    for e in err.errors():
        field_loc = ".".join(str(loc) for loc in e.get("loc", ()))
        raw_msg = e.get("msg", "Validation error")
        sanitized_msg = _sanitize_diagnostic_message(raw_msg)
        err_type = e.get("type", "unknown")
        error_items.append(f"field='{field_loc}', message='{sanitized_msg}', type='{err_type}'")
    return "; ".join(error_items)


class LoggingTelemetrySink(TelemetrySinkPort):
    """Default driven sink adapter writing structured telemetry events to logger stream."""

    def record_event(self, event: TelemetryEvent) -> None:
        """Log a single telemetry event.

        Args:
            event: Validated domain TelemetryEvent.
        """
        logger.info(
            "Telemetry event captured: id=%s type=%s session=%s",
            str(event.eventId),
            event.event_type,
            event.sessionId,
        )

    def record_batch(self, batch: TelemetryBatch) -> int:
        """Log a batch of telemetry events.

        Args:
            batch: Validated domain TelemetryBatch.

        Returns:
            Count of events logged.
        """
        return self.record_events(batch.events)

    def record_events(self, events: List[TelemetryEvent]) -> int:
        """Log a list of validated telemetry events.

        Args:
            events: List of validated domain TelemetryEvent instances.

        Returns:
            Count of events logged.
        """
        for event in events:
            self.record_event(event)
        return len(events)


class TelemetryService:
    """Application use case service managing ingestion and validation of telemetry events."""

    def __init__(self, sink: Optional[TelemetrySinkPort] = None) -> None:
        """Initialize service with injected telemetry sink port."""
        self._sink: TelemetrySinkPort = sink if sink is not None else LoggingTelemetrySink()

    def record_event(self, event: TelemetryEvent) -> None:
        """Validate and dispatch single telemetry event to sink."""
        self._sink.record_event(event)

    def record_raw_batch(self, raw_batch: RawTelemetryBatch) -> IngestReceipt:
        """Validate each event individually, isolate malformed items, and bulk persist valid items.

        Args:
            raw_batch: Batch container containing raw event dictionaries.

        Returns:
            IngestReceipt with accurate received, stored, and rejected counters.
        """
        valid_events: List[TelemetryEvent] = []
        rejected_count = 0

        for idx, raw_item in enumerate(raw_batch.events):
            try:
                valid_event = TelemetryEvent.model_validate(raw_item)
                valid_events.append(valid_event)
            except ValidationError as err:
                rejected_count += 1
                sanitized_err = _format_sanitized_validation_error(err)
                logger.warning(
                    "Telemetry event rejected: index=%d error=%s",
                    idx,
                    sanitized_err,
                )

        stored_count = 0
        if valid_events:
            stored_count = self._sink.record_events(valid_events)

        return IngestReceipt(
            received=len(raw_batch.events),
            stored=stored_count,
            rejected=rejected_count,
        )

    def record_batch(self, batch: Union[TelemetryBatch, RawTelemetryBatch]) -> IngestReceipt:
        """Validate and dispatch event batch to sink, returning receipt.

        Supports both RawTelemetryBatch for partial per-item evaluation and legacy TelemetryBatch.
        """
        if isinstance(batch, RawTelemetryBatch):
            return self.record_raw_batch(batch)

        stored_count = self._sink.record_events(batch.events)
        return IngestReceipt(
            received=len(batch.events),
            stored=stored_count,
            rejected=0,
        )


__all__ = ["LoggingTelemetrySink", "TelemetryService"]
