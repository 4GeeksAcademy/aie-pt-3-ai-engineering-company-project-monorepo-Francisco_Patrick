"""Vectorized Pandas operational telemetry analysis pipeline.

Conforms strictly to TrackFlow Telemetry Plan, research.md, and data-model.md:
- Side-effect free, deterministic metric functions.
- Mandatory UTC datetime normalization before any temporal grouping.
- Purely vectorized Pandas transformations (zero procedural for/while loops).
- Safe against division-by-zero, empty datasets, and invalid dates.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import pandas as pd

try:
    from domain.telemetry.report_models import (
        AuthFailureRateMetric,
        DailyEventVolumeMetric,
        ErrorDistributionMetric,
        TelemetryMetrics,
    )
except ImportError:
    from services.api.domain.telemetry.report_models import (
        AuthFailureRateMetric,
        DailyEventVolumeMetric,
        ErrorDistributionMetric,
        TelemetryMetrics,
    )


def normalize_telemetry_dataframe(
    df: pd.DataFrame,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> pd.DataFrame:
    """Normalize timestamp column to timezone-aware UTC datetime and filter within bounds.

    Pure vectorized transformation that returns an isolated DataFrame copy to preserve
    immutability of input data.

    Args:
        df: Input pandas DataFrame with raw telemetry records.
        start_date: Optional UTC start datetime filter (inclusive).
        end_date: Optional UTC end datetime filter (inclusive).

    Returns:
        pd.DataFrame with normalized 'timestamp' (UTC datetime64) and 'date' (YYYY-MM-DD str).
    """
    if df.empty or "timestamp" not in df.columns:
        res = df.copy()
        if "timestamp" in res.columns:
            res["timestamp"] = pd.to_datetime(res["timestamp"], utc=True)
        res["date"] = pd.Series(dtype="str")
        return res

    data = df.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"], utc=True)

    if start_date is not None:
        start_utc = (
            start_date.replace(tzinfo=timezone.utc)
            if start_date.tzinfo is None
            else start_date.astimezone(timezone.utc)
        )
        data = data[data["timestamp"] >= start_utc]

    if end_date is not None:
        end_utc = (
            end_date.replace(tzinfo=timezone.utc)
            if end_date.tzinfo is None
            else end_date.astimezone(timezone.utc)
        )
        data = data[data["timestamp"] <= end_utc]

    data["date"] = data["timestamp"].dt.strftime("%Y-%m-%d")
    return data


def calculate_events_per_day(
    df: pd.DataFrame,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Compute daily telemetry event volume aggregated by UTC calendar date.

    Uses vectorized grouping without procedural loops. Results are ordered
    chronologically in ascending sequence.

    Args:
        df: Input DataFrame containing telemetry event records.
        start_date: Optional start datetime filter.
        end_date: Optional end datetime filter.

    Returns:
        List of dicts formatted as [{'date': 'YYYY-MM-DD', 'count': int}].
    """
    if df.empty or "timestamp" not in df.columns:
        return []

    data = normalize_telemetry_dataframe(df, start_date=start_date, end_date=end_date)
    if data.empty:
        return []

    grouped = (
        data.groupby("date", as_index=False)
        .size()
        .rename(columns={"size": "count"})
        .sort_values(by="date", ascending=True)
    )

    return grouped.to_dict(orient="records")


