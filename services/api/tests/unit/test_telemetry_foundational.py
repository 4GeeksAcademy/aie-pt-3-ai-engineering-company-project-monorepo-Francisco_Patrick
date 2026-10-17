"""Unit tests for Phase 2 Telemetry Foundational components.

Covers:
- Pydantic report domain models (report_models.py)
- Thread-safe in-memory cache with 60s TTL (cache.py)
- SQLModel telemetry repository queries and DataFrame extraction (telemetry_repo.py)
"""

from datetime import datetime, timedelta, timezone
import threading
import time
from uuid import uuid4
import pytest
from sqlmodel import Session, SQLModel, create_engine

from application.telemetry.cache import TelemetryReportCache
from domain.telemetry.report_models import (
    AuthFailureRateMetric,
    DailyEventVolumeMetric,
    ErrorDistributionMetric,
    ReportingPeriod,
    TelemetryMetrics,
    TelemetryReportResponse,
)
from infrastructure.persistence.sqlmodel.models import TelemetryEventRecord
from infrastructure.persistence.sqlmodel.telemetry_repo import (
    SQLModelTelemetryRepository,
)


# --- T004: Domain Models & Schemas Tests ---


def test_reporting_period_valid_utc_normalization() -> None:
    """Verify ReportingPeriod accepts naive and aware datetimes, normalizing both to UTC."""
    start = datetime(2026, 10, 10, 0, 0, 0)
    end = datetime(2026, 10, 17, 23, 59, 59)

    period = ReportingPeriod(from_date=start, to_date=end)
    assert period.from_date.tzinfo == timezone.utc
    assert period.to_date.tzinfo == timezone.utc
    assert period.from_date < period.to_date

    # Verify alias initialization and export
    aliased = ReportingPeriod.model_validate({"from": start.isoformat(), "to": end.isoformat()})
    dumped = aliased.model_dump(by_alias=True)
    assert "from" in dumped
    assert "to" in dumped


def test_reporting_period_inverted_bounds_raises_error() -> None:
    """Verify inverted date ranges (from > to) raise ValueError."""
    start = datetime(2026, 10, 17, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 10, 0, 0, 0, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="cannot be later than end date"):
        ReportingPeriod(from_date=start, to_date=end)


def test_auth_failure_rate_metric_invariants() -> None:
    """Verify AuthFailureRateMetric invariants."""
    # Valid metric
    metric = AuthFailureRateMetric(
        date="2026-10-15",
        total_attempts=100,
        failed_attempts=5,
        failure_rate=0.05,
    )
    assert metric.failure_rate == 0.05

    # Zero total attempts with 0.0 rate
    zero_metric = AuthFailureRateMetric(
        date="2026-10-15",
        total_attempts=0,
        failed_attempts=0,
        failure_rate=0.0,
    )
    assert zero_metric.failure_rate == 0.0

    # Failed attempts exceeding total attempts
    with pytest.raises(ValueError, match="cannot exceed total_attempts"):
        AuthFailureRateMetric(
            date="2026-10-15",
            total_attempts=5,
            failed_attempts=10,
            failure_rate=0.5,
        )

    # Non-zero rate when total attempts is zero
    with pytest.raises(ValueError, match="failure_rate must be 0.0 when total_attempts is 0"):
        AuthFailureRateMetric(
            date="2026-10-15",
            total_attempts=0,
            failed_attempts=0,
            failure_rate=0.1,
        )


def test_telemetry_report_response_full_structure() -> None:
    """Verify complete TelemetryReportResponse serialization."""
    period = ReportingPeriod(
        from_date=datetime(2026, 10, 10, 0, 0, 0, tzinfo=timezone.utc),
        to_date=datetime(2026, 10, 17, 0, 0, 0, tzinfo=timezone.utc),
    )
    metrics = TelemetryMetrics(
        events_per_day=[DailyEventVolumeMetric(date="2026-10-11", count=142)],
        error_rate_by_type=[
            ErrorDistributionMetric(event_type="auth_login_failed", count=10, percentage=100.0)
        ],
        auth_failure_rate=[
            AuthFailureRateMetric(
                date="2026-10-11",
                total_attempts=50,
                failed_attempts=5,
                failure_rate=0.1,
            )
        ],
    )
    response = TelemetryReportResponse(period=period, metrics=metrics)
    dumped = response.model_dump(by_alias=True)

    assert "period" in dumped
    assert "from" in dumped["period"]
    assert "to" in dumped["period"]
    assert len(dumped["metrics"]["events_per_day"]) == 1
    assert dumped["metrics"]["events_per_day"][0]["count"] == 142


# --- T005: Cache Infrastructure Tests ---


