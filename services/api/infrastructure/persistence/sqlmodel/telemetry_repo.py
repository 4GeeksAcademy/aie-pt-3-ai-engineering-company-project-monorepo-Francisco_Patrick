"""SQLModel persistence adapter for querying Telemetry domain events.

Implements TelemetryRepositoryPort using SQLModel / SQLAlchemy relational sessions.
Extracts raw immutable TelemetryEventRecord entities and converts to normalized
Pandas DataFrames for analytics.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, Generator, List, Optional
import pandas as pd
from sqlmodel import Session, col, select

from domain.telemetry.ports import TelemetryRepositoryPort
from infrastructure.persistence.sqlmodel.client import sqlmodel_manager
from infrastructure.persistence.sqlmodel.models import TelemetryEventRecord


class SQLModelTelemetryRepository(TelemetryRepositoryPort):
    """Relational SQLModel persistence adapter implementing TelemetryRepositoryPort.

    Extracts raw immutable telemetry events filtered by temporal boundaries
    and optional event taxonomies.
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

    def get_events_in_range(
        self,
        start_date: datetime,
        end_date: datetime,
        event_types: Optional[List[str]] = None,
    ) -> List[TelemetryEventRecord]:
        """Extract raw telemetry records within a UTC time window.

        Args:
            start_date: Inclusive UTC start datetime.
            end_date: Inclusive UTC end datetime.
            event_types: Optional list of event_type taxonomy filters.

        Returns:
            List of raw TelemetryEventRecord entities ordered chronologically.
        """
        start_utc = (
            start_date.replace(tzinfo=timezone.utc)
            if start_date.tzinfo is None
            else start_date.astimezone(timezone.utc)
        )
        end_utc = (
            end_date.replace(tzinfo=timezone.utc)
            if end_date.tzinfo is None
            else end_date.astimezone(timezone.utc)
        )

        statement = select(TelemetryEventRecord).where(
            TelemetryEventRecord.timestamp >= start_utc,
            TelemetryEventRecord.timestamp <= end_utc,
        )

        if event_types:
            statement = statement.where(col(TelemetryEventRecord.event_type).in_(event_types))

        statement = statement.order_by(col(TelemetryEventRecord.timestamp).asc())

        with self._get_session() as session:
            results = session.exec(statement).all()
            return list(results)

    def get_events_as_dicts(
        self,
        start_date: datetime,
        end_date: datetime,
        event_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Extract raw telemetry records within a UTC time window as dictionaries.

        Args:
            start_date: Inclusive UTC start datetime.
            end_date: Inclusive UTC end datetime.
            event_types: Optional list of event_type taxonomy filters.

        Returns:
            List of dictionaries representing event records.
        """
        records = self.get_events_in_range(start_date, end_date, event_types=event_types)
        return [
            {
                "event_id": str(r.event_id),
                "timestamp": r.timestamp,
                "session_id": r.session_id,
                "user_id": r.user_id,
                "event_type": r.event_type,
                "schema_version": r.schema_version,
                "request_id": r.request_id,
                "properties": r.properties,
                "created_at": r.created_at,
            }
            for r in records
        ]

    def get_events_dataframe(
        self,
        start_date: datetime,
        end_date: datetime,
        event_types: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Extract raw telemetry records within a UTC time window as a Pandas DataFrame.

        Normalizes timestamp column to UTC timezone-aware pandas datetime.

        Args:
            start_date: Inclusive UTC start datetime.
            end_date: Inclusive UTC end datetime.
            event_types: Optional list of event_type taxonomy filters.

        Returns:
            pandas.DataFrame containing normalized telemetry event rows.
        """
        dicts = self.get_events_as_dicts(start_date, end_date, event_types=event_types)
        columns = [
            "event_id",
            "timestamp",
            "session_id",
            "user_id",
            "event_type",
            "schema_version",
            "request_id",
            "properties",
            "created_at",
        ]
        if not dicts:
            df = pd.DataFrame(columns=columns)
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            return df

        df = pd.DataFrame(dicts)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return df


__all__ = ["SQLModelTelemetryRepository"]
