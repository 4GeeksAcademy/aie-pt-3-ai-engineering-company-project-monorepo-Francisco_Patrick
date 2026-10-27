"""Relational models and database engine for reporting pipeline.

Defines SQLModel entities for executive KPI snapshots and pipeline execution audit logs,
along with database engine creation, session factory, and schema initialization.
"""

from datetime import datetime, timezone
import os
from typing import Generator, Optional
import urllib.parse
from uuid import UUID, uuid4

from sqlalchemy import Column as SAColumn, DateTime, Index, UniqueConstraint
from sqlalchemy.engine import Engine, make_url
from sqlmodel import Field, Session, SQLModel, create_engine


class ExecutiveKpiSnapshot(SQLModel, table=True):
    """Pre-computed weekly business performance snapshot for executive dashboards."""

    __tablename__ = "executive_kpi_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "period_start",
            "period_end",
            "country",
            name="uq_kpi_snapshot_period_country",
        ),
        Index("idx_kpi_snapshots_period", "period_start", "period_end"),
        Index("idx_kpi_snapshots_country", "country"),
    )

    snapshot_id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    period_start: datetime = Field(
        sa_column=SAColumn(DateTime(timezone=True), nullable=False),
    )
    period_end: datetime = Field(
        sa_column=SAColumn(DateTime(timezone=True), nullable=False),
    )
    country: str = Field(
        nullable=False,
        index=True,
        description="Regional scope: US, ES, or GLOBAL",
    )
    shipments_volume: int = Field(
        default=0,
        nullable=False,
        description="Total outbound packages fulfilled",
    )
    on_time_delivery_rate: float = Field(
        default=1.0,
        nullable=False,
        description="Ratio of deliveries completed within SLA (0.0 to 1.0)",
    )
    operational_cost_eur: float = Field(
        default=0.0,
        nullable=False,
        description="Total logistics and fulfillment cost in EUR",
    )
    returns_rate: float = Field(
        default=0.0,
        nullable=False,
        description="Return percentage (0.0 to 100.0)",
    )
    customer_satisfaction_score: float = Field(
        default=100.0,
        nullable=False,
        description="Normalized customer satisfaction score (0.0 to 100.0)",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=SAColumn(DateTime(timezone=True), nullable=False),
    )


class PipelineExecutionLog(SQLModel, table=True):
    """Audit execution metadata log for pipeline flow runs."""

    __tablename__ = "pipeline_execution_logs"

    run_id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False,
    )
    flow_name: str = Field(
        default="executive_performance_pipeline_flow",
        nullable=False,
    )
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=SAColumn(DateTime(timezone=True), nullable=False),
    )
    ended_at: Optional[datetime] = Field(
        default=None,
        sa_column=SAColumn(DateTime(timezone=True), nullable=True),
    )
    records_processed: int = Field(
        default=0,
        nullable=False,
    )
    status: str = Field(
        default="RUNNING",
        nullable=False,
        description="Lifecycle status: RUNNING, SUCCESS, FAILED",
    )
    error_details: Optional[str] = Field(
        default=None,
        nullable=True,
        description="Sanitized failure description",
    )


def get_default_sqlite_path() -> str:
    """Resolve absolute path to services/api/inventory.db."""
    base_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "services", "api")
    )
    return os.path.join(base_dir, "inventory.db")


def build_database_url() -> str:
    """Build database connection URL with PostgreSQL/SQLite fallback."""
    db_user = os.getenv("user") or os.getenv("DB_USER")
    db_password = os.getenv("password") or os.getenv("DB_PASSWORD")
    db_host = os.getenv("host") or os.getenv("DB_HOST")
    db_port = os.getenv("port") or os.getenv("DB_PORT", "5432")
    db_name = os.getenv("dbname") or os.getenv("DB_NAME", "postgres")

    default_sqlite_url = f"sqlite:///{get_default_sqlite_path()}"

    if db_user and db_host:
        encoded_password = urllib.parse.quote_plus(db_password or "")
        url = f"postgresql+psycopg2://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}?sslmode=require"
    else:
        url = os.environ.get("DATABASE_URL", default_sqlite_url)

    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+psycopg2://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    return url


_global_engine: Optional[Engine] = None


def get_engine(database_url: Optional[str] = None) -> Engine:
    """Create or return database engine for reporting schema operations."""
    global _global_engine
    if database_url:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        return create_engine(database_url, echo=False, connect_args=connect_args)

    if _global_engine is None:
        url = build_database_url()
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        try:
            _global_engine = create_engine(url, echo=False, connect_args=connect_args)
            with _global_engine.connect():
                pass
        except Exception:
            # Fall back to SQLite
            sqlite_url = f"sqlite:///{get_default_sqlite_path()}"
            _global_engine = create_engine(
                sqlite_url, echo=False, connect_args={"check_same_thread": False}
            )

    return _global_engine


def set_engine(engine: Engine) -> None:
    """Set global engine override (primarily for test isolation)."""
    global _global_engine
    _global_engine = engine


def get_session(engine: Optional[Engine] = None) -> Session:
    """Return an active SQLModel session."""
    eng = engine or get_engine()
    return Session(eng)


def init_reporting_db(target_engine: Optional[Engine] = None) -> None:
    """Initialize table schemas for executive_kpi_snapshots and pipeline_execution_logs."""
    eng = target_engine or get_engine()
    SQLModel.metadata.create_all(
        eng,
        tables=[
            ExecutiveKpiSnapshot.__table__,
            PipelineExecutionLog.__table__,
        ],
    )


__all__ = [
    "ExecutiveKpiSnapshot",
    "PipelineExecutionLog",
    "build_database_url",
    "get_default_sqlite_path",
    "get_engine",
    "get_session",
    "init_reporting_db",
    "set_engine",
]
