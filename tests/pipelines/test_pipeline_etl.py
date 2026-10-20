"""Unit and integration tests for ETL extraction, vectorized transformations, and flow execution."""

from datetime import datetime, timedelta, timezone
import os
from typing import Any, Dict
import pandas as pd
import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from data.pipelines.models import (
    ExecutiveKpiSnapshot,
    PipelineExecutionLog,
    init_reporting_db,
    set_engine,
)
from data.pipelines.pipeline import (
    compute_regional_metrics,
    executive_performance_pipeline_flow,
    extract_telemetry_and_domain_data,
    transform_executive_kpis,
)


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    """Isolate database per test run with an in-memory or temporary SQLite database."""
    test_db_path = tmp_path / "test_inventory.db"
    engine = create_engine(
        f"sqlite:///{test_db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    set_engine(engine)

    # Create tables
    init_reporting_db(engine)

    # Create telemetry_events and domain tables if needed
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
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS stock_exit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku_id INTEGER NOT NULL,
                warehouse_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                user_uuid TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.commit()

    yield engine


def test_zero_division_guardrails():
    """Verify that empty datasets return safe default baseline metrics without zero-division errors."""
    empty_orders = pd.DataFrame(columns=["order_id", "warehouse_code", "total_cost_eur"])
    empty_tracking = pd.DataFrame(
        columns=["tracking_number_hash", "origin_warehouse", "timestamp", "is_delivered", "is_delivered_on_time"]
    )
    empty_returns = pd.DataFrame(columns=["return_id", "warehouse_code"])
    empty_cx = pd.DataFrame(columns=["warehouse_code", "csat_rating", "first_contact_resolution"])

    for scope in ["US", "ES", "GLOBAL"]:
        metrics = compute_regional_metrics(
            df_orders=empty_orders,
            df_tracking=empty_tracking,
            df_returns=empty_returns,
            df_cx=empty_cx,
            country_code=scope,
        )

        assert metrics["country"] == scope
        assert metrics["shipments_volume"] == 0
        assert metrics["on_time_delivery_rate"] == 1.0
        assert metrics["operational_cost_eur"] == 0.0
        assert metrics["returns_rate"] == 0.0
        assert metrics["customer_satisfaction_score"] == 100.0


def test_compute_regional_metrics_mathematical_precision():
    """Verify exact formula precision across US, ES, and GLOBAL scopes."""
    now = datetime.now(timezone.utc)

    # Orders: 2 US, 1 ES
    df_orders = pd.DataFrame([
        {"order_id": "ord-1", "warehouse_code": "US-LAX-01", "total_cost_eur": 25.50},
        {"order_id": "ord-2", "warehouse_code": "US-LAX-01", "total_cost_eur": 30.00},
        {"order_id": "ord-3", "warehouse_code": "ES-ZAZ-01", "total_cost_eur": 15.00},
    ])

    # Tracking: US: 1 on-time, 1 late; ES: 1 on-time
    df_tracking = pd.DataFrame([
        {
            "tracking_number_hash": "trk-1",
            "origin_warehouse": "US-LAX-01",
            "timestamp": now.isoformat(),
            "is_delivered": True,
            "is_delivered_on_time": 1.0,
        },
        {
            "tracking_number_hash": "trk-2",
            "origin_warehouse": "US-LAX-01",
            "timestamp": now.isoformat(),
            "is_delivered": True,
            "is_delivered_on_time": 0.0,
        },
        {
            "tracking_number_hash": "trk-3",
            "origin_warehouse": "ES-ZAZ-01",
            "timestamp": now.isoformat(),
            "is_delivered": True,
            "is_delivered_on_time": 1.0,
        },
    ])

    # Returns: US: 1 return out of 2 shipments = 50%; ES: 0 returns = 0%
    df_returns = pd.DataFrame([
        {"return_id": "ret-1", "warehouse_code": "US-LAX-01"},
    ])

    # CX: US: 1 rating at 4.0/5.0, FCR=1.0 -> (4/5*100)*0.7 + (1.0*100)*0.3 = 56 + 30 = 86.0
    df_cx = pd.DataFrame([
        {"warehouse_code": "US-LAX-01", "csat_rating": 4.0, "first_contact_resolution": 1.0},
        {"warehouse_code": "ES-ZAZ-01", "csat_rating": 5.0, "first_contact_resolution": 1.0},
    ])

    # US Scope
    us_metrics = compute_regional_metrics(df_orders, df_tracking, df_returns, df_cx, "US")
    assert us_metrics["shipments_volume"] == 2
    assert us_metrics["operational_cost_eur"] == 55.50
    assert us_metrics["on_time_delivery_rate"] == 0.5
    assert us_metrics["returns_rate"] == 50.0
    assert us_metrics["customer_satisfaction_score"] == 86.0

    # ES Scope
    es_metrics = compute_regional_metrics(df_orders, df_tracking, df_returns, df_cx, "ES")
    assert es_metrics["shipments_volume"] == 1
    assert es_metrics["operational_cost_eur"] == 15.00
    assert es_metrics["on_time_delivery_rate"] == 1.0
    assert es_metrics["returns_rate"] == 0.0
    assert es_metrics["customer_satisfaction_score"] == 100.0

    # GLOBAL Scope
    global_metrics = compute_regional_metrics(df_orders, df_tracking, df_returns, df_cx, "GLOBAL")
    assert global_metrics["shipments_volume"] == 3
    assert global_metrics["operational_cost_eur"] == 70.50
    assert abs(global_metrics["on_time_delivery_rate"] - (2 / 3)) < 0.001
    assert abs(global_metrics["returns_rate"] - (1 / 3 * 100.0)) < 0.01


def test_telemetry_asset_preservation():
    """Verify that services/telemetry/analysis.py exists and preserves its original purpose."""
    telemetry_analysis_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "services", "telemetry", "analysis.py")
    )
    assert os.path.exists(telemetry_analysis_path), "services/telemetry/analysis.py must exist"

    with open(telemetry_analysis_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Verify functions are intact
    assert "def calculate_events_per_day(" in content
    assert "def calculate_error_rate_by_type(" in content
    assert "def calculate_auth_failure_rate(" in content
    assert "def generate_telemetry_report(" in content


def test_end_to_end_pipeline_flow(setup_test_db):
    """Execute executive_performance_pipeline_flow and verify database records and audit log."""
    engine = setup_test_db

    # Seed sample telemetry event in database
    import json
    now = datetime.now(timezone.utc)
    with engine.connect() as conn:
        conn.exec_driver_sql(
            """
            INSERT INTO telemetry_events (
                event_id, timestamp, session_id, user_id, event_type, schema_version, request_id, properties, created_at
            ) VALUES (
                'test-ev-1', :ts, 'sess-1', 'usr-1', 'outbound_order_fulfilled', '1.0', 'req-1', :props, :ca
            )
            """,
            {
                "ts": now.isoformat(),
                "props": json.dumps({
                    "orderId": "ord-test-1",
                    "warehouseCode": "US-LAX-01",
                    "totalCostEur": 42.0,
                    "destinationCountry": "US",
                }),
                "ca": now.isoformat(),
            },
        )
        conn.commit()

    # Run flow
    flow_state = executive_performance_pipeline_flow(
        period_start=now - timedelta(days=7),
        period_end=now + timedelta(days=1),
        return_state=True,
    )

    assert flow_state.is_completed()

    # Verify snapshot records exist
    with Session(engine) as session:
        snapshots = session.exec(select(ExecutiveKpiSnapshot)).all()
        assert len(snapshots) == 3  # US, ES, GLOBAL

        countries = {s.country for s in snapshots}
        assert countries == {"US", "ES", "GLOBAL"}

        # Verify execution log
        logs = session.exec(select(PipelineExecutionLog)).all()
        assert len(logs) == 1
        assert logs[0].status == "SUCCESS"
        assert logs[0].records_processed >= 1
