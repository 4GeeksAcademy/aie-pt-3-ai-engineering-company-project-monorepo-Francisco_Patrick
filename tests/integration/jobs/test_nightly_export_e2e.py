"""End-to-end integration tests for nightly export orchestrator."""

from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
from unittest.mock import patch
import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, select

from data.pipelines.models import init_reporting_db, set_engine
from services.jobs.models import JobRun, JobStatus, init_jobs_db
from services.jobs.runner import NightlyExportRunner


@pytest.fixture
def integration_env(tmp_path, monkeypatch):
    """Set up isolated database and filesystem environment for integration testing."""
    test_db_path = tmp_path / "integration_inventory.db"
    engine = create_engine(
        f"sqlite:///{test_db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    set_engine(engine)
    init_jobs_db(engine)
    init_reporting_db(engine)

    # Set up telemetry_events table
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
        # Seed telemetry events for 2026-10-24
        conn.exec_driver_sql(
            """
            INSERT INTO telemetry_events (
                event_id, timestamp, session_id, user_id, event_type,
                schema_version, request_id, properties, created_at
            ) VALUES
            ('evt-int-1', '2026-10-24T08:00:00Z', 'sess-1', 'user-1', 'outbound_order_fulfilled', '1.0', 'req-1', '{"orderId": "ord-1", "warehouseCode": "US-LAX-01", "totalCostEur": 15.5}', '2026-10-24T08:00:01Z'),
            ('evt-int-2', '2026-10-24T14:30:00Z', 'sess-2', 'user-2', 'shipment_tracking_updated', '1.0', 'req-2', '{"orderId": "ord-1", "status": "DELIVERED", "isDelivered": true, "onTime": true}', '2026-10-24T14:30:01Z');
            """
        )
        conn.commit()

    raw_dir = tmp_path / "raw"
    monkeypatch.setenv("RAW_DATA_DIR", str(raw_dir))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{test_db_path}")

    return {
        "engine": engine,
        "raw_dir": raw_dir,
    }


def test_us1_end_to_end_export_and_completion(integration_env):
    """Test US1: Full execution lifecycle creating CSV snapshot and completed JobRun record."""
    engine = integration_env["engine"]
    raw_dir = integration_env["raw_dir"]
    target_date = "2026-10-24"

    runner = NightlyExportRunner(engine=engine, raw_data_dir=str(raw_dir))

    # Mock subprocess execution to simulate successful pipeline run
    mock_subprocess = subprocess.CompletedProcess(
        args=["python", "data/pipelines/pipeline.py"],
        returncode=0,
        stdout="Executive pipeline completed successfully",
        stderr="",
    )

    with patch("subprocess.run", return_value=mock_subprocess) as mock_run:
        result = runner.execute(target_date_override=target_date)

        # Check result
        assert result.status == JobStatus.COMPLETED
        assert result.target_date == target_date
        assert result.skipped is False
        assert result.pipeline_exit_code == 0
        assert result.run_id is not None

        # Verify CSV snapshot created
        csv_file = raw_dir / f"telemetry_{target_date}.csv"
        assert csv_file.exists()
        with open(csv_file, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
        assert len(lines) == 3
        assert "evt-int-1" in lines[1]
        assert "evt-int-2" in lines[2]

        # Verify JobRun database record
        with Session(engine) as session:
            job_record = session.get(JobRun, result.run_id)
            assert job_record is not None
            assert job_record.status == JobStatus.COMPLETED.value
            assert job_record.target_date == target_date
            assert job_record.started_at is not None
            assert job_record.finished_at is not None
            assert job_record.error_message is None


def test_us2_concurrency_locking_prevents_duplicate_run(integration_env):
    """Test US2: Secondary execution detects active lock, skips cleanly, and does not spawn pipeline."""
    engine = integration_env["engine"]
    raw_dir = integration_env["raw_dir"]
    target_date = "2026-10-24"

    runner = NightlyExportRunner(engine=engine, raw_data_dir=str(raw_dir))

    # Pre-seed an active processing run
    with Session(engine) as session:
        lock_run = JobRun(
            job_name="nightly_export",
            target_date="2026-10-24",
            status=JobStatus.PROCESSING.value,
            started_at=datetime.now(timezone.utc),
        )
        session.add(lock_run)
        session.commit()
        session.refresh(lock_run)
        active_id = lock_run.id

    with patch("subprocess.run") as mock_run:
        result = runner.execute(target_date_override=target_date)

        assert result.skipped is True
        assert result.skip_reason == "concurrency_lock_active"
        assert result.run_id == active_id
        mock_run.assert_not_called()

        # Verify only the pre-seeded record exists and is untouched
        with Session(engine) as session:
            all_runs = session.exec(select(JobRun)).all()
            assert len(all_runs) == 1
            assert all_runs[0].id == active_id
            assert all_runs[0].status == JobStatus.PROCESSING.value
            assert all_runs[0].started_at is not None
            assert all_runs[0].finished_at is None
            assert all_runs[0].error_message is None


def test_us3_idempotency_and_historical_backfill(integration_env):
    """Test US3: Backfill with custom date works and second run for same date skips idempotently."""
    engine = integration_env["engine"]
    raw_dir = integration_env["raw_dir"]
    backfill_date = "2026-10-24"

    runner = NightlyExportRunner(engine=engine, raw_data_dir=str(raw_dir))

    mock_subprocess = subprocess.CompletedProcess(
        args=["python", "data/pipelines/pipeline.py"],
        returncode=0,
        stdout="Backfill run finished",
        stderr="",
    )

    # 1. First execution for backfill date
    with patch("subprocess.run", return_value=mock_subprocess) as mock_run:
        res1 = runner.execute(target_date_override=backfill_date)
        assert res1.status == JobStatus.COMPLETED
        assert res1.skipped is False
        assert mock_run.call_count == 1

    csv_file = raw_dir / f"telemetry_{backfill_date}.csv"
    assert csv_file.exists()
    file_mtime = csv_file.stat().st_mtime

    # 2. Second execution for identical date (must skip idempotently)
    with patch("subprocess.run") as mock_run_2:
        res2 = runner.execute(target_date_override=backfill_date)
        assert res2.status == JobStatus.COMPLETED
        assert res2.skipped is True
        assert res2.skip_reason == "already_completed"
        assert res2.run_id == res1.run_id
        mock_run_2.assert_not_called()

    # CSV snapshot was preserved and not overwritten
    assert csv_file.stat().st_mtime == file_mtime


def test_us4_failure_recovery_and_lock_clearance(integration_env):
    """Test US4: End-to-end failure transitions job to failed, clears lock, and records sanitized error."""
    engine = integration_env["engine"]
    raw_dir = integration_env["raw_dir"]
    target_date = "2026-10-24"

    runner = NightlyExportRunner(engine=engine, raw_data_dir=str(raw_dir))

    # Simulate failing subprocess
    mock_subprocess = subprocess.CompletedProcess(
        args=["python", "data/pipelines/pipeline.py"],
        returncode=1,
        stdout="",
        stderr="Pipeline task error: access_token=secret_jwt_xyz failed to connect to warehouse",
    )

    with patch("subprocess.run", return_value=mock_subprocess):
        result = runner.execute(target_date_override=target_date)

        assert result.status == JobStatus.FAILED
        assert result.pipeline_exit_code == 1
        assert "secret_jwt_xyz" not in result.error_message

        # Verify database state: no lock stranded in processing
        with Session(engine) as session:
            job_record = session.get(JobRun, result.run_id)
            assert job_record is not None
            assert job_record.status == JobStatus.FAILED.value
            assert job_record.started_at is not None
            assert job_record.finished_at is not None
            assert job_record.error_message is not None
            assert "secret_jwt_xyz" not in job_record.error_message

            # Active lock check must return None
            active_lock = runner.check_active_lock()
            assert active_lock is None


