"""Unit tests for NightlyExportRunner service logic."""

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine
from sqlmodel import Session, select

from services.jobs.models import JobExecutionResult, JobRun, JobStatus, init_jobs_db
from services.jobs.runner import NightlyExportRunner, sanitize_error_message


@pytest.fixture
def test_db(tmp_path):
    """Create an isolated SQLite test database engine."""
    db_file = tmp_path / "test_jobs.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    init_jobs_db(engine)

    # Initialize a telemetry_events table for testing exports
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

    return engine


# ---------------------------------------------------------------------------
# US1 Tests (T008, T009)
# ---------------------------------------------------------------------------

def test_export_telemetry_csv_with_events(test_db, tmp_path):
    """Test exporting telemetry events writes a CSV with correct rows and headers."""
    raw_dir = tmp_path / "raw"
    target_date = "2026-10-24"

    # Seed events for target date and another date
    with test_db.connect() as conn:
        conn.exec_driver_sql(
            """
            INSERT INTO telemetry_events (
                event_id, timestamp, session_id, user_id, event_type,
                schema_version, request_id, properties, created_at
            ) VALUES
            ('evt-1', '2026-10-24T10:00:00Z', 'sess-1', 'usr-1', 'order_created', '1.0', 'req-1', '{"amount": 100}', '2026-10-24T10:00:01Z'),
            ('evt-2', '2026-10-24T18:30:00Z', 'sess-2', 'usr-2', 'shipment_dispatched', '1.0', 'req-2', '{"carrier": "DHL"}', '2026-10-24T18:30:01Z'),
            ('evt-3', '2026-10-25T01:00:00Z', 'sess-3', 'usr-3', 'order_created', '1.0', 'req-3', '{"amount": 50}', '2026-10-25T01:00:01Z');
            """
        )
        conn.commit()

    runner = NightlyExportRunner(engine=test_db, raw_data_dir=str(raw_dir))
    csv_path = runner.export_telemetry_csv(target_date)

    assert os.path.exists(csv_path)
    assert Path(csv_path).name == f"telemetry_{target_date}.csv"

    # Verify content
    with open(csv_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]

    # Header + 2 rows for 2026-10-24
    assert len(lines) == 3
    assert lines[0] == "event_id,timestamp,session_id,user_id,event_type,schema_version,request_id,properties,created_at"
    assert "evt-1" in lines[1]
    assert "evt-2" in lines[2]
    assert "evt-3" not in "".join(lines)


def test_export_telemetry_csv_empty_state_headers(test_db, tmp_path):
    """Test exporting for a date with no events creates CSV with headers and 0 data rows."""
    raw_dir = tmp_path / "raw"
    target_date = "2026-10-20"

    runner = NightlyExportRunner(engine=test_db, raw_data_dir=str(raw_dir))
    csv_path = runner.export_telemetry_csv(target_date)

    assert os.path.exists(csv_path)
    with open(csv_path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]

    assert len(lines) == 1
    assert lines[0] == "event_id,timestamp,session_id,user_id,event_type,schema_version,request_id,properties,created_at"


def test_run_downstream_pipeline_arguments_and_success(test_db, tmp_path):
    """Test run_downstream_pipeline formats arguments and returns CompletedProcess."""
    runner = NightlyExportRunner(engine=test_db, raw_data_dir=str(tmp_path))
    target_date = "2026-10-24"

    mock_proc = subprocess.CompletedProcess(
        args=["python", "data/pipelines/pipeline.py"],
        returncode=0,
        stdout="Pipeline finished successfully.",
        stderr="",
    )

    with patch("subprocess.run", return_value=mock_proc) as mock_run:
        result = runner.run_downstream_pipeline(target_date)

        assert result.returncode == 0
        mock_run.assert_called_once()
        called_args = mock_run.call_args[0][0]
        assert "data/pipelines/pipeline.py" in called_args[1]
        assert "--start-date" in called_args
        assert f"{target_date}T00:00:00Z" in called_args
        assert "--end-date" in called_args
        assert f"{target_date}T23:59:59Z" in called_args


