# Data Model: Telemetry Report Endpoint & Operational Dashboard

**Feature Branch**: `018-telemetry-report-endpoint`  
**Date**: 2026-10-17  
**Status**: Completed  

---

## 1. Domain Entities & Schemas

### 1.1 ReportingPeriod
Represents the temporal boundaries of the analytical report.

| Field | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `from` | `datetime` (ISO 8601 UTC) | Yes | Start timestamp of the reporting window (inclusive) | `2026-10-10T00:00:00Z` |
| `to` | `datetime` (ISO 8601 UTC) | Yes | End timestamp of the reporting window (inclusive) | `2026-10-17T00:00:00Z` |

**Validation Rules & Invariants**:
- `from <= to`: The start timestamp must not be later than the end timestamp. Inverted ranges yield HTTP 422 Unprocessable Entity.
- Timestamps must be normalized to timezone-aware UTC datetime.

---

### 1.2 DailyEventVolumeMetric
Represents aggregate event counts bucketed by UTC calendar date.

| Field | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `date` | `str` (YYYY-MM-DD) | Yes | UTC calendar date of the aggregated events | `"2026-10-16"` |
| `count` | `int` | Yes | Total count of telemetry events recorded on this date (`>= 0`) | `142` |

**Validation Rules & Invariants**:
- `count >= 0`.
- Dates must be strictly ordered chronologically in ascending sequence.

---

### 1.3 ErrorDistributionMetric
Represents categorized breakdown of operational system errors and failure events.

| Field | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `event_type` | `str` | Yes | Telemetry event taxonomy name indicating failure/error | `"auth_login_failed"` |
| `count` | `int` | Yes | Number of error occurrences within the time window (`>= 0`) | `18` |
| `percentage` | `float` | Yes | Percentage of total operational errors (`0.0 <= percentage <= 100.0`) | `45.0` |

**Validation Rules & Invariants**:
- `count >= 0`.
- Sum of `percentage` across all error types equals 100.0 (or 0.0 if total errors is 0).
- Safe division: If total error count is 0, list is empty or percentage is 0.0 without division-by-zero exceptions.

---

### 1.4 AuthFailureRateMetric
Represents daily authentication attempts, failures, and failure proportion.

| Field | Type | Required | Description | Example |
| :--- | :--- | :--- | :--- | :--- |
| `date` | `str` (YYYY-MM-DD) | Yes | UTC calendar date | `"2026-10-16"` |
| `total_attempts` | `int` | Yes | Total login attempts (`succeeded + failed`) on this date (`>= 0`) | `50` |
| `failed_attempts` | `int` | Yes | Total failed login attempts on this date (`>= 0`) | `5` |
| `failure_rate` | `float` | Yes | Computed ratio `failed_attempts / total_attempts` (`0.0 <= failure_rate <= 1.0`) | `0.1` |

**Validation Rules & Invariants**:
- `0 <= failed_attempts <= total_attempts`.
- If `total_attempts == 0`, `failure_rate = 0.0`.
- Strictly safe against division-by-zero using vectorized `.fillna(0.0)`.

---

### 1.5 TelemetryMetrics
Container object bundling all operational metrics dimensions.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `events_per_day` | `List[DailyEventVolumeMetric]` | Yes | Daily event counts across the period |
| `error_rate_by_type` | `List[ErrorDistributionMetric]` | Yes | Error distribution breakdown by event type |
| `auth_failure_rate` | `List[AuthFailureRateMetric]` | Yes | Daily authentication failure ratios |

---

### 1.6 TelemetryReportResponse
Consolidated top-level payload returned by `GET /telemetry/report`.

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `period` | `ReportingPeriod` | Yes | Resolved UTC time window bounds |
| `metrics` | `TelemetryMetrics` | Yes | Operational metrics object |

```json
{
  "period": {
    "from": "2026-10-10T10:00:00+00:00",
    "to": "2026-10-17T10:00:00+00:00"
  },
  "metrics": {
    "events_per_day": [
      { "date": "2026-10-11", "count": 142 },
      { "date": "2026-10-12", "count": 210 }
    ],
    "error_rate_by_type": [
      { "event_type": "auth_login_failed", "count": 15, "percentage": 60.0 },
      { "event_type": "frontend_error_captured", "count": 10, "percentage": 40.0 }
    ],
    "auth_failure_rate": [
      { "date": "2026-10-11", "total_attempts": 20, "failed_attempts": 2, "failure_rate": 0.1 },
      { "date": "2026-10-12", "total_attempts": 35, "failed_attempts": 1, "failure_rate": 0.0286 }
    ]
  }
}
```

---

## 2. In-Memory Cache Model

### 2.1 CacheEntry
Internal data model for storing precalculated reports.

| Attribute | Type | Description |
| :--- | :--- | :--- |
| `payload` | `Dict[str, Any]` | Serialized JSON response conforming to `TelemetryReportResponse` |
| `created_at` | `float` | Monotonic timestamp (`time.monotonic()`) when the entry was created |
| `expires_at` | `float` | Monotonic timestamp (`created_at + 60.0`) after which the entry is stale |

**Cache Invariants**:
- Cache TTL is strictly 60 seconds.
- Cache Key: Normalized string formatted as `f"{start_date.isoformat()}_{end_date.isoformat()}"`.
- Thread safety: Protected by `threading.Lock` during access and updates.

---

## 3. Relational Storage Model (Existing Read Target)

The analysis pipeline queries the immutable table `telemetry_events` in the relational database:

```sql
CREATE TABLE IF NOT EXISTS telemetry_events (
    event_id VARCHAR(36) PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    session_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255),
    event_type VARCHAR(255) NOT NULL,
    schema_version VARCHAR(32) NOT NULL,
    request_id VARCHAR(255) NOT NULL,
    properties JSON NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL
);
```

**Index Usage**:
- Queries filter on `timestamp` range (`WHERE timestamp >= :start AND timestamp <= :end`), utilizing the index on `timestamp`.
- For auth metrics, queries filter on `event_type IN (...)`, utilizing the index on `event_type`.
