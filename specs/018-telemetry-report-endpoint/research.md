# Research & Technical Decisions: Telemetry Report Endpoint & Operational Dashboard

**Feature Branch**: `018-telemetry-report-endpoint`  
**Date**: 2026-10-17  
**Status**: Completed  

---

## 1. Context & Objectives

The goal is to provide operational observability into system health without impacting database performance or mixing technical metrics with business metrics. The feature consists of:
1. **Analysis Pipeline with Pandas** (`services/telemetry/analysis.py`): Vectorized, side-effect-free metric functions extracting operational dimensions (`events_per_day`, `error_rate_by_type`, `auth_failure_rate`).
2. **FastAPI Report Endpoint** (`GET /telemetry/report` and `/api/v1/telemetry/report`): Resolves time period once (default: past 7 days UTC), passes explicit bounds to pipeline functions, and caches responses in memory with a 60-second TTL.
3. **Engineering Telemetry Dashboard** (`uis/backoffice/app/telemetry/page.tsx`): Lightweight, accessible Next.js UI rendering visual charts/tables of operational metrics with period display and error resilience.

---

## 2. Technical Decisions & Analysis

### Decision 1: Pandas Temporal Aggregation & Strict UTC Datetime Normalization

- **Context**: Timestamps stored in relational database tables (`telemetry_events`) can arrive as ISO 8601 strings, naive datetime objects, or timezone-aware datetimes with variable microsecond precision. If grouped without explicit conversion to UTC datetime, string lexicographical comparisons or timezone mismatches create incorrect date groupings with no visible runtime error.
- **Decision**: 
  - In `services/telemetry/analysis.py`, every metric function converts the timestamp column using:
    ```python
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    ```
  - For daily grouping (`events_per_day`, `auth_failure_rate`), the pipeline derives a normalized calendar date column:
    ```python
    df["date"] = df["timestamp"].dt.strftime("%Y-%m-%d")
    ```
  - All aggregations exclusively use vectorized Pandas methods (`.groupby()`, `.agg()`, `.count()`, `.sum()`, `.mean()`) with **zero procedural loops** (`for`, `while`).
  - Empty dataset handling: When queries yield zero records, functions immediately return empty lists `[]` or standard empty structures with expected schema keys, completely avoiding `NaN` or indexing exceptions.
- **Rationale**: Vectorized operations in Pandas guarantee deterministic execution and sub-millisecond calculation times for tens of thousands of records, while mandatory UTC normalization guarantees identical grouping across local environments and deployment nodes.
- **Alternatives Considered**:
  - *Pure SQL aggregation (`GROUP BY strftime(...)`)*: Rejected because the architectural specification requires metric logic to be encapsulated in a reusable Python Pandas analysis pipeline (`services/telemetry/analysis.py`), enabling identical offline batch execution, testing with mock dataframes, and dynamic multi-dimensional slicing.
  - *Procedural Python loops with `collections.defaultdict`*: Rejected by specification constraint ("Do not use loops to calculate metrics — only Pandas operations").

---

### Decision 2: In-Memory Caching Architecture & 60-Second TTL

- **Context**: Continuous polling from engineering dashboards and monitoring agents could repeatedly query the database and re-run Pandas aggregations for identical date ranges. The specification requires an in-memory cache with a 60-second TTL keyed by the resolved period (`start_date`, `end_date`).
- **Decision**:
  - Implement a thread-safe, lightweight in-memory cache class `TelemetryReportCache` in `services/api/application/telemetry/cache.py` (or within the service layer).
  - Cache Key: A deterministic string tuple formed by the canonical ISO 8601 UTC strings: `f"{start_date.isoformat()}_{end_date.isoformat()}"`.
  - Cache Value: A dataclass `CacheEntry` holding the serialized response dictionary and an expiration timestamp `expires_at = time.monotonic() + 60.0`.
  - Cache Eviction: Lazy expiration on read (if `time.monotonic() >= entry.expires_at`, delete key and recompute). A simple LRU/cleanup cap (max 256 keys) ensures bounded memory footprint.
  - Concurrency Safety: Use a standard Python `threading.Lock` to prevent race conditions or cache corruption during concurrent read/write operations.
- **Rationale**: Minimal complexity, zero external dependencies (no Redis requirement for single-process monitoring), thread-safe in FastAPI's asynchronous threadpool, sub-millisecond response latency (< 1ms on cache hits), and zero persistence load during active dashboard viewing.
- **Alternatives Considered**:
  - *Redis / Memcached*: Overkill for a local single-node service; violates zero-overhead principle and adds deployment complexity.
  - *`functools.lru_cache`*: Does not support time-based TTL invalidation natively without external wrappers.

---

### Decision 3: Event Catalog Taxonomy & Metric Functions

- **Context**: The existing database table `telemetry_events` stores `event_type`, `timestamp`, `session_id`, `user_id`, and `properties` (JSON). We need 3 distinct operational dimensions answering technical system health questions:
  1. Event volume over time
  2. Operational error distribution
  3. Authentication flow reliability