def test_run_downstream_pipeline_failure_return_code(test_db, tmp_path):
    """Test run_downstream_pipeline captures non-zero return code."""
    runner = NightlyExportRunner(engine=test_db, raw_data_dir=str(tmp_path))
    target_date = "2026-10-24"

    mock_proc = subprocess.CompletedProcess(
        args=["python", "data/pipelines/pipeline.py"],
        returncode=1,
        stdout="",
        stderr="Database connection failed: FATAL error",
    )

    with patch("subprocess.run", return_value=mock_proc):
        result = runner.run_downstream_pipeline(target_date)
        assert result.returncode == 1
        assert "FATAL error" in result.stderr


# ---------------------------------------------------------------------------
# US2 Tests (T015)
# ---------------------------------------------------------------------------

def test_check_active_lock_and_concurrency_abort(test_db, tmp_path):
    """Test US2: Existing processing record is detected, aborting execution with clean skip."""
    runner = NightlyExportRunner(engine=test_db, raw_data_dir=str(tmp_path))
    target_date = "2026-10-24"

    # Pre-insert an active processing job run
    with Session(test_db) as session:
        active_job = JobRun(
            job_name="nightly_export",
            target_date="2026-10-24",
            status=JobStatus.PROCESSING.value,
            started_at=datetime.now(timezone.utc),
        )
        session.add(active_job)
        session.commit()
        session.refresh(active_job)
        active_id = active_job.id

    # Verify check_active_lock detects it
    detected = runner.check_active_lock()
    assert detected is not None
    assert detected.id == active_id

    # Verify execute aborts with clean skip
    with patch("subprocess.run") as mock_run:
        result = runner.execute(target_date_override=target_date)

        assert result.skipped is True
        assert result.skip_reason == "concurrency_lock_active"
        assert result.run_id == active_id
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# US3 Tests (T020, T021)
# ---------------------------------------------------------------------------

def test_resolve_target_date_default_yesterday(test_db, tmp_path, monkeypatch):
    """Test target date resolution defaults to yesterday in UTC when no override provided."""
    monkeypatch.delenv("TARGET_DATE", raising=False)
    runner = NightlyExportRunner(engine=test_db, raw_data_dir=str(tmp_path))

    expected = (datetime.now(timezone.utc).date() - timedelta(days=1)).strftime("%Y-%m-%d")
    resolved = runner.resolve_target_date()
    assert resolved == expected


def test_resolve_target_date_env_var(test_db, tmp_path, monkeypatch):
    """Test TARGET_DATE environment variable override."""
    monkeypatch.setenv("TARGET_DATE", "2026-10-15")
    runner = NightlyExportRunner(engine=test_db, raw_data_dir=str(tmp_path))

    assert runner.resolve_target_date() == "2026-10-15"


def test_resolve_target_date_cli_precedence(test_db, tmp_path, monkeypatch):
    """Test CLI argument takes precedence over TARGET_DATE env var."""
    monkeypatch.setenv("TARGET_DATE", "2026-10-15")
    runner = NightlyExportRunner(engine=test_db, raw_data_dir=str(tmp_path))

    assert runner.resolve_target_date(override="2026-10-18") == "2026-10-18"


def test_resolve_target_date_invalid_formats(test_db, tmp_path):
    """Test malformed and invalid calendar dates raise ValueError."""
    runner = NightlyExportRunner(engine=test_db, raw_data_dir=str(tmp_path))

    with pytest.raises(ValueError, match="Malformed target date format"):
        runner.resolve_target_date("2026/10/24")

    with pytest.raises(ValueError, match="Malformed target date format"):
        runner.resolve_target_date("invalid-date")

    with pytest.raises(ValueError, match="Invalid calendar date"):
        runner.resolve_target_date("2026-02-31")


