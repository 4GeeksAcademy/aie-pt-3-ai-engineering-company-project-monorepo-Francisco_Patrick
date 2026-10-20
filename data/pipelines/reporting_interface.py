"""Boundary interface between reporting presentation layer and pipeline persistence/execution.

Adheres to Monorepo Constitution Principle I:
- No inline ETL queries inside route controllers.
- Routes delegate 100% of pipeline operations to this interface module.
"""

from datetime import datetime
import os
import sys
from typing import Any, Dict, List, Optional
from uuid import UUID

_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from sqlmodel import Session, col, desc, select

from data.pipelines.models import (
    ExecutiveKpiSnapshot,
    PipelineExecutionLog,
    get_engine,
    get_session,
    init_reporting_db,
)


class PipelineActiveConflictError(Exception):
    """Raised when triggering a pipeline run while an active run is in progress."""

    pass


def get_pipeline_status(session: Optional[Session] = None) -> Dict[str, Any]:
    """Retrieve operational status and metadata of the latest pipeline execution.

    Returns:
        Dict conforming to PipelineStatusResponse contract:
        - latest_run: Optional dict of the latest PipelineExecutionLog
        - is_running: True if an execution currently has status 'RUNNING'
        - healthy: True if latest run completed with status 'SUCCESS'
    """
    init_reporting_db()
    sess = session or get_session()
    close_sess = session is None

    try:
        # Check if any run is currently RUNNING
        active_run = sess.exec(
            select(PipelineExecutionLog)
            .where(PipelineExecutionLog.status == "RUNNING")
            .order_by(desc(PipelineExecutionLog.started_at))
        ).first()

        latest_run = sess.exec(
            select(PipelineExecutionLog).order_by(desc(PipelineExecutionLog.started_at))
        ).first()

        is_running = active_run is not None
        healthy = latest_run is not None and latest_run.status == "SUCCESS"

        latest_run_dict = None
        if latest_run is not None:
            latest_run_dict = {
                "run_id": str(latest_run.run_id),
                "flow_name": latest_run.flow_name,
                "started_at": latest_run.started_at.isoformat() if latest_run.started_at else None,
                "ended_at": latest_run.ended_at.isoformat() if latest_run.ended_at else None,
                "records_processed": latest_run.records_processed,
                "status": latest_run.status,
                "error_details": latest_run.error_details,
            }

        return {
            "latest_run": latest_run_dict,
            "is_running": is_running,
            "healthy": healthy,
        }
    finally:
        if close_sess:
            sess.close()


def trigger_pipeline_run(
    period_start: Optional[datetime] = None,
    period_end: Optional[datetime] = None,
    session: Optional[Session] = None,
) -> Dict[str, Any]:
    """Trigger an execution run of the executive performance pipeline.

    Args:
        period_start: Optional start of the reporting window in UTC.
        period_end: Optional end of the reporting window in UTC.
        session: Optional SQLModel session.

    Returns:
        Dict conforming to PipelineTriggerResponse:
        - run_id: UUID string
        - status: 'INITIATED' or 'QUEUED'
        - message: Confirmation message

    Raises:
        PipelineActiveConflictError: If a pipeline run is already RUNNING.
    """
    init_reporting_db()
    sess = session or get_session()
    close_sess = session is None

    try:
        # Check active conflict
        active_run = sess.exec(
            select(PipelineExecutionLog).where(PipelineExecutionLog.status == "RUNNING")
        ).first()
        if active_run is not None:
            raise PipelineActiveConflictError(
                f"Pipeline run '{active_run.run_id}' is already in RUNNING state."
            )

        # Lazy import to avoid circular dependency
        from data.pipelines.pipeline import executive_performance_pipeline_flow

        # Run or trigger the flow
        state = executive_performance_pipeline_flow(
            period_start=period_start,
            period_end=period_end,
            return_state=True,
        )

        # Retrieve the run_id from state or execution log
        latest_run = sess.exec(
            select(PipelineExecutionLog).order_by(desc(PipelineExecutionLog.started_at))
        ).first()

        run_id = str(latest_run.run_id) if latest_run else str(state.state_details.flow_run_id)

        return {
            "run_id": run_id,
            "status": "INITIATED",
            "message": "Executive performance pipeline run executed successfully.",
        }
    finally:
        if close_sess:
            sess.close()


def get_executive_kpis(
    country: Optional[str] = "GLOBAL",
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    session: Optional[Session] = None,
) -> Dict[str, Any]:
    """Retrieve pre-computed weekly executive KPI snapshots.

    Args:
        country: Optional filter by scope: 'US', 'ES', or 'GLOBAL'. Defaults to 'GLOBAL'.
        start_date: Optional filter for period_start >= start_date.
        end_date: Optional filter for period_end <= end_date.
        session: Optional SQLModel session.

    Returns:
        Dict conforming to ExecutiveKpisResponse:
        - count: int
        - snapshots: List of snapshot dicts
    """
    init_reporting_db()
    sess = session or get_session()
    close_sess = session is None

    try:
        query = select(ExecutiveKpiSnapshot)

        if country:
            query = query.where(ExecutiveKpiSnapshot.country == country.upper())

        if start_date:
            query = query.where(ExecutiveKpiSnapshot.period_start >= start_date)

        if end_date:
            query = query.where(ExecutiveKpiSnapshot.period_end <= end_date)

        query = query.order_by(desc(ExecutiveKpiSnapshot.period_start))

        results = sess.exec(query).all()

        snapshots: List[Dict[str, Any]] = []
        for r in results:
            snapshots.append(
                {
                    "snapshot_id": str(r.snapshot_id),
                    "period_start": r.period_start.isoformat(),
                    "period_end": r.period_end.isoformat(),
                    "country": r.country,
                    "shipments_volume": r.shipments_volume,
                    "on_time_delivery_rate": float(r.on_time_delivery_rate),
                    "operational_cost_eur": float(r.operational_cost_eur),
                    "returns_rate": float(r.returns_rate),
                    "customer_satisfaction_score": float(r.customer_satisfaction_score),
                    "generated_at": r.generated_at.isoformat(),
                }
            )

        return {
            "count": len(snapshots),
            "snapshots": snapshots,
        }
    finally:
        if close_sess:
            sess.close()


__all__ = [
    "PipelineActiveConflictError",
    "get_executive_kpis",
    "get_pipeline_status",
    "trigger_pipeline_run",
]
