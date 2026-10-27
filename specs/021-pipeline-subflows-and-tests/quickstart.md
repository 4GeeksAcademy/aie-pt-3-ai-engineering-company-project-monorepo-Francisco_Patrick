# Quickstart & Verification Guide: Pipeline Subflows and Tests

**Feature Branch**: `feature/021-pipeline-subflows-and-tests`  
**Date**: 2026-10-27  
**Status**: Ready for Validation  

---

## 1. Prerequisites & Environment Setup

Ensure your local virtual environment is active and dependencies are installed.

```bash
# Verify Python version (3.11+ required)
python --version

# Verify Prefect installation (3.x required)
prefect version

# Verify Node.js version (18+ required)
node --version
```

---

## 2. Validation Scenarios

### Scenario 1: Run Isolated Transformation Unit Tests

Validates **FR-006, FR-007, FR-008, FR-009, and FR-010**: unit tests execute in complete memory isolation without live database or network calls.

```bash
# Run the dedicated pipeline transformation unit test suite
python -m pytest tests/pipelines/test_pipeline.py -v
```

**Expected Outcome**:
- 100% of unit tests pass cleanly with exit code `0`.
- Zero database connections or network sockets are opened during test execution.
- Verifies:
  - `test_transformation_zero_division_guardrails`: Returns default neutral metrics (volume=0, on_time=1.0, cost=0.0, returns=0.0, csat=100.0) without throwing exceptions.
  - `test_transformation_malformed_and_missing_payloads`: Defensive handling of nulls, invalid cost types, and unexpected ratings.
  - `test_transformation_exact_mathematical_precision`: Computed metrics match hand-calculated ground truth for US, ES, and GLOBAL scopes.

---

### Scenario 2: Standalone CLI Pipeline Execution Compatibility

Validates **FR-001, FR-002, FR-003, FR-004, FR-005, and FR-011**: pipeline subflows execute sequentially, record audit metadata, and exit cleanly with code 0.

#### 2.1 Default Trailing 7-Day Window Run
```bash
# Run pipeline with default calendar window (preceding Monday to Sunday)
python data/pipelines/pipeline.py
```

**Expected Outcome**:
- Prefect logs show execution of:
  - Master flow: `executive_performance_pipeline_flow`
  - Subflow 1: `extract_fulfillment_and_telemetry_flow`
  - Subflow 2: `transform_executive_performance_kpis_flow`
  - Subflow 3: `load_executive_kpi_snapshots_flow`
  - Subflow 4: `dispatch_pipeline_notifications_flow`
- Exit code is `0`.
- Snapshot records persisted in `executive_kpi_snapshots` for `US`, `ES`, and `GLOBAL`.
- Audit log entry created in `pipeline_execution_logs` with status `SUCCESS`.

#### 2.2 Custom ISO Date Window Run
```bash
# Run pipeline with explicit ISO 8601 UTC date window
python data/pipelines/pipeline.py --start-date 2026-10-12T00:00:00Z --end-date 2026-10-18T23:59:59Z
```

**Expected Outcome**:
- Pipeline parses custom date bounds.
- Re-executes all subflows over the custom window.
- Idempotently upserts snapshots into the database without primary key or unique constraint errors.
- Exits cleanly with code `0`.

---

### Scenario 3: Verify Telemetry Asset Preservation

Validates **FR-012 and SC-004**: confirms `services/telemetry/analysis.py` and `telemetry_events` remain unmodified.

```bash
# Verify git status of telemetry analysis assets
git status services/telemetry/analysis.py
```

**Expected Outcome**:
- Clean working tree for `services/telemetry/analysis.py` (no modifications).
- All operational report functions (`calculate_events_per_day`, `calculate_error_rate_by_type`, `calculate_auth_failure_rate`, `generate_telemetry_report`) remain intact.

---

### Scenario 4: Executive Backoffice Reporting Dashboard (`/reporting`)

Validates **FR-013, FR-014, FR-015, FR-016, and SC-005**: executive reporting page displays briefing KPIs, allows hub filtering, and handles network states gracefully.

```bash
# Start backend API (if not already running)
uvicorn services.api.main:app --port 8000

# In a separate terminal, run backoffice frontend
cd uis/backoffice
npm run dev
```

1. Navigate to `http://localhost:3000/reporting` in a browser.
2. Verify visual rendering:
   - **Executive Header**: Confirms active reporting window badge (e.g. `Oct 12, 2026 – Oct 18, 2026 UTC`).
   - **Hub Selector**: Buttons for `GLOBAL`, `US (LAX)`, and `ES (ZAZ)`.
   - **5 Core KPI Cards**:
     - *Shipments Volume*
     - *Global On-Time Delivery Rate* (with SLA threshold indicator)
     - *Operational Cost in EUR* (with formatted Euro currency symbol)
     - *Returns Rate* (percentage)
     - *Customer Satisfaction Score* (composite score out of 100)
3. Click between `GLOBAL`, `US`, and `ES`:
   - Metrics immediately update to reflect the selected regional hub snapshot.
4. **Error Recovery Validation**:
   - Temporarily stop backend service or simulate offline network.
   - Refresh `/reporting`.
   - Verify that an accessible error banner with a "Retry Loading Metrics" button is displayed (no blank screen or raw stack trace).

---

### Scenario 5: Static Analysis, Strict Typing, and Build Verification

Validates **SC-007, Constitution Principle III, and monorepo build health**.

```bash
# 1. Typecheck backoffice Next.js application (zero any, strict TS)
cd uis/backoffice
npm run typecheck

# 2. Build backoffice for production
npm run build

# 3. Typecheck shared-types package from root
cd ../..
npm run typecheck
```

**Expected Outcome**:
- Zero TypeScript compiler errors or type warnings.
- Production bundle compiled successfully.
