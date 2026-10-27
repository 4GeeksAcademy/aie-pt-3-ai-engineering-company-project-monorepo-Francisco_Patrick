"""Nightly telemetry export orchestrator and background job runner."""

from csv import writer as csv_writer
from datetime import datetime, timedelta, timezone
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import List, Optional, Union
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from data.pipelines.models import get_engine
from services.jobs.models import JobExecutionResult, JobRun, JobStatus, init_jobs_db

logger = logging.getLogger("scripts.nightly_export")

CSV_COLUMNS: List[str] = [
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


def sanitize_error_message(exc: Union[Exception, str]) -> str:
    """Mask sensitive credentials, tokens, or connection strings and truncate to 500 characters.

    Args:
        exc: Exception instance or raw error message string.

    Returns:
        Sanitized, credential-masked error string of at most 500 characters.
    """
    raw_message = str(exc) if isinstance(exc, Exception) else (exc or "")

    # Mask database connection strings with passwords (e.g. postgresql://user:pass@host:port/db)
    sanitized = re.sub(
        r"://([^:]+):([^@]+)@",
        r"://\1:***@",
        raw_message,
    )

    # Mask key-value secrets (e.g., password=XYZ, secret_key=XYZ, token=XYZ)
    pattern = re.compile(
        r"(password|token|secret|key|authorization|bearer)\s*[:=]\s*([^\s,;]+)",
        re.IGNORECASE,
    )
    sanitized = pattern.sub(r"\1=***", sanitized)

    # Truncate to maximum 500 characters
    if len(sanitized) > 500:
        sanitized = sanitized[:497] + "..."

    return sanitized


class NightlyExportRunner:
    """Orchestrates daily telemetry snapshot export and executive KPI pipeline execution."""

    def __init__(
        self,
        engine: Optional[Engine] = None,
        raw_data_dir: Optional[str] = None,
        job_name: str = "nightly_export",
    ) -> None:
        """Initialize the orchestrator with database engine and export directory.

        Args:
            engine: SQLAlchemy/SQLModel Engine instance (defaults to shared get_engine()).
            raw_data_dir: Target directory for CSV exports (defaults to 'data/raw').
            job_name: Unique process identifier for concurrency and state tracking.
        """
        self.engine = engine or get_engine()
        self.raw_data_dir = raw_data_dir or os.getenv("RAW_DATA_DIR", "data/raw")
        self.job_name = job_name

        # Ensure job tables exist
        init_jobs_db(self.engine)

    def resolve_target_date(self, override: Optional[str] = None) -> str:
        """Resolve target date in YYYY-MM-DD UTC format from override, env, or UTC yesterday.

        Args:
            override: Optional date string passed via CLI argument.

        Returns:
            Resolved ISO date string formatted as YYYY-MM-DD.

        Raises:
            ValueError: If target date string format is malformed or invalid calendar date.
        """
        candidate = override or os.getenv("TARGET_DATE")
        if candidate:
            candidate = candidate.strip()
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", candidate):
                raise ValueError(
                    f"Malformed target date format: '{candidate}'. Expected YYYY-MM-DD."
                )
            try:
                parsed = datetime.strptime(candidate, "%Y-%m-%d").date()
                return parsed.strftime("%Y-%m-%d")
            except ValueError as err:
                raise ValueError(
                    f"Invalid calendar date: '{candidate}'. Details: {err}"
                ) from err

        yesterday = datetime.now(timezone.utc).date() - timedelta(days=1)
        return yesterday.strftime("%Y-%m-%d")

    def check_active_lock(self) -> Optional[JobRun]:
        """Check if an active processing job currently exists in the database.

        Returns:
            The active JobRun record if currently in 'processing' status, else None.
        """
        with Session(self.engine) as session:
            stmt = (
                select(JobRun)
                .where(JobRun.job_name == self.job_name)
                .where(JobRun.status == JobStatus.PROCESSING.value)
            )
            return session.exec(stmt).first()

    def check_idempotency(self, target_date: str) -> Optional[JobRun]:
        """Check if the target_date has already completed successfully.

        Args:
            target_date: Target cohort date in YYYY-MM-DD format.

        Returns:
            The completed JobRun record if found, else None.
        """
        with Session(self.engine) as session:
            stmt = (
                select(JobRun)
                .where(JobRun.job_name == self.job_name)
                .where(JobRun.target_date == target_date)
                .where(JobRun.status == JobStatus.COMPLETED.value)
            )
            return session.exec(stmt).first()

    def export_telemetry_csv(self, target_date: str) -> str:
        """Export telemetry events for target_date to data/raw/telemetry_YYYY-MM-DD.csv.

        Preserves existing snapshot files without overwriting. Writes column headers
        and zero rows if no events exist for the target date.

        Args:
            target_date: Target cohort date in YYYY-MM-DD format.

        Returns:
            Filesystem path to the exported CSV file.
        """
        os.makedirs(self.raw_data_dir, exist_ok=True)
        csv_filename = f"telemetry_{target_date}.csv"
        csv_path = os.path.join(self.raw_data_dir, csv_filename)

        if os.path.exists(csv_path):
            logger.info(
                "Audit file %s already exists. Preserving existing snapshot.",
                csv_path,
            )
            return csv_path

        logger.info(
            "Exporting telemetry events for %s to %s",
            target_date,
            csv_path,
        )

        start_boundary = f"{target_date}T00:00:00"
        end_boundary = f"{target_date}T23:59:59.999999Z"

        rows: List[tuple] = []
        with self.engine.connect() as conn:
            # Check table existence defensively
            is_sqlite = self.engine.dialect.name == "sqlite"
            check_sql = (
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='telemetry_events'"
                if is_sqlite
                else "SELECT count(*) FROM information_schema.tables WHERE table_name='telemetry_events'"
            )
            table_exists = conn.execute(text(check_sql)).scalar()

            if table_exists and table_exists > 0:
                query = text(
                    """
                    SELECT event_id, timestamp, session_id, user_id, event_type,
                           schema_version, request_id, properties, created_at
                    FROM telemetry_events
                    WHERE timestamp >= :start_time AND timestamp <= :end_time
                    ORDER BY timestamp ASC
                    """
                )
                result = conn.execute(
                    query,
                    {"start_time": start_boundary, "end_time": end_boundary},
                )
                rows = result.fetchall()

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv_writer(f)
            writer.writerow(CSV_COLUMNS)
            for row in rows:
                writer.writerow(list(row))

        return csv_path

    def run_downstream_pipeline(self, target_date: str) -> subprocess.CompletedProcess:
        """Execute downstream KPI pipeline as an isolated subprocess for target_date.

        Args:
            target_date: Target cohort date in YYYY-MM-DD format.

        Returns:
            subprocess.CompletedProcess containing returncode, stdout, and stderr.
        """
        start_date_param = f"{target_date}T00:00:00Z"
        end_date_param = f"{target_date}T23:59:59Z"

        pipeline_script = "data/pipelines/pipeline.py"
        cmd = [
            sys.executable,
            pipeline_script,
            "--start-date",
            start_date_param,
            "--end-date",
            end_date_param,
        ]

        logger.info(
            "Spawning downstream KPI pipeline subprocess for target date %s",
            target_date,
        )

        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
            env=os.environ.copy(),
        )

    def execute(
        self,
        target_date_override: Optional[str] = None,
        dry_run: bool = False,
    ) -> JobExecutionResult:
        """Execute the end-to-end nightly export orchestration cycle.

        Args:
            target_date_override: Optional date string override (YYYY-MM-DD).
            dry_run: If True, resolves date and checks locks without writing files or running pipeline.

        Returns:
            JobExecutionResult reflecting execution status and metadata.
        """
        start_time = datetime.now(timezone.utc)
        target_date = self.resolve_target_date(target_date_override)
        logger.info(
            "Nightly telemetry export initiated. Target date: %s",
            target_date,
        )

        # 1. Concurrency Lock Check
        active_lock = self.check_active_lock()
        if active_lock is not None:
            logger.info(
                "Active job '%s' currently processing (Run ID: %s). Skipping duplicate execution.",
                self.job_name,
                active_lock.id,
            )
            return JobExecutionResult(
                status=JobStatus.PROCESSING,
                target_date=target_date,
                run_id=active_lock.id,
                skipped=True,
                skip_reason="concurrency_lock_active",
            )

        # 2. Idempotency Check
        completed_run = self.check_idempotency(target_date)
        if completed_run is not None:
            logger.info(
                "Target date %s has already completed successfully (Run ID: %s). Skipping export.",
                target_date,
                completed_run.id,
            )
            csv_path = os.path.join(self.raw_data_dir, f"telemetry_{target_date}.csv")
            return JobExecutionResult(
                status=JobStatus.COMPLETED,
                target_date=target_date,
                run_id=completed_run.id,
                skipped=True,
                skip_reason="already_completed",
                csv_path=csv_path if os.path.exists(csv_path) else None,
            )

        if dry_run:
            logger.info("Dry-run mode enabled. Skipping execution.")
            return JobExecutionResult(
                status=JobStatus.PENDING,
                target_date=target_date,
                skipped=True,
                skip_reason="dry_run",
            )

        # 3. Create active 'processing' record (lock acquisition)
        job_run = JobRun(
            job_name=self.job_name,
            target_date=target_date,
            status=JobStatus.PROCESSING.value,
            started_at=start_time,
        )
        with Session(self.engine) as session:
            session.add(job_run)
            session.commit()
            session.refresh(job_run)
            run_id = job_run.id

        # 4. Processing Lifecycle with Defensive Error Handling
        try:
            csv_path = self.export_telemetry_csv(target_date)
            proc = self.run_downstream_pipeline(target_date)

            if proc.returncode != 0:
                err_detail = proc.stderr or proc.stdout or f"Subprocess exited with code {proc.returncode}"
                raise RuntimeError(
                    f"Downstream KPI pipeline failed with exit code {proc.returncode}: {err_detail}"
                )

            logger.info("Downstream KPI pipeline completed successfully with exit code 0")

            finish_time = datetime.now(timezone.utc)
            duration_s = (finish_time - start_time).total_seconds()
            with Session(self.engine) as session:
                persisted = session.get(JobRun, run_id)
                if persisted:
                    persisted.status = JobStatus.COMPLETED.value
                    persisted.finished_at = finish_time
                    session.add(persisted)
                    session.commit()

            logger.info(
                "Nightly telemetry export completed successfully for %s. Duration: %.2fs",
                target_date,
                duration_s,
            )

            return JobExecutionResult(
                status=JobStatus.COMPLETED,
                target_date=target_date,
                run_id=run_id,
                csv_path=csv_path,
                pipeline_exit_code=0,
            )

        except Exception as exc:
            finish_time = datetime.now(timezone.utc)
            sanitized_err = sanitize_error_message(exc)
            logger.error(
                "Nightly export failed for %s: %s",
                target_date,
                sanitized_err,
            )

            with Session(self.engine) as session:
                persisted = session.get(JobRun, run_id)
                if persisted:
                    persisted.status = JobStatus.FAILED.value
                    persisted.finished_at = finish_time
                    persisted.error_message = sanitized_err
                    session.add(persisted)
                    session.commit()

            return JobExecutionResult(
                status=JobStatus.FAILED,
                target_date=target_date,
                run_id=run_id,
                pipeline_exit_code=getattr(exc, "returncode", 1),
                error_message=sanitized_err,
            )


__all__ = [
    "NightlyExportRunner",
    "sanitize_error_message",
]
