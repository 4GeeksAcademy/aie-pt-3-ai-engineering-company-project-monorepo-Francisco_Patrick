"""Executive Business Performance Data Pipeline.

Orchestrated using Prefect 3.x.
Execution Schedule: Weekly on Mondays at 06:00 UTC.
Target Audience: Executive Leadership (CEO Daniel Espinoza, CTO Andrés Kim).

CLI Usage:
    # Run pipeline with default trailing 7-day calendar window:
    python data/pipelines/pipeline.py

    # Run pipeline with custom ISO date window:
    python data/pipelines/pipeline.py --start-date 2026-10-12T00:00:00Z --end-date 2026-10-18T23:59:59Z
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import sys

# Ensure repository root is on sys.path when invoked directly as a script
_repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import numpy as np
import pandas as pd
from prefect import flow, task
from sqlalchemy import text
from sqlmodel import Session, select

from data.pipelines.models import (
    ExecutiveKpiSnapshot,
    PipelineExecutionLog,
    get_engine,
    get_session,
    init_reporting_db,
)

logger = logging.getLogger("data.pipelines.pipeline")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def get_default_reporting_window() -> tuple[datetime, datetime]:
    """Calculate default reporting window: preceding Monday 00:00:00 UTC to Sunday 23:59:59 UTC."""
    now = datetime.now(timezone.utc)
    # Days since last Sunday (weekday(): Monday is 0, Sunday is 6)
    days_since_sunday = (now.weekday() + 1) % 7
    if days_since_sunday == 0:
        days_since_sunday = 7
    last_sunday = (now - timedelta(days=days_since_sunday)).replace(
        hour=23, minute=59, second=59, microsecond=999999
    )
    preceding_monday = (last_sunday - timedelta(days=6)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return preceding_monday, last_sunday


def sanitize_error_message(exc: Exception) -> str:
    """Sanitize error message to prevent leaking credentials, internal paths, or tokens."""
    msg = str(exc)
    # Redact common secrets patterns
    for sensitive in ["password", "token", "secret", "key"]:
        if sensitive in msg.lower():
            return f"Database/Execution error occurred: {type(exc).__name__}"
    return msg[:500]


# ---------------------------------------------------------------------------
# Stage 1: Extraction Task
# ---------------------------------------------------------------------------

@task(
    name="extract_telemetry_and_domain_data",
    retries=3,
    retry_delay_seconds=10,
)
def extract_telemetry_and_domain_data(
    period_start: datetime,
    period_end: datetime,
) -> Dict[str, pd.DataFrame]:
    """Extract raw telemetry events and domain operational records within watermark bounds.

    Args:
        period_start: Start of reporting period (inclusive).
        period_end: End of reporting period (inclusive).

    Returns:
        Dict mapping entity names to pandas DataFrames ('orders', 'tracking', 'returns', 'cx').
    """
    engine = get_engine()
    start_iso = period_start.isoformat()
    end_iso = period_end.isoformat()

    orders_records: List[Dict[str, Any]] = []
    tracking_records: List[Dict[str, Any]] = []
    returns_records: List[Dict[str, Any]] = []
    cx_records: List[Dict[str, Any]] = []

    with engine.connect() as conn:
        # Check if telemetry_events table exists
        table_check = conn.execute(
            text(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='telemetry_events'"
                if engine.dialect.name == "sqlite"
                else "SELECT count(*) FROM information_schema.tables WHERE table_name='telemetry_events'"
            )
        ).scalar()

        if table_check and table_check > 0:
            query = text(
                """
                SELECT event_id, timestamp, event_type, properties
                FROM telemetry_events
                WHERE timestamp >= :start_time AND timestamp <= :end_time
                  AND event_type IN (
                      'outbound_order_fulfilled',
                      'shipment_tracking_updated',
                      'carrier_recommendation_selected',
                      'return_request_evaluated',
                      'return_item_inspected',
                      'cx_inquiry_resolved'
                  )
                """
            )
            rows = conn.execute(query, {"start_time": start_iso, "end_time": end_iso}).fetchall()

            for row in rows:
                ev_id, ts, ev_type, props_raw = row[0], row[1], row[2], row[3]
                if isinstance(props_raw, str):
                    try:
                        props = json.loads(props_raw)
                    except Exception:
                        props = {}
                elif isinstance(props_raw, dict):
                    props = props_raw
                else:
                    props = {}

                if ev_type in ("outbound_order_fulfilled", "carrier_recommendation_selected"):
                    orders_records.append({
                        "order_id": props.get("orderId", str(ev_id)),
                        "warehouse_code": props.get("warehouseCode", "US-LAX-01"),
                        "total_cost_eur": float(props.get("totalCostEur", props.get("estimatedCostEur", 0.0))),
                        "destination_country": props.get("destinationCountry", "GLOBAL"),
                        "timestamp": ts,
                    })
                elif ev_type == "shipment_tracking_updated":
                    tracking_records.append({
                        "tracking_number_hash": props.get("trackingNumberHash", str(ev_id)),
                        "origin_warehouse": props.get("originWarehouse", "US-LAX-01"),
                        "timestamp": ts,
                        "is_delivered": props.get("isDelivered", True),
                        "is_delivered_on_time": 1.0 if props.get("isDeliveredOnTime", True) else 0.0,
                    })
                elif ev_type in ("return_request_evaluated", "return_item_inspected"):
                    returns_records.append({
                        "return_id": props.get("returnId", str(ev_id)),
                        "warehouse_code": props.get("warehouseCode", "US-LAX-01"),
                        "timestamp": ts,
                    })
                elif ev_type == "cx_inquiry_resolved":
                    cx_records.append({
                        "ticket_id": props.get("ticketId", str(ev_id)),
                        "warehouse_code": props.get("warehouseCode", "US-LAX-01"),
                        "csat_rating": float(props.get("csatRating", 5.0)),
                        "first_contact_resolution": 1.0 if props.get("firstContactResolution", True) else 0.0,
                        "timestamp": ts,
                    })

    df_orders = pd.DataFrame(orders_records) if orders_records else pd.DataFrame(
        columns=["order_id", "warehouse_code", "total_cost_eur", "destination_country", "timestamp"]
    )
    df_tracking = pd.DataFrame(tracking_records) if tracking_records else pd.DataFrame(
        columns=["tracking_number_hash", "origin_warehouse", "timestamp", "is_delivered", "is_delivered_on_time"]
    )
    df_returns = pd.DataFrame(returns_records) if returns_records else pd.DataFrame(
        columns=["return_id", "warehouse_code", "timestamp"]
    )
    df_cx = pd.DataFrame(cx_records) if cx_records else pd.DataFrame(
        columns=["ticket_id", "warehouse_code", "csat_rating", "first_contact_resolution", "timestamp"]
    )

    return {
        "orders": df_orders,
        "tracking": df_tracking,
        "returns": df_returns,
        "cx": df_cx,
    }


# ---------------------------------------------------------------------------
# Stage 2: Transformation & Caching Task
# ---------------------------------------------------------------------------

import hashlib

def kpi_transformation_cache_key(context: Any, parameters: Dict[str, Any]) -> str:
    """Compute deterministic cache key based on extraction window and DataFrame signatures."""
    period_start = str(parameters.get("period_start", ""))
    period_end = str(parameters.get("period_end", ""))
    raw_data = parameters.get("raw_data", {})
    counts_sig = ",".join(f"{k}_{len(v)}" for k, v in sorted(raw_data.items()))
    raw_sig = f"kpi_transform_{period_start}_{period_end}_{counts_sig}"
    digest = hashlib.sha256(raw_sig.encode("utf-8")).hexdigest()
    return f"kpi_transform_{digest}"


def compute_regional_metrics(
    df_orders: pd.DataFrame,
    df_tracking: pd.DataFrame,
    df_returns: pd.DataFrame,
    df_cx: pd.DataFrame,
    country_code: str,
) -> Dict[str, Any]:
    """Compute vectorized executive KPIs for a specific geographic scope with zero-division safety."""
    if country_code != "GLOBAL":
        target_wh = "US-LAX-01" if country_code == "US" else "ES-ZAZ-01"
        sub_orders = df_orders[df_orders["warehouse_code"] == target_wh]
        sub_tracking = df_tracking[df_tracking["origin_warehouse"] == target_wh]
        sub_returns = df_returns[df_returns["warehouse_code"] == target_wh]
        sub_cx = df_cx[df_cx["warehouse_code"] == target_wh]
    else:
        sub_orders = df_orders
        sub_tracking = df_tracking
        sub_returns = df_returns
        sub_cx = df_cx

    # KPI 1: Shipments Volume
    shipments_volume = int(len(sub_orders))

    # KPI 2: Global On-Time Delivery Rate (0.0 to 1.0)
    if not sub_tracking.empty:
        latest_tracking = (
            sub_tracking.sort_values("timestamp")
            .groupby("tracking_number_hash", as_index=False)
            .last()
        )
        valid_deliveries = latest_tracking[latest_tracking["is_delivered"].notna()]
        if len(valid_deliveries) > 0:
            on_time_rate = float(np.round(valid_deliveries["is_delivered_on_time"].mean(), 4))
        else:
            on_time_rate = 1.0
    else:
        on_time_rate = 1.0

    # KPI 3: Operational Cost in EUR
    if not sub_orders.empty and "total_cost_eur" in sub_orders.columns:
        operational_cost_eur = float(np.round(sub_orders["total_cost_eur"].fillna(0.0).sum(), 2))
    else:
        operational_cost_eur = 0.0

    # KPI 4: Returns Rate (0.0% to 100.0%)
    if shipments_volume > 0:
        return_items_count = len(sub_returns)
        returns_rate = float(np.round((return_items_count / shipments_volume) * 100.0, 2))
    else:
        returns_rate = 0.0

    # KPI 5: Customer Satisfaction Score (0.0 to 100.0)
    if not sub_cx.empty:
        valid_ratings = sub_cx["csat_rating"].dropna()
        avg_rating_pct = (valid_ratings.mean() / 5.0) * 100.0 if len(valid_ratings) > 0 else 100.0
        fcr_pct = (
            (sub_cx["first_contact_resolution"].mean() * 100.0)
            if "first_contact_resolution" in sub_cx
            else 100.0
        )
        csat_score = float(np.round((avg_rating_pct * 0.70) + (fcr_pct * 0.30), 2))
    else:
        csat_score = 100.0

    return {
        "country": country_code,
        "shipments_volume": max(0, shipments_volume),
        "on_time_delivery_rate": min(max(0.0, on_time_rate), 1.0),
        "operational_cost_eur": max(0.0, operational_cost_eur),
        "returns_rate": min(max(0.0, returns_rate), 100.0),
        "customer_satisfaction_score": min(max(0.0, csat_score), 100.0),
    }


@task(
    name="transform_executive_kpis",
    cache_key_fn=kpi_transformation_cache_key,
    cache_expiration=timedelta(hours=24),
)
def transform_executive_kpis(
    raw_data: Dict[str, pd.DataFrame],
    period_start: datetime,
    period_end: datetime,
) -> List[Dict[str, Any]]:
    """Transform extracted raw DataFrames into regional and global pre-aggregated KPI snapshots."""
    df_orders = raw_data.get("orders", pd.DataFrame())
    df_tracking = raw_data.get("tracking", pd.DataFrame())
    df_returns = raw_data.get("returns", pd.DataFrame())
    df_cx = raw_data.get("cx", pd.DataFrame())

    snapshots: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    for scope in ["US", "ES", "GLOBAL"]:
        metrics = compute_regional_metrics(
            df_orders=df_orders,
            df_tracking=df_tracking,
            df_returns=df_returns,
            df_cx=df_cx,
            country_code=scope,
        )
        metrics["period_start"] = period_start
        metrics["period_end"] = period_end
        metrics["generated_at"] = now
        snapshots.append(metrics)

    return snapshots


# ---------------------------------------------------------------------------
# Stage 3: Idempotent Load & Audit Logging Task
# ---------------------------------------------------------------------------

def execute_snapshot_upsert(
    session: Session,
    snapshots: List[Dict[str, Any]],
) -> int:
    """Execute dialect-adaptive idempotent upsert into executive_kpi_snapshots."""
    is_sqlite = (
        session.bind.dialect.name == "sqlite"
        if session.bind
        else True
    )

    if is_sqlite:
        from sqlalchemy.dialects.sqlite import insert as dialect_insert
    else:
        from sqlalchemy.dialects.postgresql import insert as dialect_insert

    for snap in snapshots:
        stmt = dialect_insert(ExecutiveKpiSnapshot).values(
            snapshot_id=uuid4(),
            period_start=snap["period_start"],
            period_end=snap["period_end"],
            country=snap["country"],
            shipments_volume=snap["shipments_volume"],
            on_time_delivery_rate=snap["on_time_delivery_rate"],
            operational_cost_eur=snap["operational_cost_eur"],
            returns_rate=snap["returns_rate"],
            customer_satisfaction_score=snap["customer_satisfaction_score"],
            generated_at=snap["generated_at"],
        )
        upsert_stmt = stmt.on_conflict_do_update(
            index_elements=["period_start", "period_end", "country"],
            set_={
                "shipments_volume": stmt.excluded.shipments_volume,
                "on_time_delivery_rate": stmt.excluded.on_time_delivery_rate,
                "operational_cost_eur": stmt.excluded.operational_cost_eur,
                "returns_rate": stmt.excluded.returns_rate,
                "customer_satisfaction_score": stmt.excluded.customer_satisfaction_score,
                "generated_at": stmt.excluded.generated_at,
            },
        )
        session.exec(upsert_stmt)

    return len(snapshots)


@task(
    name="load_reporting_snapshots",
    retries=3,
    retry_delay_seconds=10,
)
def load_reporting_snapshots(
    snapshots: List[Dict[str, Any]],
    run_id: UUID,
) -> int:
    """Atomically persist pre-computed snapshots into executive_kpi_snapshots."""
    init_reporting_db()
    with get_session() as session:
        with session.begin():
            count = execute_snapshot_upsert(session, snapshots)
        return count


# ---------------------------------------------------------------------------
# Auxiliary Non-Critical Task: Notification
# ---------------------------------------------------------------------------

def send_notification_webhook(run_id: str, status: str, summary: Dict[str, Any]) -> bool:
    """Mockable notification dispatcher for Slack/Teams alerts."""
    logger.info("Dispatched pipeline execution notification for run_id=%s, status=%s", run_id, status)
    return True


@task(name="notify_pipeline_status")
def notify_pipeline_status(run_id: str, status: str, summary: Dict[str, Any]) -> bool:
    """Non-critical auxiliary task for publishing pipeline execution notifications."""
    return send_notification_webhook(run_id, status, summary)


# ---------------------------------------------------------------------------
# Primary Prefect Orchestration Flow
# ---------------------------------------------------------------------------

@flow(name="executive_performance_pipeline_flow")
def executive_performance_pipeline_flow(
    period_start: Optional[datetime] = None,
    period_end: Optional[datetime] = None,
) -> Any:
    """Main execution flow for the resilient business performance data pipeline."""
    init_reporting_db()

    start_window, end_window = get_default_reporting_window()
    actual_start = period_start if period_start is not None else start_window
    actual_end = period_end if period_end is not None else end_window

    run_id = uuid4()
    started_at = datetime.now(timezone.utc)
    records_processed = 0

    # 1. Initialize execution audit log in RUNNING state
    with get_session() as session:
        log_entry = PipelineExecutionLog(
            run_id=run_id,
            flow_name="executive_performance_pipeline_flow",
            started_at=started_at,
            records_processed=0,
            status="RUNNING",
        )
        session.add(log_entry)
        session.commit()

    try:
        # 2. Stage 1: Extraction
        raw_data = extract_telemetry_and_domain_data(actual_start, actual_end)
        records_processed = sum(len(df) for df in raw_data.values())

        # 3. Stage 2: Transformation & Caching
        snapshots = transform_executive_kpis(raw_data, actual_start, actual_end)

        # 4. Stage 3: Load (Atomic Upsert)
        load_reporting_snapshots(snapshots, run_id)

        # 5. Non-critical auxiliary notification (state captured via return_state=True)
        notify_state = notify_pipeline_status(
            run_id=str(run_id),
            status="SUCCESS",
            summary={"records_processed": records_processed},
            return_state=True,
        )
        if notify_state.is_failed():
            logger.warning(
                "Non-critical notification task failed: %s; continuing flow execution without error.",
                notify_state.result(raise_on_failure=False),
            )

        # 6. Finalize execution audit log with SUCCESS
        with get_session() as session:
            existing_log = session.exec(
                select(PipelineExecutionLog).where(PipelineExecutionLog.run_id == run_id)
            ).first()
            if existing_log:
                existing_log.ended_at = datetime.now(timezone.utc)
                existing_log.records_processed = records_processed
                existing_log.status = "SUCCESS"
                session.add(existing_log)
                session.commit()

        logger.info(
            "Pipeline run %s completed successfully. Processed %d records.",
            run_id,
            records_processed,
        )
        return snapshots

    except Exception as exc:
        sanitized_error = sanitize_error_message(exc)
        logger.error("Pipeline run %s failed: %s", run_id, sanitized_error)

        with get_session() as session:
            existing_log = session.exec(
                select(PipelineExecutionLog).where(PipelineExecutionLog.run_id == run_id)
            ).first()
            if existing_log:
                existing_log.ended_at = datetime.now(timezone.utc)
                existing_log.records_processed = records_processed
                existing_log.status = "FAILED"
                existing_log.error_details = sanitized_error
                session.add(existing_log)
                session.commit()

        raise exc


# ---------------------------------------------------------------------------
# CLI Runner Entry Point
# ---------------------------------------------------------------------------

def parse_iso_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 string into UTC datetime object."""
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError as e:
        raise argparse.ArgumentTypeError(f"Invalid ISO 8601 datetime format '{dt_str}': {e}")


def main() -> None:
    """CLI execution entry point."""
    parser = argparse.ArgumentParser(
        description="Run TrackFlow resilient executive business performance pipeline."
    )
    parser.add_argument(
        "--start-date",
        type=parse_iso_datetime,
        default=None,
        help="UTC window start date in ISO format (e.g. 2026-10-12T00:00:00Z)",
    )
    parser.add_argument(
        "--end-date",
        type=parse_iso_datetime,
        default=None,
        help="UTC window end date in ISO format (e.g. 2026-10-18T23:59:59Z)",
    )
    args = parser.parse_args()

    try:
        flow_state = executive_performance_pipeline_flow(
            period_start=args.start_date,
            period_end=args.end_date,
            return_state=True,
        )
        if flow_state.is_completed():
            logger.info("Pipeline execution finished with state: COMPLETED")
            sys.exit(0)
        else:
            logger.error("Pipeline execution finished with state: %s", flow_state.name)
            sys.exit(1)
    except Exception as e:
        logger.error("Unhandled exception during CLI execution: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
