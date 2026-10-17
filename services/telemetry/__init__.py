"""
Telemetry analysis package for operational health monitoring and reporting.

Encapsulates side-effect-free, vectorized Pandas metric functions for daily event volumes,
operational error distributions, and authentication failure rates.
"""

from telemetry.analysis import (
    calculate_auth_failure_rate,
    calculate_error_rate_by_type,
    calculate_events_per_day,
    generate_telemetry_report,
    normalize_telemetry_dataframe,
)

__all__: list[str] = [
    "calculate_auth_failure_rate",
    "calculate_error_rate_by_type",
    "calculate_events_per_day",
    "generate_telemetry_report",
    "normalize_telemetry_dataframe",
]
