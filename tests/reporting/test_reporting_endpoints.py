"""API route contract and validation tests for reporting endpoints."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine

from data.pipelines.models import (
    ExecutiveKpiSnapshot,
    PipelineExecutionLog,
    init_reporting_db,
    set_engine,
)
from services.api.main import app


@pytest.fixture(autouse=True)
def setup_reporting_test_db(tmp_path):
    """Isolate database for reporting route testing."""
    test_db_path = tmp_path / "test_reporting_routes.db"
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


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


def test_get_status_initial_state(client):
    """GET /api/v1/reporting/status returns default empty state when no runs exist."""
    response = client.get("/api/v1/reporting/status")
    assert response.status_code == 200
    data = response.json()
    assert data["is_running"] is False
    assert data["healthy"] is False
    assert data["latest_run"] is None


def test_get_status_with_completed_run(client, setup_reporting_test_db):
    """GET /api/v1/reporting/status returns latest run details when completed."""
    engine = setup_reporting_test_db
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        log = PipelineExecutionLog(
            run_id=uuid4(),
            flow_name="executive_performance_pipeline_flow",
            started_at=now - timedelta(minutes=2),
            ended_at=now,
            records_processed=150,
            status="SUCCESS",
        )
        session.add(log)
        session.commit()

    response = client.get("/api/v1/reporting/status")
    assert response.status_code == 200
    data = response.json()
    assert data["is_running"] is False
    assert data["healthy"] is True
    assert data["latest_run"] is not None
    assert data["latest_run"]["status"] == "SUCCESS"
    assert data["latest_run"]["records_processed"] == 150


def test_post_trigger_success(client):
    """POST /api/v1/reporting/trigger accepts trigger request and returns 202 INITIATED."""
    response = client.post("/api/v1/reporting/trigger", json={})
    assert response.status_code == 202
    data = response.json()
    assert "run_id" in data
    assert data["status"] in ("INITIATED", "QUEUED")
    assert "message" in data


def test_post_trigger_conflict_409(client, setup_reporting_test_db):
    """POST /api/v1/reporting/trigger returns 409 Conflict when a run is already RUNNING."""
    engine = setup_reporting_test_db
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        active_log = PipelineExecutionLog(
            run_id=uuid4(),
            flow_name="executive_performance_pipeline_flow",
            started_at=now - timedelta(minutes=1),
            records_processed=0,
            status="RUNNING",
        )
        session.add(active_log)
        session.commit()

    response = client.post("/api/v1/reporting/trigger", json={})
    assert response.status_code == 409
    data = response.json()
    assert "detail" in data
    assert "already in RUNNING state" in data["detail"]


def test_get_kpis_filtered_by_country(client, setup_reporting_test_db):
    """GET /api/v1/reporting/kpis retrieves pre-computed snapshots matching country filter."""
    engine = setup_reporting_test_db
    now = datetime.now(timezone.utc)

    with Session(engine) as session:
        us_snap = ExecutiveKpiSnapshot(
            snapshot_id=uuid4(),
            period_start=now - timedelta(days=7),
            period_end=now,
            country="US",
            shipments_volume=120,
            on_time_delivery_rate=0.95,
            operational_cost_eur=4200.0,
            returns_rate=12.5,
            customer_satisfaction_score=88.0,
            generated_at=now,
        )
        es_snap = ExecutiveKpiSnapshot(
            snapshot_id=uuid4(),
            period_start=now - timedelta(days=7),
            period_end=now,
            country="ES",
            shipments_volume=80,
            on_time_delivery_rate=0.98,
            operational_cost_eur=2100.0,
            returns_rate=8.0,
            customer_satisfaction_score=92.0,
            generated_at=now,
        )
        session.add(us_snap)
        session.add(es_snap)
        session.commit()

    # Query US
    res_us = client.get("/api/v1/reporting/kpis?country=US")
    assert res_us.status_code == 200
    data_us = res_us.json()
    assert data_us["count"] == 1
    assert data_us["snapshots"][0]["country"] == "US"
    assert data_us["snapshots"][0]["shipments_volume"] == 120

    # Query ES
    res_es = client.get("/api/v1/reporting/kpis?country=ES")
    assert res_es.status_code == 200
    data_es = res_es.json()
    assert data_es["count"] == 1
    assert data_es["snapshots"][0]["country"] == "ES"


def test_get_kpis_invalid_country_422(client):
    """GET /api/v1/reporting/kpis returns 422 for unsupported country scope."""
    response = client.get("/api/v1/reporting/kpis?country=FR")
    assert response.status_code == 422