def test_check_idempotency_and_snapshot_preservation(test_db, tmp_path):
    """Test US3: Completed target date skips execution and preserves existing CSV snapshot."""
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    target_date = "2026-10-24"

    # Pre-create an existing CSV snapshot with custom content
    csv_file = raw_dir / f"telemetry_{target_date}.csv"
    with open(csv_file, "w", encoding="utf-8") as f:
        f.write("original,audit,content\n1,2,3\n")

    runner = NightlyExportRunner(engine=test_db, raw_data_dir=str(raw_dir))

    # Pre-seed a completed job run
    with Session(test_db) as session:
        completed_job = JobRun(
            job_name="nightly_export",
            target_date=target_date,
            status=JobStatus.COMPLETED.value,
            started_at=datetime.now(timezone.utc),
            finished_at=datetime.now(timezone.utc),
        )
        session.add(completed_job)
        session.commit()
        session.refresh(completed_job)
        completed_id = completed_job.id

    # Verify check_idempotency detects completed run
    detected = runner.check_idempotency(target_date)
    assert detected is not None
    assert detected.id == completed_id

    # Execute runner: should skip execution and NOT touch existing CSV
    with patch("subprocess.run") as mock_run:
        result = runner.execute(target_date_override=target_date)

        assert result.skipped is True
        assert result.skip_reason == "already_completed"
        assert result.status == JobStatus.COMPLETED
        assert result.run_id == completed_id
        mock_run.assert_not_called()

    # Verify CSV file was preserved
    with open(csv_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert content == "original,audit,content\n1,2,3\n"


# ---------------------------------------------------------------------------
# US4 Tests (T027, T028)
# ---------------------------------------------------------------------------

def test_sanitize_error_message_credential_masking():
    """Test sensitive database URLs, passwords, bearer tokens are masked and text is truncated."""
    # DB URL masking
    db_err = "OperationalError: connection to postgresql://admin:SuperSecretPass123@db.supabase.com:5432/trackflow failed"
    sanitized = sanitize_error_message(db_err)
    assert "SuperSecretPass123" not in sanitized
    assert "admin:***@" in sanitized

    # Key-value secret masking
    auth_err = "AuthError: Invalid key token=eyJhbGciOiJIUzI1NiJ9 and password: my-secret-password"
    sanitized_auth = sanitize_error_message(auth_err)
    assert "my-secret-password" not in sanitized_auth
    assert "eyJhbGciOiJIUzI1NiJ9" not in sanitized_auth
    assert "token=***" in sanitized_auth
    assert "password=***" in sanitized_auth

    # Truncation to 500 characters
    long_msg = "Error: " + ("x" * 600)
    truncated = sanitize_error_message(long_msg)
    assert len(truncated) <= 500
    assert truncated.endswith("...")


def test_execute_failure_state_recovery_and_lock_release(test_db, tmp_path):
    """Test US4: Failed pipeline updates status to failed, records error, and releases lock."""
    runner = NightlyExportRunner(engine=test_db, raw_data_dir=str(tmp_path))
    target_date = "2026-10-24"

    # Simulate failing subprocess
    mock_failing_proc = subprocess.CompletedProcess(
        args=["python", "data/pipelines/pipeline.py"],
        returncode=1,
        stdout="",
        stderr="psycopg2.OperationalError: connection failed with password=db-password-secret-123",
    )

    with patch("subprocess.run", return_value=mock_failing_proc):
        result = runner.execute(target_date_override=target_date)

        assert result.status == JobStatus.FAILED
        assert result.pipeline_exit_code == 1
        assert "db-password-secret-123" not in result.error_message
        assert "password=***" in result.error_message

        # Verify database record
        with Session(test_db) as session:
            job_record = session.get(JobRun, result.run_id)
            assert job_record is not None
            assert job_record.status == JobStatus.FAILED.value
            assert job_record.finished_at is not None
            assert "password=***" in job_record.error_message

            # Verify no jobs remain in processing status
            active = runner.check_active_lock()
            assert active is None


def test_cli_malformed_date_returns_code_1(monkeypatch):
    """Test CLI main returns non-zero exit code on malformed date."""
    from scripts.nightly_export import main

    exit_code = main(["--date", "malformed-date"])
    assert exit_code == 1