def test_telemetry_report_cache_basic_operations() -> None:
    """Verify cache get, set, hit, miss, and key generation."""
    cache = TelemetryReportCache(default_ttl_seconds=60.0)

    start = datetime(2026, 10, 10, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 17, 0, 0, 0, tzinfo=timezone.utc)
    key = cache.generate_key(start, end)
    assert "2026-10-10" in key
    assert "2026-10-17" in key

    assert cache.get(key) is None
    payload = {"data": "operational_report_1"}
    cache.set(key, payload)

    assert cache.get(key) == payload
    assert len(cache) == 1

    # Invalidate
    assert cache.invalidate(key) is True
    assert cache.get(key) is None
    assert cache.invalidate(key) is False


def test_telemetry_report_cache_ttl_expiration() -> None:
    """Verify cache entry expires after TTL."""
    cache = TelemetryReportCache(default_ttl_seconds=0.1)
    cache.set("ephemeral_key", {"report": "temp"}, ttl_seconds=0.1)

    assert cache.get("ephemeral_key") == {"report": "temp"}
    time.sleep(0.15)
    assert cache.get("ephemeral_key") is None


def test_telemetry_report_cache_capacity_eviction() -> None:
    """Verify oldest or expired entries are evicted when max capacity is reached."""
    cache = TelemetryReportCache(default_ttl_seconds=60.0, max_entries=3)

    cache.set("k1", {"val": 1})
    cache.set("k2", {"val": 2})
    cache.set("k3", {"val": 3})

    assert len(cache) == 3
    # Adding a 4th key evicts the oldest (k1)
    cache.set("k4", {"val": 4})
    assert len(cache) == 3
    assert cache.get("k1") is None
    assert cache.get("k4") == {"val": 4}


def test_telemetry_report_cache_concurrency_safety() -> None:
    """Verify concurrent reads and writes do not corrupt cache state."""
    cache = TelemetryReportCache(default_ttl_seconds=5.0, max_entries=50)

    def worker(worker_id: int) -> None:
        for i in range(25):
            k = f"key_{worker_id}_{i}"
            cache.set(k, {"worker": worker_id, "i": i})
            _ = cache.get(k)

    threads = [threading.Thread(target=worker, args=(w,)) for w in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(cache) <= 50


# --- T006: Repository & Query Tests ---


@pytest.fixture
def memory_db_session() -> Session:
    """Provide an in-memory SQLite session with table schemas created."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_sqlmodel_telemetry_repo_queries(memory_db_session: Session) -> None:
    """Verify telemetry extraction queries and DataFrame conversion."""
    repo = SQLModelTelemetryRepository(session=memory_db_session)

    base_time = datetime(2026, 10, 15, 12, 0, 0, tzinfo=timezone.utc)

    # Seed 3 telemetry records
    events = [
        TelemetryEventRecord(
            event_id=uuid4(),
            timestamp=base_time - timedelta(days=2),
            session_id="sess_1",
            user_id="usr_1",
            event_type="auth_login_succeeded",
            schema_version="1.0.0",
            request_id="req_1",
            properties={"browser": "chrome"},
        ),
        TelemetryEventRecord(
            event_id=uuid4(),
            timestamp=base_time - timedelta(days=1),
            session_id="sess_2",
            user_id="usr_2",
            event_type="auth_login_failed",
            schema_version="1.0.0",
            request_id="req_2",
            properties={"reason": "invalid_credentials"},
        ),
        TelemetryEventRecord(
            event_id=uuid4(),
            timestamp=base_time,
            session_id="sess_3",
            user_id=None,
            event_type="frontend_error_captured",
            schema_version="1.0.0",
            request_id="req_3",
            properties={"error": "chunk_load_failed"},
        ),
    ]
    for ev in events:
        memory_db_session.add(ev)
    memory_db_session.commit()

    # Query full range
    start_dt = base_time - timedelta(days=3)
    end_dt = base_time + timedelta(hours=1)
    results = repo.get_events_in_range(start_dt, end_dt)
    assert len(results) == 3

    # Query with event_types filter
    auth_results = repo.get_events_in_range(start_dt, end_dt, event_types=["auth_login_failed"])
    assert len(auth_results) == 1
    assert auth_results[0].event_type == "auth_login_failed"

    # Query as DataFrame
    df = repo.get_events_dataframe(start_dt, end_dt)
    assert not df.empty
    assert len(df) == 3
    assert "timestamp" in df.columns
    assert "event_type" in df.columns
    assert str(df["timestamp"].dtype).startswith("datetime64[")
    assert "UTC" in str(df["timestamp"].dtype)

    # Query empty range
    empty_df = repo.get_events_dataframe(
        base_time + timedelta(days=10),
        base_time + timedelta(days=11),
    )
    assert empty_df.empty
    assert "timestamp" in empty_df.columns
