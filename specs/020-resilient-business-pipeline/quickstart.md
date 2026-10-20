# Quickstart Validation Guide: Resilient Business Performance Pipeline

**Feature**: `020-resilient-business-pipeline`  
**Date**: 2026-10-20  
**Status**: Ready for Verification  

This guide provides step-by-step procedures to validate that the pipeline and presentation endpoints fulfill all acceptance criteria and functional requirements.

---

## Prerequisites

1. Ensure the Python environment is activated:
   ```powershell
   # Windows PowerShell
   .\services\api\.venv\Scripts\Activate.ps1
   ```
2. Verify dependencies are available:
   ```powershell
   python -c "import prefect, pandas, fastapi, sqlmodel; print('Dependencies ready!')"
   ```
3. Initialize the database schema and sample domain data:
   ```powershell
   python services\api\seed.py
   ```

---

## Validation Scenarios

### Scenario 1: CLI Direct Pipeline Execution

Execute the production pipeline directly from the command line:

```powershell
python data\pipelines\pipeline.py
```

**Expected Outcomes**:
- The flow `executive_performance_pipeline_flow` executes tasks sequentially:
  1. `extract_telemetry_and_domain_data`
  2. `transform_executive_kpis`
  3. `load_reporting_snapshots`
  4. `notify_pipeline_status` (optional auxiliary task)
- Logs report completion with zero unhandled exceptions.
- Exit code is `0`.

---

### Scenario 2: Idempotency Verification (Double-Run Check)

Validate that consecutive pipeline runs over the same data window produce zero duplicates:

1. Execute the pipeline twice:
   ```powershell
   python data\pipelines\pipeline.py
   python data\pipelines\pipeline.py
   ```
2. Verify the destination records in the database:
   ```powershell
   python -c "from data.pipelines.reporting_interface import get_executive_kpis; res = get_executive_kpis(); print('Snapshot count:', res['count'])"
   ```

**Expected Outcomes**:
- The snapshot count for the default window remains exactly `3` (one for `US`, one for `ES`, one for `GLOBAL`).
- No duplicate records or constraint errors occur.

---

### Scenario 3: Non-Critical Step Partial Failure Tolerance

Validate that an error in the non-critical auxiliary step (`notify_pipeline_status`) does not abort the main ETL flow:

1. Run the test suite targeting partial failure tolerance:
   ```powershell
   pytest tests\pipelines\test_pipeline_resilience.py -k "test_optional_task_failure_tolerance"
   ```

**Expected Outcomes**:
- The auxiliary notification task raises an exception, which is captured via `return_state=True`.
- The main flow catches the failed state, logs a warning, and continues executing downstream load and audit persistence.
- The pipeline execution status completes as `SUCCESS`.

---

### Scenario 4: Task Caching & External Retries

Validate task retry configuration and result caching:

```powershell
pytest tests\pipelines\test_pipeline_resilience.py -k "test_caching_and_retries"
```

**Expected Outcomes**:
- Consecutive calls to `transform_executive_kpis` with identical inputs within 24 hours return cached results without re-aggregating DataFrames.
- Simulated transient connection errors in `extract_telemetry_and_domain_data` or `load_reporting_snapshots` trigger retries up to 3 times before succeeding.

---

### Scenario 5: Presentation API Endpoints Validation

Launch the API server or run test suite for `services/reporting/`:

1. Run endpoint contract test suite:
   ```powershell
   pytest tests\reporting\test_reporting_endpoints.py
   ```
2. Manual verification via HTTP client:
   - `GET /api/v1/reporting/status` returns latest execution metadata (`started_at`, `ended_at`, `records_processed`, `status`, `healthy`).
   - `POST /api/v1/reporting/trigger` triggers flow execution and returns `{ "run_id": "...", "status": "INITIATED", ... }`.
   - `GET /api/v1/reporting/kpis?country=GLOBAL` returns the pre-aggregated metrics conforming to [reporting-api.yaml](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/020-resilient-business-pipeline/contracts/reporting-api.yaml).

---

### Scenario 6: Telemetry Asset Preservation Verification

Ensure existing engineering telemetry remains untouched:

```powershell
git diff --name-only origin/main -- services/telemetry/analysis.py
```

**Expected Outcomes**:
- Output is empty; `services/telemetry/analysis.py` has zero modifications.
