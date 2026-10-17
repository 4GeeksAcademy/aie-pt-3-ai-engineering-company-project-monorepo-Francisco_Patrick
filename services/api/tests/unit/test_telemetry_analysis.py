"""Unit tests for Pandas operational telemetry analysis pipeline.

Conforms to Phase 4 / User Story 2 requirements:
- Vectorized, side-effect-free Pandas metric functions.
- Strict UTC datetime normalization before temporal grouping.
- events_per_day calculation and chronological ordering.
- error_rate_by_type filtering, counting, percentage distribution, and descending ordering.
- generate_telemetry_report consolidated pipeline runner.
- Resilient empty dataset handling with zero division guards.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List
import pandas as pd
import pytest

from domain.telemetry.report_models import (
    AuthFailureRateMetric,
    DailyEventVolumeMetric,
    ErrorDistributionMetric,
    TelemetryMetrics,
)
from telemetry.analysis import (
    calculate_auth_failure_rate,
    calculate_error_rate_by_type,
    calculate_events_per_day,
    generate_telemetry_report,
)


def _create_sample_telemetry_df() -> pd.DataFrame:
    """Helper to generate a predictable sample DataFrame across multiple days and event types."""
    data = [
        # 2026-10-10: 3 events (1 success, 2 errors)
        {
            "event_id": "evt-1",
            "timestamp": "2026-10-10T02:15:00+00:00",
            "event_type": "inbound_order_created",
            "session_id": "sess-1",
            "user_id": "u-1",
            "schema_version": "1.0.0",
            "request_id": "req-1",
            "properties": {},
            "created_at": "2026-10-10T02:15:00+00:00",
        },
        {
            "event_id": "evt-2",
            "timestamp": "2026-10-10T14:30:00Z",
            "event_type": "auth_login_failed",
            "session_id": "sess-2",
            "user_id": "u-2",
            "schema_version": "1.0.0",
            "request_id": "req-2",
            "properties": {},
            "created_at": "2026-10-10T14:30:00Z",
        },
        {
            "event_id": "evt-3",
            "timestamp": "2026-10-10T23:59:00+00:00",
            "event_type": "db_connection_exception",
            "session_id": "sess-3",
            "user_id": None,
            "schema_version": "1.0.0",
            "request_id": "req-3",
            "properties": {},
            "created_at": "2026-10-10T23:59:00+00:00",
        },
        # 2026-10-11: 4 events (1 success, 3 errors of varying types)
        {
            "event_id": "evt-4",
            "timestamp": "2026-10-11T08:00:00+02:00",  # Non-UTC timezone offset (+02:00 -> 06:00:00 UTC)
            "event_type": "stock_exit_recorded",
            "session_id": "sess-4",
            "user_id": "u-3",
            "schema_version": "1.0.0",
            "request_id": "req-4",
            "properties": {},
            "created_at": "2026-10-11T08:00:00+02:00",
        },
        {
            "event_id": "evt-5",
            "timestamp": "2026-10-11T12:00:00Z",
            "event_type": "auth_login_failed",
            "session_id": "sess-5",
            "user_id": "u-4",
            "schema_version": "1.0.0",
            "request_id": "req-5",
            "properties": {},
            "created_at": "2026-10-11T12:00:00Z",
        },
        {
            "event_id": "evt-6",
            "timestamp": "2026-10-11T16:00:00Z",
            "event_type": "auth_login_failed",
            "session_id": "sess-6",
            "user_id": "u-5",
            "schema_version": "1.0.0",
            "request_id": "req-6",
            "properties": {},
            "created_at": "2026-10-11T16:00:00Z",
        },
        {
            "event_id": "evt-7",
            "timestamp": "2026-10-11T20:00:00Z",
            "event_type": "frontend_error_captured",
            "session_id": "sess-7",
            "user_id": "u-6",
            "schema_version": "1.0.0",
            "request_id": "req-7",
            "properties": {},
            "created_at": "2026-10-11T20:00:00Z",
        },
        # 2026-10-12: 1 event (non-error)
        {
            "event_id": "evt-8",
            "timestamp": "2026-10-12T01:00:00Z",
            "event_type": "user_login_succeeded",
            "session_id": "sess-8",
            "user_id": "u-7",
            "schema_version": "1.0.0",
            "request_id": "req-8",
            "properties": {},
            "created_at": "2026-10-12T01:00:00Z",
        },
    ]
    return pd.DataFrame(data)


# --- T012: calculate_events_per_day Tests ---


def test_calculate_events_per_day_standard() -> None:
    """T012: Verify daily event aggregation counts events accurately and sorts ascending."""
    df = _create_sample_telemetry_df()
    results = calculate_events_per_day(df)

    assert isinstance(results, list)
    assert len(results) == 3

    # Ensure chronological order
    dates = [item["date"] if isinstance(item, dict) else item.date for item in results]
    counts = [item["count"] if isinstance(item, dict) else item.count for item in results]

    assert dates == ["2026-10-10", "2026-10-11", "2026-10-12"]
    assert counts == [3, 4, 1]


def test_calculate_events_per_day_utc_normalization() -> None:
    """T012: Non-UTC timestamp (2026-10-11T01:00:00+04:00 -> 2026-10-10T21:00:00Z) groups into correct UTC day."""
    df = pd.DataFrame([
        {
            "event_id": "evt-tz",
            "timestamp": "2026-10-11T01:00:00+04:00",  # In UTC, this is 2026-10-10 21:00:00
            "event_type": "inbound_order_created",
        }
    ])
    results = calculate_events_per_day(df)
    assert len(results) == 1
    date_val = results[0]["date"] if isinstance(results[0], dict) else results[0].date
    assert date_val == "2026-10-10"


def test_calculate_events_per_day_empty_df() -> None:
    """T012: Empty DataFrame returns empty list without error."""
    empty_df = pd.DataFrame(columns=["event_id", "timestamp", "event_type"])
    results = calculate_events_per_day(empty_df)
    assert results == []


def test_calculate_events_per_day_immutability() -> None:
    """T012: Calling calculate_events_per_day twice produces identical results and leaves input DataFrame intact."""
    df = _create_sample_telemetry_df()
    original_cols = list(df.columns)
    original_len = len(df)

    res1 = calculate_events_per_day(df)
    res2 = calculate_events_per_day(df)

    assert res1 == res2
    assert list(df.columns) == original_cols
    assert len(df) == original_len


def test_calculate_events_per_day_with_date_filtering() -> None:
    """T012: Passing start_date and end_date filters events within inclusive boundaries."""
    df = _create_sample_telemetry_df()
    start = datetime(2026, 10, 11, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 11, 23, 59, 59, tzinfo=timezone.utc)

    results = calculate_events_per_day(df, start_date=start, end_date=end)
    assert len(results) == 1
    date_val = results[0]["date"] if isinstance(results[0], dict) else results[0].date
    count_val = results[0]["count"] if isinstance(results[0], dict) else results[0].count
    assert date_val == "2026-10-11"
    assert count_val == 4


# --- T013: calculate_error_rate_by_type Tests ---


def test_calculate_error_rate_by_type_standard() -> None:
    """T013: Aggregates operational failure events, computes percentage, and sorts by count descending."""
    df = _create_sample_telemetry_df()
    results = calculate_error_rate_by_type(df)

    assert isinstance(results, list)
    # Errors in sample:
    # auth_login_failed: 3
    # db_connection_exception: 1
    # frontend_error_captured: 1
    # Total errors = 5
    assert len(results) == 3

    types = [item["event_type"] if isinstance(item, dict) else item.event_type for item in results]
    counts = [item["count"] if isinstance(item, dict) else item.count for item in results]
    percentages = [
        item["percentage"] if isinstance(item, dict) else item.percentage for item in results
    ]

    assert types[0] == "auth_login_failed"
    assert counts[0] == 3
    assert percentages[0] == 60.0

    assert counts[1] == 1
    assert percentages[1] == 20.0

    assert counts[2] == 1
    assert percentages[2] == 20.0

    # Total sum of percentages should equal 100.0
    assert pytest.approx(sum(percentages), 0.01) == 100.0


def test_calculate_error_rate_by_type_no_errors() -> None:
    """T013: Dataset with zero errors returns empty list without division-by-zero exception."""
    df = pd.DataFrame([
        {
            "event_id": "evt-ok",
            "timestamp": "2026-10-10T12:00:00Z",
            "event_type": "inbound_order_created",
        },
        {
            "event_id": "evt-ok-2",
            "timestamp": "2026-10-10T13:00:00Z",
            "event_type": "stock_exit_recorded",
        },
    ])
    results = calculate_error_rate_by_type(df)
    assert results == []


def test_calculate_error_rate_by_type_empty_df() -> None:
    """T013: Empty DataFrame returns empty list."""
    empty_df = pd.DataFrame(columns=["event_id", "timestamp", "event_type"])
    results = calculate_error_rate_by_type(empty_df)
    assert results == []


# --- T014: generate_telemetry_report Tests ---


def test_generate_telemetry_report_consolidated() -> None:
    """T014: generate_telemetry_report runs pipeline and returns TelemetryMetrics container."""
    df = _create_sample_telemetry_df()
    metrics = generate_telemetry_report(df)

    assert isinstance(metrics, TelemetryMetrics)
    assert len(metrics.events_per_day) == 3
    assert len(metrics.error_rate_by_type) == 3
    assert len(metrics.auth_failure_rate) == 3
    # Check DailyEventVolumeMetric models
    assert all(isinstance(m, DailyEventVolumeMetric) for m in metrics.events_per_day)
    # Check ErrorDistributionMetric models
    assert all(isinstance(m, ErrorDistributionMetric) for m in metrics.error_rate_by_type)
    # Check AuthFailureRateMetric models
    assert all(isinstance(m, AuthFailureRateMetric) for m in metrics.auth_failure_rate)


def test_generate_telemetry_report_empty_df() -> None:
    """T014: generate_telemetry_report on empty DataFrame returns valid TelemetryMetrics with empty lists."""
    empty_df = pd.DataFrame(columns=["event_id", "timestamp", "event_type"])
    metrics = generate_telemetry_report(empty_df)

    assert isinstance(metrics, TelemetryMetrics)
    assert metrics.events_per_day == []
    assert metrics.error_rate_by_type == []
    assert metrics.auth_failure_rate == []


# --- T015: ReportService Connection with Analysis Runner Tests ---


def test_report_service_connects_with_dataframe_and_analysis_runner() -> None:
    """T015: Verify TelemetryReportService extracts DataFrame from repository and invokes analysis runner."""
    from unittest.mock import MagicMock
    from application.telemetry.cache import TelemetryReportCache
    from application.telemetry.report_service import TelemetryReportService

    mock_repo = MagicMock()
    sample_df = _create_sample_telemetry_df()
    mock_repo.get_events_dataframe.return_value = sample_df

    cache = TelemetryReportCache()
    service = TelemetryReportService(repository=mock_repo, cache=cache)

    start = datetime(2026, 10, 10, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 12, 23, 59, 59, tzinfo=timezone.utc)

    report, is_hit = service.get_report(start_date=start, end_date=end)

    assert not is_hit
    assert mock_repo.get_events_dataframe.called
    assert len(report.metrics.events_per_day) == 3
    assert len(report.metrics.error_rate_by_type) == 3
    assert len(report.metrics.auth_failure_rate) == 3


# --- T016: calculate_auth_failure_rate Tests (US3) ---


def test_calculate_auth_failure_rate_standard() -> None:
    """T016: Aggregates total and failed login attempts per day and computes failure ratios."""
    df = _create_sample_telemetry_df()
    results = calculate_auth_failure_rate(df)

    assert isinstance(results, list)
    assert len(results) == 3

    # Sample data contains:
    # 2026-10-10: 1 failed (auth_login_failed) -> total=1, failed=1, rate=1.0
    # 2026-10-11: 2 failed (auth_login_failed x 2) -> total=2, failed=2, rate=1.0
    # 2026-10-12: 1 success (user_login_succeeded) -> total=1, failed=0, rate=0.0
    dates = [item["date"] if isinstance(item, dict) else item.date for item in results]
    totals = [
        item["total_attempts"] if isinstance(item, dict) else item.total_attempts
        for item in results
    ]
    faileds = [
        item["failed_attempts"] if isinstance(item, dict) else item.failed_attempts
        for item in results
    ]
    rates = [
        item["failure_rate"] if isinstance(item, dict) else item.failure_rate for item in results
    ]

    assert dates == ["2026-10-10", "2026-10-11", "2026-10-12"]
    assert totals == [1, 2, 1]
    assert faileds == [1, 2, 0]
    assert rates == [1.0, 1.0, 0.0]


def test_calculate_auth_failure_rate_mixed_day() -> None:
    """T016: Correctly calculates failure_rate as failed_attempts / total_attempts with decimal precision."""
    data = [
        {
            "event_id": f"evt-{i}",
            "timestamp": "2026-10-15T10:00:00Z",
            "event_type": "auth_login_failed" if i < 3 else "user_login_succeeded",
        }
        for i in range(10)  # 3 failed, 7 succeeded -> total 10, failure rate = 0.3
    ]
    df = pd.DataFrame(data)
    results = calculate_auth_failure_rate(df)

    assert len(results) == 1
    res = results[0]
    assert res["date"] == "2026-10-15"
    assert res["total_attempts"] == 10
    assert res["failed_attempts"] == 3
    assert pytest.approx(res["failure_rate"], 0.0001) == 0.3


def test_calculate_auth_failure_rate_zero_division_guard() -> None:
    """T016: Zero login events or empty DataFrame evaluates safely to empty list without exceptions."""
    empty_df = pd.DataFrame(columns=["event_id", "timestamp", "event_type"])
    results = calculate_auth_failure_rate(empty_df)
    assert results == []

    # Non-auth events only
    df_no_auth = pd.DataFrame([
        {
            "event_id": "evt-1",
            "timestamp": "2026-10-15T10:00:00Z",
            "event_type": "inbound_order_created",
        },
        {
            "event_id": "evt-2",
            "timestamp": "2026-10-15T11:00:00Z",
            "event_type": "stock_exit_recorded",
        },
    ])
    results_no_auth = calculate_auth_failure_rate(df_no_auth)
    assert results_no_auth == []


def test_calculate_auth_failure_rate_all_successes() -> None:
    """T016: Day with 100% successful attempts produces failure_rate = 0.0."""
    data = [
        {
            "event_id": f"evt-{i}",
            "timestamp": "2026-10-16T12:00:00Z",
            "event_type": "user_login_succeeded",
        }
        for i in range(5)
    ]
    df = pd.DataFrame(data)
    results = calculate_auth_failure_rate(df)

    assert len(results) == 1
    assert results[0]["total_attempts"] == 5
    assert results[0]["failed_attempts"] == 0
    assert results[0]["failure_rate"] == 0.0


def test_calculate_auth_failure_rate_all_failures() -> None:
    """T016: Day with 100% failed attempts produces failure_rate = 1.0."""
    data = [
        {
            "event_id": f"evt-{i}",
            "timestamp": "2026-10-16T12:00:00Z",
            "event_type": "auth_login_failed",
        }
        for i in range(4)
    ]
    df = pd.DataFrame(data)
    results = calculate_auth_failure_rate(df)

    assert len(results) == 1
    assert results[0]["total_attempts"] == 4
    assert results[0]["failed_attempts"] == 4
    assert results[0]["failure_rate"] == 1.0


def test_calculate_auth_failure_rate_property_level_attempt_status() -> None:
    """T016: Accommodates unified user_login_attempted events with properties.attemptStatus."""
    data = [
        {
            "event_id": "evt-p1",
            "timestamp": "2026-10-17T09:00:00Z",
            "event_type": "user_login_attempted",
            "properties": {"attemptStatus": "failed"},
        },
        {
            "event_id": "evt-p2",
            "timestamp": "2026-10-17T09:30:00Z",
            "event_type": "user_login_attempted",
            "properties": {"attemptStatus": "success"},
        },
        {
            "event_id": "evt-p3",
            "timestamp": "2026-10-17T10:00:00Z",
            "event_type": "user_login_attempted",
            "properties": {"attemptStatus": "failure"},
        },
        {
            "event_id": "evt-p4",
            "timestamp": "2026-10-17T11:00:00Z",
            "event_type": "user_login_attempted",
            "properties": {"attemptStatus": "success"},
        },
    ]
    df = pd.DataFrame(data)
    results = calculate_auth_failure_rate(df)

    assert len(results) == 1
    assert results[0]["total_attempts"] == 4
    assert results[0]["failed_attempts"] == 2
    assert results[0]["failure_rate"] == 0.5


def test_calculate_auth_failure_rate_utc_normalization() -> None:
    """T016: Non-UTC timestamps are converted to UTC before calendar date grouping."""
    data = [
        {
            "event_id": "evt-tz-1",
            # In UTC, 2026-10-18 01:00:00 +04:00 is 2026-10-17 21:00:00 UTC
            "timestamp": "2026-10-18T01:00:00+04:00",
            "event_type": "auth_login_failed",
        },
        {
            "event_id": "evt-tz-2",
            "timestamp": "2026-10-17T22:00:00Z",
            "event_type": "user_login_succeeded",
        },
    ]
    df = pd.DataFrame(data)
    results = calculate_auth_failure_rate(df)

    assert len(results) == 1
    assert results[0]["date"] == "2026-10-17"
    assert results[0]["total_attempts"] == 2
    assert results[0]["failed_attempts"] == 1
    assert results[0]["failure_rate"] == 0.5


def test_calculate_auth_failure_rate_with_date_filtering() -> None:
    """T016: Explicit start_date and end_date filters events accurately."""
    df = _create_sample_telemetry_df()
    start = datetime(2026, 10, 11, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 10, 11, 23, 59, 59, tzinfo=timezone.utc)

    results = calculate_auth_failure_rate(df, start_date=start, end_date=end)
    assert len(results) == 1
    assert results[0]["date"] == "2026-10-11"
    assert results[0]["total_attempts"] == 2
    assert results[0]["failed_attempts"] == 2
    assert results[0]["failure_rate"] == 1.0


def test_calculate_auth_failure_rate_immutability() -> None:
    """T016: Multiple calls produce identical deterministic output without mutating the input DataFrame."""
    df = _create_sample_telemetry_df()
    original_cols = list(df.columns)
    original_len = len(df)

    res1 = calculate_auth_failure_rate(df)
    res2 = calculate_auth_failure_rate(df)

    assert res1 == res2
    assert list(df.columns) == original_cols
    assert len(df) == original_len

