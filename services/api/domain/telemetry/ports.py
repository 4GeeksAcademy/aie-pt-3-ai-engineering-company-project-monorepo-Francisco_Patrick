"""Telemetry domain driven port interfaces.

Defines abstract sinks for recording telemetry events (e.g. structured logger, analytics broker).
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, List, Optional

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

    @abstractmethod
    def record_events(self, events: List[TelemetryEvent]) -> int:
        """Persist a list of validated telemetry events in a single transaction.

        Args:
            events: List of validated domain TelemetryEvent instances.

        Returns:
            Count of events successfully recorded.
        """
        ...


class TelemetryRepositoryPort(ABC):
    """Driven port interface for extracting raw telemetry records from persistence."""

    @abstractmethod
    def get_events_in_range(
        self,
        start_date: datetime,
        end_date: datetime,
        event_types: Optional[List[str]] = None,
    ) -> List[Any]:
        """Extract raw telemetry records within a UTC time window.

        Args:
            start_date: Inclusive UTC start datetime.
            end_date: Inclusive UTC end datetime.
            event_types: Optional list of event_type taxonomy filters.

        Returns:
            List of raw telemetry event records.
        """
        ...

    @abstractmethod
    def get_events_dataframe(
        self,
        start_date: datetime,
        end_date: datetime,
        event_types: Optional[List[str]] = None,
    ) -> Any:
        """Extract raw telemetry records within a UTC time window as a Pandas DataFrame.

        Args:
            start_date: Inclusive UTC start datetime.
            end_date: Inclusive UTC end datetime.
            event_types: Optional list of event_type taxonomy filters.

        Returns:
            pandas.DataFrame containing normalized telemetry event rows.
        """
        ...


__all__ = ["TelemetryRepositoryPort", "TelemetrySinkPort"]
