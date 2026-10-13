"""Telemetry domain driven port interfaces.

Defines abstract sinks for recording telemetry events (e.g. structured logger, analytics broker).
"""

from abc import ABC, abstractmethod
from typing import List

from domain.telemetry.models import TelemetryBatch, TelemetryEvent


class TelemetrySinkPort(ABC):
    """Driven port interface for telemetry event sinks."""

    @abstractmethod
    def record_event(self, event: TelemetryEvent) -> None:
        """Record a single validated telemetry event.

        Args:
            event: Validated domain TelemetryEvent.
        """
        ...

    @abstractmethod
    def record_batch(self, batch: TelemetryBatch) -> int:
        """Record a validated batch of telemetry events.

        Args:
            batch: Validated domain TelemetryBatch.

        Returns:
            Count of events recorded.
        """
        ...


__all__ = ["TelemetrySinkPort"]