- **Decision**:
  - **Metric 1: Daily Event Volume (`events_per_day`)**:
    - Query: `SELECT timestamp, event_type FROM telemetry_events WHERE timestamp >= :start AND timestamp <= :end`
    - Pandas pipeline: Filter within range, convert `timestamp` to UTC datetime, group by `date` (`%Y-%m-%d`), count records, return `[{"date": str, "count": int}]` sorted chronologically.
  - **Metric 2: Operational Error Distribution (`error_rate_by_type`)**:
    - Filter for failure and error events: `event_type.str.contains("error|fail|exception|threshold|crash", case=False, regex=True)` or events with properties containing error flags.
    - Group by `event_type`, compute total count and relative proportion of all error events, return `[{"event_type": str, "count": int, "percentage": float}]` sorted by count descending.
  - **Metric 3: Authentication Failure Rate (`auth_failure_rate`)**:
    - Query: `SELECT timestamp, event_type, properties FROM telemetry_events WHERE event_type IN ('auth_login_failed', 'auth_login_succeeded', 'user_login_failed', 'user_login_succeeded', 'user_login_attempted') AND timestamp >= :start AND timestamp <= :end`
    - Pandas pipeline: Identify success vs. failure (either by discrete event type or `properties.attemptStatus`), group by `date`, compute `total_attempts = sum(attempts)` and `failed_attempts = sum(failed)`.
    - Division-by-zero guard: `failure_rate = (failed_attempts / total_attempts).fillna(0.0)`. Return `[{"date": str, "total_attempts": int, "failed_attempts": int, "failure_rate": float}]`.
- **Rationale**: Fully aligns with the TrackFlow event catalog captured in previous projects (e.g. `inbound_order_created`, `stock_exit_recorded`, `auth_login_failed`, `frontend_error_captured`). Strictly avoids business-domain metrics (revenue, sales conversions).
- **Alternatives Considered**:
  - *Combining all queries into one giant Pandas read*: Loading all events in a single SQL query `SELECT * FROM telemetry_events WHERE timestamp BETWEEN ...` is efficient for normal date windows (< 100k events in 7 days) and allows metric functions to accept either the shared DataFrame or connection. The pipeline will provide both a consolidated runner and individual standalone functions.

---

### Decision 4: Backoffice Dashboard UI Implementation

- **Context**: The engineering team needs a visual view in `uis/backoffice/` (route: `/telemetry`) to inspect operational metrics without manual SQL queries or reading raw JSON. The UI must conform to strict TypeScript, Core Web Vitals, and responsive styling.
- **Decision**:
  - Create a Next.js client component page at `uis/backoffice/app/telemetry/page.tsx` with subcomponents for:
    1. Active Period Indicator & Range Selector (defaults to 7-day UTC period, with controls for last 24h, 7d, 30d).
    2. Daily Event Volume Chart: Pure SVG/Tailwind responsive bar chart rendering daily counts with hover tooltips and axis labels.
    3. Error Distribution Table & Progress Bars: Clean table showing error types, counts, and horizontal proportion bars.
    4. Authentication Reliability Card: Metric card showing overall failure rate with daily trend visualization and status badges (< 5% Normal, 5-15% Warning, > 15% Critical).
    5. Refresh button with cache age indicator ("Cached for up to 60s").
    6. Non-crashing empty and error states with retry actions.
  - Zero heavy external charting dependencies: Pure CSS/SVG visualization avoids bundle bloat, ensures LCP ≤ 1.0s, and eliminates third-party library vulnerabilities.
  - Add navigation link in `uis/backoffice/components/Header.tsx` under "Telemetry".
- **Rationale**: Minimal footprint, ultra-fast rendering, zero new npm dependencies, 100% compliant with TrackFlow design system (dark slate/emerald/cyan palette) and Core Web Vitals constraints.
- **Alternatives Considered**:
  - *Recharts or Chart.js*: Adds > 150KB to bundle size, potential hydration mismatch issues in React 18 / Next.js 14 SSR. Pure SVG / Tailwind gives complete control and zero overhead.

---

### Decision 5: Monorepo Boundaries & Module Architecture

- **Context**: The user specified `services/telemetry/analysis.py` for the pipeline and `GET /telemetry/report` in FastAPI. Constitution Principle I requires domain isolation and clean layered architecture.
- **Decision**:
  - Create `services/telemetry/` package containing:
    - `services/telemetry/__init__.py`
    - `services/telemetry/analysis.py` (pure vectorized Pandas functions: `calculate_events_per_day`, `calculate_error_rate_by_type`, `calculate_auth_failure_rate`, `generate_telemetry_report`)
  - Integrate with `services/api/`:
    - Add report routes to `services/api/presentation/api/v1/telemetry.py` (which is already mounted at both `/telemetry` and `/api/v1/telemetry`).
    - Add response schemas in `services/api/domain/telemetry/models.py` or `services/api/presentation/api/v1/telemetry_schemas.py`.
    - Add cache implementation in `services/api/application/telemetry/cache.py`.
    - Publish shared TypeScript definitions to `packages/shared/types/telemetry.ts` and re-export from `packages/shared/types/index.ts`.
- **Rationale**: Perfectly respects the requested file path (`services/telemetry/analysis.py`) while maintaining seamless integration with the existing FastAPI application, database connections, and frontend clients.
