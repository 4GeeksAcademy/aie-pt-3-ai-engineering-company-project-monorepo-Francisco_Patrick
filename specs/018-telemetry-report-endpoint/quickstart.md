# Quickstart Validation Guide: Telemetry Report Endpoint & Operational Dashboard

**Feature Branch**: `018-telemetry-report-endpoint`  
**Date**: 2026-10-17  
**Status**: Ready for Implementation  

---

## 1. Prerequisites & Environment

1. **Python Environment**:
   - Python `>=3.11` (or uv virtualenv at `services/api/.venv`).
   - Packages: `fastapi`, `uvicorn`, `sqlmodel`, `pandas`, `pydantic`.
   ```bash
   cd services/api
   uv sync
   ```

2. **Frontend Environment**:
   - Node.js `>=20.x`.
   - Workspace packages installed:
   ```bash
   cd uis/backoffice
   npm install
   ```

3. **Database Seeding**:
   - Ensure the local SQLite database (`inventory.db`) or PostgreSQL instance contains schema tables including `telemetry_events`.
   ```bash
   cd services/api
   uv run python seed.py
   ```

---

## 2. Validation Scenarios

### Scenario 1: Verify Default 7-Day Window Report via API

**Objective**: Verify that `GET /telemetry/report` resolves a default 7-day UTC period, processes metric functions, and returns valid JSON.

1. **Start the API Server**:
   ```bash
   cd services/api
   uv run uvicorn main:app --reload --port 8000
   ```

2. **Send Request with curl**:
   ```bash
   curl -i http://localhost:8000/telemetry/report
   ```

3. **Expected Outcome**:
   - HTTP Status: `200 OK`.
   - Headers: `Content-Type: application/json`, `X-Cache: MISS` on first call.
   - Body conforms to [`TelemetryReportResponse`](./contracts/telemetry-report-api.yaml):
     - `period.from`: ISO timestamp exactly 7 days prior to UTC now.
     - `period.to`: ISO timestamp of UTC now.
     - `metrics.events_per_day`: Array of `{ "date": "...", "count": ... }`.
     - `metrics.error_rate_by_type`: Array of `{ "event_type": "...", "count": ..., "percentage": ... }`.
     - `metrics.auth_failure_rate`: Array of `{ "date": "...", "total_attempts": ..., "failed_attempts": ..., "failure_rate": ... }`.

---

### Scenario 2: Verify In-Memory Caching (60-Second TTL)

**Objective**: Verify that consecutive identical queries are served directly from cache without database queries or recalculation.

1. **Send First Request (Cache Miss)**:
   ```bash
   curl -i http://localhost:8000/telemetry/report
   ```
   - Note response timestamp and `X-Cache: MISS`.

2. **Send Second Request within 60 Seconds (Cache Hit)**:
   ```bash
   curl -i http://localhost:8000/telemetry/report
   ```
   - Expected Header: `X-Cache: HIT`.
   - Latency: `< 20ms`.
   - Body: Exactly identical to the first response.

3. **Send Third Request after 61 Seconds (Cache Expiry)**:
   - Expected Header: `X-Cache: MISS`.
   - Cache entry refreshed with new TTL.

---

### Scenario 3: Verify Custom Date Range Filtering

**Objective**: Verify that custom `start_date` and `end_date` query parameters bound metric computations.

1. **Send Request with Custom Range**:
   ```bash
   curl -i "http://localhost:8000/telemetry/report?start_date=2026-10-01T00:00:00Z&end_date=2026-10-05T23:59:59Z"
   ```

2. **Expected Outcome**:
   - HTTP Status: `200 OK`.
   - `period.from`: `"2026-10-01T00:00:00Z"`.
   - `period.to`: `"2026-10-05T23:59:59Z"`.
   - Metric entries restricted exclusively to dates between `2026-10-01` and `2026-10-05`.

---

### Scenario 4: Verify Input Validation & Error Handling

**Objective**: Verify that invalid date inputs or inverted ranges are safely rejected with HTTP 422.

1. **Send Inverted Date Range**:
   ```bash
   curl -i "http://localhost:8000/telemetry/report?start_date=2026-10-15T00:00:00Z&end_date=2026-10-01T00:00:00Z"
   ```
   - Expected Status: `422 Unprocessable Entity` or `400 Bad Request`.

2. **Send Malformed Date Format**:
   ```bash
   curl -i "http://localhost:8000/telemetry/report?start_date=invalid-date"
   ```
   - Expected Status: `422 Unprocessable Entity`.

---

### Scenario 5: Verify Backoffice Operational Dashboard

**Objective**: Verify the visual dashboard renders operational metrics in `uis/backoffice`.

1. **Start Backoffice Dev Server**:
   ```bash
   cd uis/backoffice
   npm run dev
   ```

2. **Access Dashboard**:
   - Navigate to `http://localhost:3000/telemetry` in a web browser.
   - Verify:
     - Header displays active reporting window (`from` and `to` timestamps).
     - Daily Event Volume chart/table renders daily counts.
     - Error Distribution table renders error types with relative percentage bars.
     - Auth Failure Rate widget shows daily failure percentages with status indicators.
     - Refresh button triggers data re-fetch.
     - Network disconnection or empty data displays a user-friendly error/empty state with retry CTA.

---

### Scenario 6: Automated Test Verification

**Objective**: Run automated verification across backend and frontend test suites.

1. **Backend Tests (Pipeline, Cache, Endpoint)**:
   ```bash
   cd services/api
   uv run pytest tests/api/test_telemetry_report.py tests/unit/test_telemetry_analysis.py -v
   ```

2. **Frontend Type Check & Tests**:
   ```bash
   cd uis/backoffice
   npm run typecheck
   npm test
   ```
