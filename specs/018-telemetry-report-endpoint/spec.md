# Feature Specification: Telemetry Report Endpoint & Operational Dashboard

**Feature Branch**: `018-telemetry-report-endpoint`

**Created**: 2026-10-17

**Status**: Draft

**Input**: User description: "/speckit-specify # feat: telemetry report endpoint\n## Overview\nWrite the analysis pipeline. For each relevant operational dimension, one Python function that loads the relevant events, transforms them with Pandas, and returns a serialisable result. Then a `GET /telemetry/report` endpoint that serves them together.\nTwo non-negotiable rules: first, don't calculate anything inside the endpoint on every request — the pipeline goes separately and the endpoint calls it, with cache. Second, convert timestamps to `datetime` before any grouping — if you don't, you'll get incorrect groups with no visible error, and you'll spend hours finding the bug.\nOne important clarification: this is not the report for the CEO. No conversion rates, no revenue. Today I want to know how healthy the system is: event volume, error rate, latency, which event types dominate. Metrics with a real temporal dimension, not a global number with no context.\n## What To Do\n### Phase 1 — Analysis Pipeline with Pandas\n* Create `services/telemetry/analysis.py` with at least 3 metric functions, each encapsulating the calculation of a distinct operational dimension from your own event catalogue. Valid examples (adapt to what you actually captured):\n* Each function must be independent and side-effect free — calling it twice with the same parameters must produce the same result.\n* Do not use loops to calculate metrics — only Pandas operations (`.groupby()`, `.agg()`, `.count()`, `.sum()`, `.mean()`).\n#### Constrains:\n* The metrics you choose must answer technical or operational questions about the system's behaviour — volume, errors, latency, availability — not business questions (sales, conversion, revenue). A business report disguised as a technical report will not be accepted; that analysis belongs to the Data Pipelines milestone.\n### Phase 2 — Report Endpoint\n* Create the `GET /telemetry/report` endpoint in FastAPI. It must:\n    * Accept optional query parameters `start_date` and `end_date` in ISO 8601 format; if not provided, default to the last 7 days (`start_date = now − 7d`, `end_date = now`, both UTC)\n    * Resolve the period once and pass `start_date` / `end_date` to every metric function — functions do not apply their own default window\n    * Call the metric functions from the analysis pipeline with those parameters\n    * Return a JSON with the structure: `{\"period\": {\"from\": \"...\", \"to\": \"...\"}, \"metrics\": {\"events_per_day\": [...], \"error_rate_by_type\": [...]}}`\n* The endpoint must not run the pipeline on every request — implement a simple in-memory cache with a 60-second TTL. If the same `start_date`/`end_date` combination is requested within the TTL, return the cached result without recalculating.\n### Phase 3 — Authentication Metric\n* If you instrumented the authentication flow in the previous project, add a third metric function that calculates the daily login failure rate: `user_login_failed` divided by total login attempts (`user_login_failed` + `user_login_succeeded`) per day. Load both event types with `event_type IN (...)` in SQL, then compute the ratio in Pandas. Include it in the endpoint under the key `auth_failure_rate`.\n### Phase 4 — Simple Visual Dashboard\n* Build a minimal page in `uis/backoffice/` (e.g. `/telemetry`) that fetches `GET /telemetry/report` and renders it visually — a chart or table per metric is enough (bar/line chart for `events_per_day`, `error_rate_by_type`, etc.). Use any charting library already available in the frontend, or a simple HTML table if you'd rather keep it minimal.\n* The page should let you pick or display the current `period` (`from`/`to`) being shown, so it's clear what window the numbers cover.\n* This dashboard is a technical view for the engineering team, not a business dashboard — keep it visualizing the same operational metrics from your report, nothing more.\n* No need for polish here: a working, readable visualization of real data is the goal, not a design exercise."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operational System Health Telemetry Reporting with Caching (Priority: P1)

As a platform operations engineer, I need a consolidated reporting endpoint that aggregates operational telemetry metrics (such as daily event throughput and error distributions) over a configurable time window with intelligent in-memory caching, so that engineering teams can continuously inspect system health without subjecting the database to heavy analytical query load.

**Why this priority**: Serves as the primary operational data API. Without a performant, cached reporting endpoint, systems monitoring tools and dashboards would trigger redundant full-table analytical queries on every poll.

**Independent Test**: Request `GET /telemetry/report` without parameters and verify that a 7-day UTC period is resolved with calculated metrics; re-request within 60 seconds with identical parameters and verify the cached result is returned instantly without re-querying the data store.

**Acceptance Scenarios**:

1. **Given** no query parameters are provided, **When** a client sends `GET /telemetry/report`, **Then** the service resolves a default window spanning the past 7 days up to the current UTC timestamp and returns `200 OK` with `{ "period": { "from": "...", "to": "..." }, "metrics": { ... } }`.
2. **Given** custom `start_date` and `end_date` query parameters in ISO 8601 format, **When** a client requests `GET /telemetry/report`, **Then** the service resolves that specific UTC window and computes metrics strictly within the requested bounds.
3. **Given** a report request has completed and populated the cache, **When** a second identical request is received within 60 seconds, **Then** the service serves the response directly from in-memory cache without calling analytical computation functions or executing database queries.
4. **Given** 60 seconds have elapsed since a cached report was generated, **When** a request with the same period is received, **Then** the cache entry is invalidated, the analysis pipeline re-executes, and fresh metrics are returned and re-cached.

