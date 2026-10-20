"""API integration and caching tests for the telemetry report endpoint.

Validates:
1. Default 7-day UTC time window resolution.
2. Custom date range query parameter handling.
3. Thread-safe 60-second in-memory caching with X-Cache headers (MISS -> HIT).
4. Dual route mounting (/telemetry/report and /api/v1/telemetry/report).
5. Input validation (inverted date ranges and malformed ISO strings returning 422).
"""

from datetime import datetime, timedelta, timezone
import uuid
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_telemetry_report_cache():
    """Ensure in-memory report cache is purged between tests to prevent pollution."""
    try:
        from presentation.dependencies import get_telemetry_report_cache_dep
        cache = get_telemetry_report_cache_dep()
        cache.clear()
    except (ImportError, AttributeError):
        pass
    yield
    try:
        from presentation.dependencies import get_telemetry_report_cache_dep
        cache = get_telemetry_report_cache_dep()
        cache.clear()
    except (ImportError, AttributeError):
        pass


def test_get_telemetry_report_default_7_day_window():
    """T007: Default request resolves a 7-day UTC period and returns X-Cache: MISS on cold read."""
    before_call = datetime.now(timezone.utc)
    response = client.get("/telemetry/report")
    after_call = datetime.now(timezone.utc)

    assert response.status_code == 200
    assert response.headers.get("X-Cache") == "MISS"

    data = response.json()
    assert "period" in data
    assert "metrics" in data

    period = data["period"]
    assert "from" in period
    assert "to" in period

    from_dt = datetime.fromisoformat(period["from"].replace("Z", "+00:00"))
    to_dt = datetime.fromisoformat(period["to"].replace("Z", "+00:00"))

    # Verify interval is approximately 7 days (within 5 seconds tolerance)
    duration = to_dt - from_dt
    assert abs(duration.total_seconds() - 7 * 86400) < 5

    # Verify 'to' is approximately current UTC time
    assert before_call - timedelta(seconds=2) <= to_dt <= after_call + timedelta(seconds=2)

    # Verify metrics structure conforming to schema
    metrics = data["metrics"]
    assert isinstance(metrics.get("events_per_day"), list)
    assert isinstance(metrics.get("error_rate_by_type"), list)
    assert isinstance(metrics.get("auth_failure_rate"), list)


def test_get_telemetry_report_caching_hit_on_subsequent_request():
    """T007: Identical request within 60s TTL returns cached response with X-Cache: HIT."""
    res1 = client.get("/telemetry/report")
    assert res1.status_code == 200
    assert res1.headers.get("X-Cache") == "MISS"
    data1 = res1.json()

    res2 = client.get("/telemetry/report")
    assert res2.status_code == 200
    assert res2.headers.get("X-Cache") == "HIT"
    data2 = res2.json()

    assert data1 == data2


def test_get_telemetry_report_custom_date_range_caching():
    """T007: Custom start_date and end_date queries return bounded period and cache hits."""
    start_str = "2026-10-01T00:00:00Z"
    end_str = "2026-10-05T23:59:59Z"

    res1 = client.get(f"/telemetry/report?start_date={start_str}&end_date={end_str}")
    assert res1.status_code == 200
    assert res1.headers.get("X-Cache") == "MISS"

    data1 = res1.json()
    assert data1["period"]["from"].startswith("2026-10-01T00:00:00")
    assert data1["period"]["to"].startswith("2026-10-05T23:59:59")

    # Second call with identical params must hit cache
    res2 = client.get(f"/telemetry/report?start_date={start_str}&end_date={end_str}")
    assert res2.status_code == 200
    assert res2.headers.get("X-Cache") == "HIT"
    assert res2.json() == data1


def test_get_telemetry_report_canonical_v1_alias():
    """T007: Canonical /api/v1/telemetry/report exhibits identical contract behavior."""
    response = client.get("/api/v1/telemetry/report")
    assert response.status_code == 200
    data = response.json()
    assert "period" in data
    assert "metrics" in data


