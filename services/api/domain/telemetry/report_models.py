"""Telemetry report domain models and response schemas.

Conforms strictly to TrackFlow Telemetry Plan, data-model.md, and OpenAPI specifications.
Zero framework or database dependencies.
"""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReportingPeriod(BaseModel):
    """Temporal boundaries of the analytical telemetry report."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_date: datetime = Field(
        ...,
        alias="from",
        description="Start timestamp of the reporting window in ISO 8601 UTC (inclusive).",
    )
    to_date: datetime = Field(
        ...,
        alias="to",
        description="End timestamp of the reporting window in ISO 8601 UTC (inclusive).",
    )

    @model_validator(mode="after")
    def validate_period_bounds(self) -> "ReportingPeriod":
        """Validate timezone normalization and interval boundaries.

        Ensures start date is not after end date and normalizes datetimes to UTC.
        """
        if self.from_date.tzinfo is None:
            self.from_date = self.from_date.replace(tzinfo=timezone.utc)
        else:
            self.from_date = self.from_date.astimezone(timezone.utc)

        if self.to_date.tzinfo is None:
            self.to_date = self.to_date.replace(tzinfo=timezone.utc)
        else:
            self.to_date = self.to_date.astimezone(timezone.utc)

        if self.from_date > self.to_date:
            raise ValueError(
                f"Invalid reporting window: start date ('from': {self.from_date.isoformat()}) "
                f"cannot be later than end date ('to': {self.to_date.isoformat()})"
            )
        return self


class DailyEventVolumeMetric(BaseModel):
    """Aggregate event counts bucketed by UTC calendar date."""

    model_config = ConfigDict(extra="forbid")

    date: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="UTC calendar date formatted as YYYY-MM-DD.",
    )
    count: int = Field(
        ...,
        ge=0,
        description="Total count of telemetry events recorded on this date.",
    )


class ErrorDistributionMetric(BaseModel):
    """Categorized breakdown of operational system errors and failure events."""

    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(
        ...,
        min_length=1,
        description="Telemetry event taxonomy name indicating failure/error.",
    )
    count: int = Field(
        ...,
        ge=0,
        description="Number of error occurrences within the time window.",
    )
    percentage: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentage of total operational errors (0.0 to 100.0).",
    )


class AuthFailureRateMetric(BaseModel):
    """Daily authentication attempts, failures, and failure proportion."""

    model_config = ConfigDict(extra="forbid")

    date: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="UTC calendar date formatted as YYYY-MM-DD.",
    )
    total_attempts: int = Field(
        ...,
        ge=0,
        description="Total login attempts (succeeded + failed) on this date.",
    )
    failed_attempts: int = Field(
        ...,
        ge=0,
        description="Total failed login attempts on this date.",
    )
    failure_rate: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Computed failure ratio failed_attempts / total_attempts (0.0 to 1.0).",
    )

    @model_validator(mode="after")
    def validate_attempt_invariants(self) -> "AuthFailureRateMetric":
        """Validate attempts relationship and zero attempt rate behavior."""
        if self.failed_attempts > self.total_attempts:
            raise ValueError(
                f"failed_attempts ({self.failed_attempts}) cannot exceed total_attempts ({self.total_attempts})"
            )
        if self.total_attempts == 0 and self.failure_rate != 0.0:
            raise ValueError(
                f"failure_rate must be 0.0 when total_attempts is 0, got {self.failure_rate}"
            )
        return self


class TelemetryMetrics(BaseModel):
    """Container bundling operational metrics dimensions."""

    model_config = ConfigDict(extra="forbid")

    events_per_day: List[DailyEventVolumeMetric] = Field(
        default_factory=list,
        description="Daily event counts across the reporting period.",
    )
    error_rate_by_type: List[ErrorDistributionMetric] = Field(
        default_factory=list,
        description="Error distribution breakdown by event type.",
    )
    auth_failure_rate: List[AuthFailureRateMetric] = Field(
        default_factory=list,
        description="Daily authentication failure ratios.",
    )


class TelemetryReportResponse(BaseModel):
    """Consolidated top-level payload returned by GET /telemetry/report."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    period: ReportingPeriod = Field(
        ...,
        description="Resolved UTC time window bounds.",
    )
    metrics: TelemetryMetrics = Field(
        ...,
        description="Operational metrics container.",
    )


class TelemetryReportQueryParams(BaseModel):
    """Query parameters for telemetry report requests."""

    model_config = ConfigDict(extra="forbid")

    start_date: Optional[datetime] = Field(
        default=None,
        description="Optional start of reporting window in ISO 8601 UTC format.",
    )
    end_date: Optional[datetime] = Field(
        default=None,
        description="Optional end of reporting window in ISO 8601 UTC format.",
    )


__all__ = [
    "AuthFailureRateMetric",
    "DailyEventVolumeMetric",
    "ErrorDistributionMetric",
    "ReportingPeriod",
    "TelemetryMetrics",
    "TelemetryReportQueryParams",
    "TelemetryReportResponse",
]
