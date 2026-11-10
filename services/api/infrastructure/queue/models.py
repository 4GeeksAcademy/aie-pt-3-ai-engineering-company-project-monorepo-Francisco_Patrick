"""SQLModel entity for dead letter queue records."""

from datetime import datetime, timezone
from typing import Optional
from sqlmodel import Field, SQLModel


class DeadLetterQueueRecord(SQLModel, table=True):
    """Persistent audit entry stored when a task exhausts retries and is quarantined."""

    __tablename__ = "dead_letter_queue"

    id: Optional[int] = Field(default=None, primary_key=True)
    task_id: str = Field(index=True, max_length=64, nullable=False)
    task_name: str = Field(max_length=255, nullable=False)
    attempt_number: int = Field(default=3, nullable=False)
    error_message: str = Field(nullable=False)
    payload_reference: Optional[str] = Field(default=None, nullable=True)
    failed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