def test_get_telemetry_report_inverted_date_range_returns_422():
    """T007: Validation rejects start_date > end_date with HTTP 422 Unprocessable Entity."""
    start_str = "2026-10-15T00:00:00Z"
    end_str = "2026-10-10T00:00:00Z"

    response = client.get(f"/telemetry/report?start_date={start_str}&end_date={end_str}")
    assert response.status_code == 422


def test_get_telemetry_report_malformed_date_returns_422():
    """T007: Malformed ISO 8601 timestamps return HTTP 422 Unprocessable Entity."""
    response = client.get("/telemetry/report?start_date=not-a-valid-datetime")
    assert response.status_code == 422


def test_get_telemetry_report_with_seeded_events():
    """T007: Ingest events, query report, and verify response schema and non-empty execution."""
    now = datetime.now(timezone.utc)
    event_payload = {
        "events": [
            {
                "eventId": str(uuid.uuid4()),
                "timestamp": now.isoformat(),
                "sessionId": "sess_report_test",
                "userId": "usr_001",
                "event_type": "inbound_order_created",
                "schemaVersion": "1.0.0",
                "requestId": "req_report_1",
                "properties": {"units": 10},
            },
            {
                "eventId": str(uuid.uuid4()),
                "timestamp": now.isoformat(),
                "sessionId": "sess_report_test",
                "userId": "usr_002",
                "event_type": "auth_login_failed",
                "schemaVersion": "1.0.0",
                "requestId": "req_report_2",
                "properties": {"attemptStatus": "failed"},
            },
        ]
    }
    ingest_res = client.post("/telemetry/events", json=event_payload)
    assert ingest_res.status_code == 200

    report_res = client.get("/telemetry/report")
    assert report_res.status_code == 200
    report_data = report_res.json()
    assert "metrics" in report_data
    assert "period" in report_data
    assert isinstance(report_data["metrics"]["auth_failure_rate"], list)


def test_get_telemetry_report_auth_failure_rate_metrics():
    """T019: Ingest mixed auth events and verify /telemetry/report returns calculated auth_failure_rate."""
    now = datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")

    events = [
        {
            "eventId": str(uuid.uuid4()),
            "timestamp": now.isoformat(),
            "sessionId": "sess_auth_test",
            "userId": f"usr_auth_{i}",
            "event_type": "auth_login_failed" if i < 2 else "user_login_succeeded",
            "schemaVersion": "1.0.0",
            "requestId": f"req_auth_{i}",
            "properties": {},
        }
        for i in range(5)  # 2 failed, 3 succeeded -> total 5, failure rate = 0.4
    ]

    ingest_res = client.post("/telemetry/events", json={"events": events})
    assert ingest_res.status_code == 200

    report_res = client.get("/telemetry/report")
    assert report_res.status_code == 200
    data = report_res.json()

    auth_rates = data["metrics"]["auth_failure_rate"]
    assert len(auth_rates) > 0

    today_metric = next((m for m in auth_rates if m["date"] == today_str), None)
    assert today_metric is not None
    assert today_metric["total_attempts"] >= 5
    assert today_metric["failed_attempts"] >= 2
    assert 0.0 <= today_metric["failure_rate"] <= 1.0


def test_get_telemetry_report_auth_failure_rate_zero_attempts_period():
    """T019: Bounded query for a period with no authentication attempts returns empty auth_failure_rate array."""
    # Historical date window where no events exist
    start_str = "2020-01-01T00:00:00Z"
    end_str = "2020-01-02T23:59:59Z"

    report_res = client.get(f"/telemetry/report?start_date={start_str}&end_date={end_str}")
    assert report_res.status_code == 200
    data = report_res.json()

    assert data["metrics"]["auth_failure_rate"] == []
    assert data["metrics"]["events_per_day"] == []
    assert data["metrics"]["error_rate_by_type"] == []

