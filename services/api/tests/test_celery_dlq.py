"""Integration tests for Celery retries, error sanitization, and Dead Letter Queue (DLQ) quarantine."""

from unittest.mock import MagicMock
import pytest
from sqlmodel import Session, SQLModel, create_engine

from infrastructure.queue.custom_task import TrackFlowTask
from infrastructure.queue.dlq import (
    SQLModelDeadLetterQueueAdapter,
    sanitize_error_message,
)
from infrastructure.queue.models import DeadLetterQueueRecord


@pytest.fixture
def in_memory_db():
    """Create an isolated in-memory SQLite database engine for DLQ testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    SQLModel.metadata.create_all(engine)
    return engine


def test_sanitize_error_message_scrubs_secrets_and_pii() -> None:
    """Verify error sanitizer removes bearer tokens, passwords, and masks emails."""
    raw_error = (
        "Failed database authentication: password=superSecretPassword123 with "
        "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz and contact "
        "engineer.john@domain.com."
    )
    sanitized = sanitize_error_message(raw_error)

    assert "superSecretPassword123" not in sanitized
    assert "password=***REDACTED***" in sanitized
    assert "Bearer ***REDACTED***" in sanitized
    assert "engineer.john@domain.com" not in sanitized
    assert "e***@domain.com" in sanitized


def test_sanitize_error_message_truncates_long_traceback() -> None:
    """Verify error sanitizer caps extremely long tracebacks at 1000 characters."""
    long_error = "Error " * 300
    sanitized = sanitize_error_message(long_error)
    assert len(sanitized) <= 1000
    assert sanitized.endswith("...")


def test_dlq_adapter_persists_and_queries_records(in_memory_db) -> None:
    """Verify DLQ adapter can record a failure and query it back."""
    adapter = SQLModelDeadLetterQueueAdapter(engine=in_memory_db)

    task_id = "test-task-1234-5678"
    task_name = "reporting.trigger_pipeline"
    record_id = adapter.record_failure(
        task_id=task_id,
        task_name=task_name,
        attempt_number=3,
        error_message="Fatal unrecoverable error token=secret_token_abc",
        payload_reference="period_start=2026-10-01",
    )
    assert record_id is not None

    record = adapter.get_record_by_task_id(task_id)
    assert record is not None
    assert record.task_id == task_id
    assert record.attempt_number == 3
    assert "secret_token_abc" not in record.error_message
    assert "token=***REDACTED***" in record.error_message
    assert record.payload_reference == "period_start=2026-10-01"

    records = adapter.list_records(limit=10)
    assert len(records) == 1
    assert records[0].task_id == task_id


def test_trackflow_task_retry_configuration() -> None:
    """Verify TrackFlowTask class attributes declare required retry and ack settings."""
    assert TrackFlowTask.max_retries == 3
    assert TrackFlowTask.retry_backoff is True
    assert TrackFlowTask.acks_late is True
    assert TrackFlowTask.reject_on_worker_lost is True


def test_trackflow_task_on_failure_quarantines_to_dlq(in_memory_db) -> None:
    """Verify on_failure hook triggers DLQ insertion upon retry exhaustion."""
    from infrastructure.queue.celery_app import celery_app

    task = TrackFlowTask()
    task.bind(celery_app)
    task.name = "inventory.list_products"
    task.push_request(retries=3)

    adapter = SQLModelDeadLetterQueueAdapter(engine=in_memory_db)



    # Patch global adapter
    from infrastructure.queue import custom_task

    original_adapter = custom_task.dlq_adapter
    custom_task.dlq_adapter = adapter

    try:
        task.on_failure(
            exc=ValueError("Calculation overflow for password=admin_pass"),
            task_id="failing-task-9999",
            args=("arg1",),
            kwargs={"kwarg1": "val1"},
            einfo=None,
        )

        record = adapter.get_record_by_task_id("failing-task-9999")
        assert record is not None
        assert record.attempt_number == 3
        assert record.task_name == "inventory.list_products"
        assert "admin_pass" not in record.error_message
    finally:
        custom_task.dlq_adapter = original_adapter
