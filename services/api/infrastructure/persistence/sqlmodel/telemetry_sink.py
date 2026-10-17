"""SQLModel persistence adapter for Telemetry domain.

Implements TelemetrySinkPort using SQLModel / SQLAlchemy relational sessions.
Maps domain TelemetryEvent models into immutable TelemetryEventRecord table entities
with atomic bulk transaction persistence.
"""

from contextlib import contextmanager
from typing import Generator, List, Optional
from sqlmodel import Session

from domain.telemetry.models import TelemetryBatch, TelemetryEvent
from domain.telemetry.ports import TelemetrySinkPort
from infrastructure.persistence.sqlmodel.client import sqlmodel_manager
from infrastructure.persistence.sqlmodel.models import TelemetryEventRecord


class SQLModelTelemetrySink(TelemetrySinkPort):
    """Relational SQLModel persistence sink adapter implementing TelemetrySinkPort.

    Enforces write-only immutability with zero update or delete capabilities.
    """

    def __init__(self, session: Optional[Session] = None) -> None:
        """Initialize adapter with an optional active Session.

        Args:
            session: Optional existing SQLModel Session.
        """
        self._session = session

    @contextmanager
    def _get_session(self) -> Generator[Session, None, None]:
        """Context manager yielding active session or creating transient session."""
        if self._session is not None:
            yield self._session
        else:
            eng = sqlmodel_manager.get_engine()
            with Session(eng) as session:
                yield session

    def record_event(self, event: TelemetryEvent) -> None:
        """Persist a single validated telemetry event.

        Args:
            event: Validated domain TelemetryEvent.
        """
        self.record_events([event])

    def record_batch(self, batch: TelemetryBatch) -> int:
        """Persist a validated batch container of telemetry events.

        Args:
            batch: Validated domain TelemetryBatch.

        Returns:
            Count of events recorded.
        """
        return self.record_events(batch.events)

    def record_events(self, events: List[TelemetryEvent]) -> int:
        """Persist a list of validated telemetry events in a single atomic transaction.

        Args:
            events: List of validated domain TelemetryEvent instances.

        Returns:
            Count of events successfully recorded.
        """
        if not events:
            return 0

        records = [
            TelemetryEventRecord(
                event_id=e.eventId,
                timestamp=e.timestamp,
                session_id=e.sessionId,
                user_id=e.userId,
                event_type=e.event_type,
                schema_version=e.schemaVersion,
                request_id=e.requestId,
                properties=e.properties,
            )
            for e in events
        ]

        with self._get_session() as session:
            try:
                session.add_all(records)
                session.commit()
                return len(records)
            except Exception:
                session.rollback()
                raise


__all__ = ["SQLModelTelemetrySink"]