---

### User Story 2 - Temporal Operational Metrics Pipeline (Priority: P1)

As a site reliability engineer, I need modular, independent metric calculation functions that extract operational telemetry events from storage and transform them using vectorized groupings and aggregations, so that temporal trends in event volume, error classifications, and system latencies are accurately represented without procedural calculation drift.

**Why this priority**: Foundational data processing layer. Ensures all metrics are mathematically consistent, side-effect free, and properly anchored to UTC timestamps before any temporal grouping occurs.

**Independent Test**: Provide fixed sample datasets to each metric calculation function with explicit start and end dates; verify that calling each function multiple times produces identical, deterministic output structured as JSON-serializable dictionaries and lists.

**Acceptance Scenarios**:

1. **Given** a collection of raw telemetry event records with diverse timestamps and event types, **When** the event volume metric function executes, **Then** timestamps are parsed into UTC datetimes, grouped by calendar date, and transformed into daily event counts (`events_per_day`).
2. **Given** operational errors and failure events recorded in the system, **When** the error metric function executes, **Then** error occurrences are aggregated by event category or error type (`error_rate_by_type`) to reveal failure distributions across services.
3. **Given** system telemetry event properties containing execution latencies or durations, **When** the latency metric function executes, **Then** average and percentile durations are computed per service or day without procedural loops.
4. **Given** identical input parameters and unchanged database state, **When** any metric function is invoked repeatedly, **Then** it produces identical output without mutating external state or maintaining hidden session buffers.

---

### User Story 3 - Authentication Flow Reliability & Failure Rate Tracking (Priority: P2)

As a security and systems administrator, I need daily visibility into authentication attempt volumes and failure rates, so that authentication service outages, credential stuffing spikes, or misconfigured integrations can be detected rapidly.

**Why this priority**: Authentication is a critical operational gateway. Monitoring the daily ratio of failed login attempts against total login volume provides immediate security posture awareness and system availability signals.

**Independent Test**: Execute the authentication metric function against a dataset containing successful and failed login attempts across multiple days; verify that the daily ratio of failures to total attempts is correctly computed and returned under the key `auth_failure_rate`.

**Acceptance Scenarios**:

1. **Given** telemetry records containing successful and failed login attempts, **When** the authentication metric function is invoked with a date range, **Then** it aggregates total attempts and failed attempts per day, returning daily failure ratios under `auth_failure_rate`.
2. **Given** a day within the requested window with zero total login attempts, **When** calculating the daily failure rate, **Then** the calculation safely produces 0.0 (or zero attempts) rather than failing with a division-by-zero exception.
3. **Given** the consolidated `GET /telemetry/report` response payload, **When** the response is serialized, **Then** `auth_failure_rate` is included alongside other operational metrics within the `metrics` object.

---

### User Story 4 - Engineering Telemetry Visual Dashboard in Backoffice (Priority: P2)

As an engineering lead or on-call developer, I need a lightweight, dedicated visual dashboard in the Backoffice interface that retrieves and renders the telemetry report metrics, so that engineering teams can assess operational trends without running manual SQL queries or interpreting raw JSON payloads.

**Why this priority**: Enhances human observability. Providing a quick, visual representation of daily event volumes, failure rates, and error distributions makes operational monitoring accessible and actionable.

**Independent Test**: Navigate to the telemetry dashboard route in the Backoffice interface; verify that the active reporting period is visibly displayed, data is retrieved from `GET /telemetry/report`, and clear charts or tables are rendered for each operational dimension.

**Acceptance Scenarios**:

1. **Given** an authenticated user accessing the Backoffice UI, **When** navigating to `/telemetry`, **Then** the page automatically fetches `GET /telemetry/report` and renders visual components for `events_per_day`, `error_rate_by_type`, and `auth_failure_rate`.
2. **Given** the rendered telemetry dashboard, **When** inspecting the header or status bar, **Then** the active reporting time window (`from` and `to` timestamps) is clearly displayed.
3. **Given** a network failure or empty telemetry dataset, **When** the dashboard loads, **Then** it displays an informative, non-crashing empty or error state with a retry action.

---

### Edge Cases

