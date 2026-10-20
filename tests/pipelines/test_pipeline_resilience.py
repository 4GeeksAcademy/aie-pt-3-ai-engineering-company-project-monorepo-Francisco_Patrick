"""Resilience, caching, idempotency, and partial failure tolerance tests."""

from datetime import datetime, timedelta, timezone
import json
import pytest
from sqlmodel import Session, create_engine, select

from data.pipelines.models import (
    ExecutiveKpiSnapshot,
    PipelineExecutionLog,
    init_reporting_db,
    set_engine,
)
from data.pipelines.pipeline import (
    executive_performance_pipeline_flow,
    extract_telemetry_and_domain_data,
    load_reporting_snapshots,
    notify_pipeline_status,
    transform_executive_kpis,
)


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    """Isolate database per test run with a temporary SQLite database."""
    test_db_path = tmp_path / "test_resilience.db"
    engine = create_engine(
        f"sqlite:///{test_db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    set_engine(engine)

    init_reporting_db(engine)

    with engine.connect() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS telemetry_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                session_id TEXT NOT NULL,
                user_id TEXT,
                event_type TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                request_id TEXT NOT NULL,
                properties TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.commit()

    yield engine


def test_optional_task_failure_tolerance(setup_test_db, monkeypatch):
    """Verify that an exception in notify_pipeline_status does not abort the main flow."""
    engine = setup_test_db

    # Invalidate or cause notify_pipeline_status to raise an error
    def faulty_notify(*args, **kwargs):
        raise RuntimeError("Simulated notification service outage (HTTP 503)")

    monkeypatch.setattr(
        "data.pipelines.pipeline.send_notification_webhook",
        faulty_notify,
    )

    now = datetime.now(timezone.utc)
    flow_state = executive_performance_pipeline_flow(
        period_start=now - timedelta(days=7),
        period_end=now,
        return_state=True,
    )

    # Primary ETL must still succeed
    assert flow_state.is_completed()

    with Session(engine) as session:
        logs = session.exec(select(PipelineExecutionLog)).all()
        assert len(logs) == 1
        assert logs[0].status == "SUCCESS"


def test_idempotency_consecutive_runs(setup_test_db):
    """Verify that running the pipeline twice for the same window leaves exactly 3 rows."""
    engine = setup_test_db
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=7)
    end = now

    # Run 1
    state1 = executive_performance_pipeline_flow(
        period_start=start,
        period_end=end,
        return_state=True,
    )
    assert state1.is_completed()

    # Run 2 with identical window
    state2 = executive_performance_pipeline_flow(
        period_start=start,
        period_end=end,
        return_state=True,
    )
    assert state2.is_completed()

    with Session(engine) as session:
        snapshots = session.exec(select(ExecutiveKpiSnapshot)).all()
        # Exactly 3 snapshots (US, ES, GLOBAL), not 6
        assert len(snapshots) == 3

        logs = session.exec(select(PipelineExecutionLog)).all()
        assert len(logs) == 2
        for log in logs:
            assert log.status == "SUCCESS"


def test_caching_and_retries():
    """Verify task retry configurations and caching properties."""
    # Check extraction task retries
    assert hasattr(extract_telemetry_and_domain_data, "retries")
    assert extract_telemetry_and_domain_data.retries == 3
    assert extract_telemetry_and_domain_data.retry_delay_seconds == 10

    # Check load task retries
    assert hasattr(load_reporting_snapshots, "retries")
    assert load_reporting_snapshots.retries == 3
    assert load_reporting_snapshots.retry_delay_seconds == 10

    # Check transform task cache configuration
    assert hasattr(transform_executive_kpis, "cache_key_fn")
    assert transform_executive_kpis.cache_key_fn is not None
    assert transform_executive_kpis.cache_expiration == timedelta(hours=24)


def test_audit_logging_and_atomic_rollback(setup_test_db, monkeypatch):
    """Verify that database operations roll back on error and log FAILED state."""
    engine = setup_test_db

    # Invalidate load by injecting failure in commit
    def faulty_load(*args, **kwargs):
        raise ValueError("Simulated database constraint failure during load")

    monkeypatch.setattr(
        "data.pipelines.pipeline.execute_snapshot_upsert",
        faulty_load,
    )

    now = datetime.now(timezone.utc)
    flow_state = executive_performance_pipeline_flow(
        period_start=now - timedelta(days=7),
        period_end=now,
        return_state=True,
    )

    assert flow_state.is_failed()

    with Session(engine) as session:
        # Snapshots should be empty due to rollback
        snapshots = session.exec(select(ExecutiveKpiSnapshot)).all()
        assert len(snapshots) == 0

        # Execution log should record FAILED
        logs = session.exec(select(PipelineExecutionLog)).all()
        assert len(logs) == 1
        assert logs[0].status == "FAILED"
        assert logs[0].error_details is not None
        assert "Simulated database constraint failure" in logs[0].error_details