def calculate_error_rate_by_type(
    df: pd.DataFrame,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Categorize and calculate percentage distribution of operational error/failure events.

    Filters for event types containing error keywords (error, fail, exception, threshold, crash)
    using vectorized string regex matching. Results are sorted by count descending.

    Args:
        df: Input DataFrame containing telemetry event records.
        start_date: Optional start datetime filter.
        end_date: Optional end datetime filter.

    Returns:
        List of dicts formatted as [{'event_type': str, 'count': int, 'percentage': float}].
    """
    if df.empty or "event_type" not in df.columns:
        return []

    data = normalize_telemetry_dataframe(df, start_date=start_date, end_date=end_date)
    if data.empty:
        return []

    error_mask = data["event_type"].str.contains(
        r"error|fail|exception|threshold|crash",
        case=False,
        regex=True,
        na=False,
    )
    errors = data[error_mask]
    if errors.empty:
        return []

    grouped = (
        errors.groupby("event_type", as_index=False)
        .size()
        .rename(columns={"size": "count"})
    )

    total_errors = int(grouped["count"].sum())
    if total_errors == 0:
        return []

    grouped["percentage"] = (grouped["count"] / total_errors * 100.0).round(2)
    grouped = grouped.sort_values(by=["count", "event_type"], ascending=[False, True])

    return grouped.to_dict(orient="records")


def calculate_auth_failure_rate(
    df: pd.DataFrame,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Calculate daily login attempts, failures, and authentication failure rates.

    Filters for authentication events (such as auth_login_failed, auth_login_succeeded,
    user_login_failed, user_login_succeeded, user_login_attempted) and evaluates failure
    ratios grouped by UTC calendar date.

    Uses strictly vectorized operations with safe division-by-zero handling (.fillna(0.0)).
    Results are ordered chronologically in ascending sequence.

    Args:
        df: Input DataFrame containing telemetry event records.
        start_date: Optional start datetime filter.
        end_date: Optional end datetime filter.

    Returns:
        List of dicts formatted as:
        [{'date': 'YYYY-MM-DD', 'total_attempts': int, 'failed_attempts': int, 'failure_rate': float}]
    """
    if df.empty or "event_type" not in df.columns:
        return []

    data = normalize_telemetry_dataframe(df, start_date=start_date, end_date=end_date)
    if data.empty:
        return []

    # Filter for authentication events (taxonomy keywords: auth_login, user_login, login)
    auth_mask = data["event_type"].str.contains(
        r"(?:auth|user)?_?login",
        case=False,
        regex=True,
        na=False,
    )
    auth_events = data[auth_mask].copy()
    if auth_events.empty:
        return []

    # Check for failure in event_type name (e.g. auth_login_failed, user_login_failed)
    failed_type_mask = auth_events["event_type"].str.contains(
        r"fail",
        case=False,
        regex=True,
        na=False,
    )

    # Check for failure in properties (e.g. {"attemptStatus": "failed"}) for unified attempt events
    if "properties" in auth_events.columns:
        prop_status = auth_events["properties"].apply(
            lambda p: str(p.get("attemptStatus") or p.get("status") or "").lower()
            if isinstance(p, dict)
            else ""
        )
        prop_failed_mask = prop_status.isin(["failed", "failure", "error", "rejected"])
        is_failed = failed_type_mask | prop_failed_mask
    else:
        is_failed = failed_type_mask

    auth_events["is_failed"] = is_failed.astype(int)

    grouped = (
        auth_events.groupby("date", as_index=False)
        .agg(
            total_attempts=("event_type", "count"),
            failed_attempts=("is_failed", "sum"),
        )
        .sort_values(by="date", ascending=True)
    )

    # Vectorized division with zero-division handling
    ratio = (
        (grouped["failed_attempts"] / grouped["total_attempts"])
        .replace([float("inf"), float("-inf")], 0.0)
        .fillna(0.0)
        .round(4)
    )
    grouped["failure_rate"] = ratio

    grouped["total_attempts"] = grouped["total_attempts"].astype(int)
    grouped["failed_attempts"] = grouped["failed_attempts"].astype(int)
    grouped["failure_rate"] = grouped["failure_rate"].astype(float)

    return grouped.to_dict(orient="records")


def generate_telemetry_report(
    df: pd.DataFrame,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> TelemetryMetrics:
    """Consolidated pipeline runner executing operational metrics transformations.

    Orchestrates daily event volume, error distribution, and authentication metrics
    into a validated TelemetryMetrics domain model.

    Args:
        df: Input DataFrame containing telemetry event records.
        start_date: Optional UTC start datetime filter.
        end_date: Optional UTC end datetime filter.

    Returns:
        Validated TelemetryMetrics domain model instance.
    """
    raw_events_per_day = calculate_events_per_day(df, start_date=start_date, end_date=end_date)
    raw_error_rate = calculate_error_rate_by_type(df, start_date=start_date, end_date=end_date)
    raw_auth_failure_rate = calculate_auth_failure_rate(
        df, start_date=start_date, end_date=end_date
    )

    events_per_day_models = [
        DailyEventVolumeMetric(date=item["date"], count=int(item["count"]))
        for item in raw_events_per_day
    ]
    error_rate_models = [
        ErrorDistributionMetric(
            event_type=item["event_type"],
            count=int(item["count"]),
            percentage=float(item["percentage"]),
        )
        for item in raw_error_rate
    ]
    auth_failure_rate_models = [
        AuthFailureRateMetric(
            date=item["date"],
            total_attempts=int(item["total_attempts"]),
            failed_attempts=int(item["failed_attempts"]),
            failure_rate=float(item["failure_rate"]),
        )
        for item in raw_auth_failure_rate
    ]

    return TelemetryMetrics(
        events_per_day=events_per_day_models,
        error_rate_by_type=error_rate_models,
        auth_failure_rate=auth_failure_rate_models,
    )


__all__ = [
    "calculate_auth_failure_rate",
    "calculate_error_rate_by_type",
    "calculate_events_per_day",
    "generate_telemetry_report",
    "normalize_telemetry_dataframe",
]
