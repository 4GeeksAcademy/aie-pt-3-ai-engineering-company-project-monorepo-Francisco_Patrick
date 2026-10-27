"""Relational database models and status definitions for background jobs."""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Column as SAColumn, DateTime, Index
from sqlalchemy.engine import Engine
from sqlmodel import Field, SQLModel

from data.pipelines.models import get_engine


class JobStatus(str, Enum):
    """Execution status for background job orchestrations."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(frozen=True)
class JobExecutionResult:
    """Immutable result metadata returned by background job runners."""

    status: JobStatus
    target_date: str
    run_id: Optional[UUID] = None
    skipped: bool = False
    skip_reason: Optional[str] = None
    csv_path: Optional[str] = None
    pipeline_exit_code: Optional[int] = None
    error_message: Optional[str] = None


class JobRun(SQLModel, table=True):
    """Execution run record for concurrency locking and idempotency tracking."""

    __tablename__ = "job_runs"
    __table_args__ = (
        Index("idx_job_runs_name_target_date", "job_name", "target_date"),
        Index("idx_job_runs_name_status", "job_name", "status"),
    )

    id: UUID = Field(
        default_factory=uuid4,
        primary_key=True,
        index=True,
        nullable=False,
        description="Unique execution identifier",
    )
    job_name: str = Field(
        max_length=64,
        nullable=False,
        index=True,
        description="Canonical job identifier, e.g. 'nightly_export'",
    )
    target_date: str = Field(
        max_length=10,
        nullable=False,
        index=True,
        description="Operational cohort date in YYYY-MM-DD UTC format",
    )
    status: str = Field(
        default=JobStatus.PROCESSING.value,
        max_length=20,
        nullable=False,
        index=True,
        description="Lifecycle state: pending, processing, completed, failed",
    )
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=SAColumn(DateTime(timezone=True), nullable=False),
        description="Timestamp when execution began",
    )
    finished_at: Optional[datetime] = Field(
        default=None,
        sa_column=SAColumn(DateTime(timezone=True), nullable=True),
        description="Timestamp when execution finalized",
    )
    error_message: Optional[str] = Field(
        default=None,
        max_length=500,
        nullable=True,
        description="Sanitized failure diagnostic summary",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=SAColumn(DateTime(timezone=True), nullable=False),
        description="Record creation timestamp",
    )


def init_jobs_db(target_engine: Optional[Engine] = None) -> None:
    """Initialize table schema and indexes for the job_runs table."""
    eng = target_engine or get_engine()
    SQLModel.metadata.create_all(
        eng,
        tables=[JobRun.__table__],
    )


__all__ = [
    "JobExecutionResult",
    "JobRun",
    "JobStatus",
    "init_jobs_db",
]
