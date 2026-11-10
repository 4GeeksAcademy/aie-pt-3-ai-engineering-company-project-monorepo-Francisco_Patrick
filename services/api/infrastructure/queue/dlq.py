"""Dead Letter Queue (DLQ) persistence adapter and error sanitization."""

import re
from abc import ABC, abstractmethod
from typing import List, Optional, Union
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from infrastructure.persistence.sqlmodel.client import get_engine
from infrastructure.queue.models import DeadLetterQueueRecord


def sanitize_error_message(error: Union[str, Exception, None]) -> str:
    """Sanitize error messages to scrub PII, authorization tokens, passwords, and secrets.

    Args:
        error: Raw exception instance or string message.

    Returns:
        Sanitized, redacted error message truncated to safe length.
    """
    if error is None:
        return "Unknown error"

    text = str(error)

    # Redact Bearer tokens
    text = re.sub(
        r"(?i)bearer\s+[a-zA-Z0-9_\-\.]+",
        "Bearer ***REDACTED***",
        text,
    )

    # Redact password / secret key-value patterns
    text = re.sub(
        r"(?i)(password|passwd|secret|token|api_key)\s*[:=]\s*['\"]?[^\s,'\"]+['\"]?",
        r"\1=***REDACTED***",
        text,
    )

    # Mask email addresses
    def mask_email(match: re.Match[str]) -> str:
        email = match.group(0)
        parts = email.split("@")
        if len(parts) == 2 and len(parts[0]) > 1:
            return f"{parts[0][0]}***@{parts[1]}"
        return "***REDACTED_EMAIL***"

    text = re.sub(
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
        mask_email,
        text,
    )

    # Truncate to maximum 1000 characters
    if len(text) > 1000:
        text = text[:997] + "..."

    return text.strip()


class DeadLetterQueuePort(ABC):
    """Abstract port interface for dead letter queue persistence operations."""

    @abstractmethod
    def record_failure(
        self,
        task_id: str,
        task_name: str,
        attempt_number: int,
        error_message: str,
        payload_reference: Optional[str] = None,
    ) -> int:
        """Persist a failed task execution record to the Dead Letter Queue."""
        pass

    @abstractmethod
    def list_records(
        self,
        limit: int = 50,
        offset: int = 0,
        task_name: Optional[str] = None,
    ) -> List[DeadLetterQueueRecord]:
        """Query quarantined task failure records for inspection."""
        pass

    @abstractmethod
    def get_record_by_task_id(
        self,
        task_id: str,
    ) -> Optional[DeadLetterQueueRecord]:
        """Retrieve a specific quarantined record by task UUID."""
        pass


class SQLModelDeadLetterQueueAdapter(DeadLetterQueuePort):
    """SQLModel/SQLAlchemy implementation of DeadLetterQueuePort."""

    def __init__(self, engine: Optional[Engine] = None) -> None:
        self._engine = engine

    def _get_engine(self) -> Engine:
        return self._engine if self._engine is not None else get_engine()

    def record_failure(
        self,
        task_id: str,
        task_name: str,
        attempt_number: int,
        error_message: str,
        payload_reference: Optional[str] = None,
    ) -> int:
        """Persist a failed task execution record with sanitized error message."""
        sanitized_msg = sanitize_error_message(error_message)
        record = DeadLetterQueueRecord(
            task_id=task_id,
            task_name=task_name,
            attempt_number=attempt_number,
            error_message=sanitized_msg,
            payload_reference=payload_reference,
        )

        with Session(self._get_engine()) as session:
            session.add(record)
            session.commit()
            session.refresh(record)
            assert record.id is not None
            return record.id

    def list_records(
        self,
        limit: int = 50,
        offset: int = 0,
        task_name: Optional[str] = None,
    ) -> List[DeadLetterQueueRecord]:
        """Query quarantined task failure records ordered by failed_at descending."""
        with Session(self._get_engine()) as session:
            stmt = select(DeadLetterQueueRecord)
            if task_name:
                stmt = stmt.where(DeadLetterQueueRecord.task_name == task_name)
            stmt = (
                stmt.order_by(DeadLetterQueueRecord.failed_at.desc())
                .offset(offset)
                .limit(limit)
            )
            return list(session.exec(stmt).all())

    def get_record_by_task_id(
        self,
        task_id: str,
    ) -> Optional[DeadLetterQueueRecord]:
        """Retrieve record for a specific task UUID."""
        with Session(self._get_engine()) as session:
            stmt = (
                select(DeadLetterQueueRecord)
                .where(DeadLetterQueueRecord.task_id == task_id)
                .order_by(DeadLetterQueueRecord.failed_at.desc())
            )
            return session.exec(stmt).first()


# Global default DLQ adapter instance
dlq_adapter = SQLModelDeadLetterQueueAdapter()