- **Zero Events in Window**: When no events exist within the specified date range, the report returns valid empty arrays or zeroed series for all metrics, rather than failing with exceptions or missing keys.
- **Inverted or Malformed Date Range**: When `start_date` is later than `end_date` or query parameters contain malformed date strings, the endpoint returns a clear `422 Unprocessable Entity` or `400 Bad Request` validation error.
- **Microsecond Timestamp Variations**: When raw event timestamps contain varying ISO formats (with or without fractional seconds or explicit UTC offsets `Z`/`+00:00`), the parser normalizes all records to UTC timezone-aware datetimes before performing date truncation or grouping.
- **High Concurrency Cache Thundering Herd**: When multiple requests for the same date window arrive simultaneously during cache expiry, the cache lookup safely resolves without crashing or corrupting memory.
- **Division by Zero in Rate Metrics**: If a specific day or category has zero denominator events (e.g., zero total login attempts), rate metrics default to 0.0 without generating `NaN` or unhandled exceptions.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST implement an independent analysis pipeline module containing side-effect-free functions that calculate distinct operational metrics over an explicitly provided UTC time window (`start_date`, `end_date`).
- **FR-002**: The pipeline functions MUST NOT rely on default time windows internally; all metric functions MUST receive resolved `start_date` and `end_date` parameters from the caller.
- **FR-003**: All metric functions MUST convert event timestamp data into timezone-aware UTC datetime values prior to executing any temporal grouping or bucketing.
- **FR-004**: Metric transformations MUST use vectorized data operations (such as grouping, aggregation, counts, sums, and means) and MUST NOT use procedural iteration loops (`for`, `while`) for metric calculations.
- **FR-005**: The pipeline MUST provide a daily event volume metric (`events_per_day`) that groups event counts by calendar date across the period.
- **FR-006**: The pipeline MUST provide an error distribution metric (`error_rate_by_type`) that quantifies occurrences of errors, failures, and anomalous system events grouped by event type or category.
- **FR-007**: The pipeline MUST provide an authentication failure rate metric (`auth_failure_rate`) that calculates the daily ratio of failed login attempts to total login attempts.
- **FR-008**: The backend MUST expose an HTTP `GET /telemetry/report` endpoint in FastAPI that accepts optional `start_date` and `end_date` query parameters in ISO 8601 format.
- **FR-009**: When query parameters are omitted, the `GET /telemetry/report` endpoint MUST resolve the analysis period to exactly the preceding 7 days up to the current UTC timestamp.
- **FR-010**: The endpoint MUST invoke the analysis pipeline functions with the resolved period and return a response conforming to `{ "period": { "from": "<iso>", "to": "<iso>" }, "metrics": { "events_per_day": [...], "error_rate_by_type": [...], "auth_failure_rate": [...] } }`.
- **FR-011**: The endpoint MUST implement an in-memory cache with a 60-second time-to-live (TTL) keyed by the resolved `start_date` and `end_date` combination, serving identical requests within the TTL without re-querying persistence storage or re-running analytical calculations.
- **FR-012**: The metrics served by the endpoint MUST strictly address technical and operational behavior (volume, errors, latency, availability) and MUST NOT compute or expose business-domain analytics (revenue, sales, conversion rates).
- **FR-013**: The system MUST provide an engineering telemetry dashboard page in `uis/backoffice/` (e.g., `/telemetry`) that fetches `GET /telemetry/report` and renders visual representations (charts or structured tables) for each operational metric.
- **FR-014**: The telemetry dashboard MUST clearly display the active time period (`from` and `to` timestamps) corresponding to the visual data.

### Key Entities

- **TelemetryReport**: Consolidated operational health payload consisting of a resolved time period and a set of operational metrics.
- **ReportingPeriod**: Time boundary object defining `from` and `to` UTC ISO 8601 timestamps for analysis.
- **DailyEventVolumeMetric**: Time-series entry containing a calendar date string (`date`) and the total count of captured events (`count`).
- **ErrorDistributionMetric**: Categorical entry containing an error or failure event type (`event_type`), total occurrences (`count`), and relative proportion or error frequency.
- **AuthFailureRateMetric**: Time-series entry containing a calendar date (`date`), total login attempts (`total_attempts`), failed attempts (`failed_attempts`), and computed failure ratio (`failure_rate`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Report generation requests for a standard 7-day period complete and return HTTP 200 responses in under 500 milliseconds on cold queries and under 50 milliseconds on cached hits.
- **SC-002**: 100% of repeated report requests for the same time window received within 60 seconds are served from memory cache without executing database read transactions.
- **SC-003**: 100% of calculated metric groupings are validated against UTC calendar dates, eliminating grouping anomalies caused by string or local timezone truncations.
- **SC-004**: Zero business-domain metrics (sales, revenue, commercial conversion) are present in the report payload or dashboard.
- **SC-005**: The Backoffice telemetry dashboard loads and visualizes all operational metrics within 1 second on production builds.
- **SC-006**: Periods with zero recorded events or zero login attempts produce valid structured responses with empty metric series and zero runtime exceptions.

## Assumptions

- Telemetry events are stored in the existing relational database (`telemetry_events` table) with accessible `timestamp`, `event_type`, and `properties` attributes.
- The default 7-day sliding window provides sufficient operational visibility for routine engineering inspections without exceeding single-node memory constraints.
- An in-memory cache keyed by ISO date bounds is sufficient for the reporting endpoint's operational monitoring traffic.
- The telemetry dashboard in `uis/backoffice/` is intended for authenticated internal engineering and operations personnel.
- If specific authentication event types (such as `user_login_failed` and `user_login_succeeded`) are represented as a unified `user_login_attempted` event with an `attemptStatus` attribute in the schema, the analysis pipeline flexibly accommodates both the discrete event type taxonomy and property-level attempt statuses.
