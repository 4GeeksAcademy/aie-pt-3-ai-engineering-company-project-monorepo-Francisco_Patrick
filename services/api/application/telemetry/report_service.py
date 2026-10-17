"""Telemetry reporting orchestration service.

Coordinates temporal window resolution, thread-safe in-memory caching,
persistence queries, and metrics aggregation conforming strictly to TrackFlow data-model.md
and OpenAPI specifications.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from application.telemetry.cache import TelemetryReportCache
from domain.telemetry.ports import TelemetryRepositoryPort
from domain.telemetry.report_models import (
    AuthFailureRateMetric,
    DailyEventVolumeMetric,
    ErrorDistributionMetric,
    ReportingPeriod,
    TelemetryMetrics,
    TelemetryReportResponse,
)


class TelemetryReportService:
    """Orchestrates operational health reporting with 60-second in-memory caching."""

    def __init__(
        self,
        repository: TelemetryRepositoryPort,
        cache: Optional[TelemetryReportCache] = None,
        analysis_runner: Optional[Callable[..., TelemetryMetrics]] = None,
    ) -> None:
        """Initialize service with persistence repository and cache collaborators.

        Args:
            repository: Relational or memory repository port for extracting telemetry records.
            cache: Thread-safe in-memory cache instance (defaults to TelemetryReportCache).
            analysis_runner: Optional custom metric runner function.
        """
        self._repository = repository
        self._cache = cache if cache is not None else TelemetryReportCache()
        self._analysis_runner = analysis_runner

    def get_report(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Tuple[TelemetryReportResponse, bool]:
        """Resolve reporting window, query or calculate metrics, and return response with cache hit indicator.

        Args:
            start_date: Optional start datetime of the reporting window.
            end_date: Optional end datetime of the reporting window.

        Returns:
            Tuple of (TelemetryReportResponse, is_cache_hit boolean).

        Raises:
            ValueError: If start_date is later than end_date.
        """
        is_default_window = start_date is None and end_date is None
        now_utc = datetime.now(timezone.utc)

        if is_default_window:
            resolved_end = now_utc
            resolved_start = now_utc - timedelta(days=7)
        else:
            resolved_end = end_date if end_date is not None else now_utc
            resolved_start = (
                start_date if start_date is not None else (resolved_end - timedelta(days=7))
            )

        # Normalize to UTC aware datetimes
        if resolved_start.tzinfo is None:
            resolved_start = resolved_start.replace(tzinfo=timezone.utc)
        else:
            resolved_start = resolved_start.astimezone(timezone.utc)

        if resolved_end.tzinfo is None:
            resolved_end = resolved_end.replace(tzinfo=timezone.utc)
        else:
            resolved_end = resolved_end.astimezone(timezone.utc)

        if resolved_start > resolved_end:
            raise ValueError(
                f"Invalid reporting window: start date ('{resolved_start.isoformat()}') "
                f"cannot be later than end date ('{resolved_end.isoformat()}')"
            )

        # Determine cache key: static 'default_7d' for unparameterized queries within 60s,
        # or deterministic ISO datetime key for custom explicit ranges
        cache_key = (
            "default_7d"
            if is_default_window
            else TelemetryReportCache.generate_key(resolved_start, resolved_end)
        )

        cached_payload = self._cache.get(cache_key)
        if cached_payload is not None:
            return TelemetryReportResponse.model_validate(cached_payload), True

        # Compute metrics
        metrics = self._compute_metrics(resolved_start, resolved_end)
        period = ReportingPeriod(from_date=resolved_start, to_date=resolved_end)
        report = TelemetryReportResponse(period=period, metrics=metrics)

        # Store in cache with 60-second TTL
        self._cache.set(cache_key, report.model_dump(by_alias=True, mode="json"))

        return report, False

    def _compute_metrics(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> TelemetryMetrics:
        """Execute metrics pipeline or initial aggregation over raw telemetry records."""
        # Check if vectorized Pandas analysis runner is plugged in or available
        runner = self._analysis_runner
        if runner is None:
            try:
                from telemetry.analysis import generate_telemetry_report

                runner = generate_telemetry_report
            except ImportError:
                try:
                    from services.telemetry.analysis import generate_telemetry_report

                    runner = generate_telemetry_report
                except ImportError:
                    runner = None

        if runner is not None:
            df = self._repository.get_events_dataframe(start_date, end_date)
            return runner(df, start_date=start_date, end_date=end_date)

        # Fallback / initial Phase 3 aggregation using repository records
        events = self._repository.get_events_in_range(start_date, end_date)
        return self._aggregate_initial_metrics(events)

    def _aggregate_initial_metrics(self, events: List[Any]) -> TelemetryMetrics:
        """Initial baseline aggregation conforming to TelemetryMetrics schemas."""
        daily_counts: Dict[str, int] = {}
        error_counts: Dict[str, int] = {}
        auth_attempts: Dict[str, Dict[str, int]] = {}

        error_keywords = ("error", "fail", "exception", "crash", "threshold")
        auth_types = {
            "auth_login_failed",
            "auth_login_succeeded",
            "user_login_failed",
            "user_login_succeeded",
            "user_login_attempted",
        }

        for ev in events:
            # Normalize timestamp string or datetime
            ts = ev.timestamp
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            else:
                ts = ts.astimezone(timezone.utc)

            date_str = ts.strftime("%Y-%m-%d")
            daily_counts[date_str] = daily_counts.get(date_str, 0) + 1

            event_type = ev.event_type
            if any(kw in event_type.lower() for kw in error_keywords):
                error_counts[event_type] = error_counts.get(event_type, 0) + 1

            if event_type in auth_types:
                if date_str not in auth_attempts:
                    auth_attempts[date_str] = {"total": 0, "failed": 0}
                auth_attempts[date_str]["total"] += 1
                if "failed" in event_type.lower():
                    auth_attempts[date_str]["failed"] += 1

        # Events per day
        events_per_day = [
            DailyEventVolumeMetric(date=d, count=c) for d, c in sorted(daily_counts.items())
        ]

        # Error rate by type
        total_errors = sum(error_counts.values())
        error_rate_by_type = [
            ErrorDistributionMetric(
                event_type=etype,
                count=cnt,
                percentage=round((cnt / total_errors) * 100.0, 2) if total_errors > 0 else 0.0,
            )
            for etype, cnt in sorted(error_counts.items(), key=lambda item: item[1], reverse=True)
        ]

        # Auth failure rate
        auth_failure_rate = [
            AuthFailureRateMetric(
                date=d,
                total_attempts=vals["total"],
                failed_attempts=vals["failed"],
                failure_rate=(
                    round(vals["failed"] / vals["total"], 4) if vals["total"] > 0 else 0.0
                ),
            )
            for d, vals in sorted(auth_attempts.items())
        ]

        return TelemetryMetrics(
            events_per_day=events_per_day,
            error_rate_by_type=error_rate_by_type,
            auth_failure_rate=auth_failure_rate,
        )


__all__ = ["TelemetryReportService"]
