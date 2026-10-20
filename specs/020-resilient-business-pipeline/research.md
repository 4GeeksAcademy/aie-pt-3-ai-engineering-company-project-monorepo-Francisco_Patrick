# Technical Research: Resilient Business Performance Pipeline

**Feature**: `020-resilient-business-pipeline`  
**Date**: 2026-10-20  
**Status**: Completed  

---

## 1. Prefect 3.x Flow & Task Orchestration Primitives

### Decision: Prefect `@flow` and `@task` Architecture with State Inspection

We will use native Prefect 3.x decorators (`@flow` and `@task`) to orchestrate the pipeline stages:
1. `extract_telemetry_and_domain_data`: Extracts raw telemetry events and domain operational records. Configured with external IO retries (`retries=3`, `retry_delay_seconds=10`).
2. `transform_executive_kpis`: Computes vectorized Pandas metrics for US, ES, and GLOBAL scopes. Configured with task-level result caching (`cache_key_fn`, `cache_expiration=timedelta(hours=24)`).
3. `load_reporting_snapshots`: Atomically upserts snapshot records into `reporting.executive_kpi_snapshots` and writes the audit record. Configured with retries (`retries=3`, `retry_delay_seconds=10`).
4. `notify_pipeline_status` (Optional / Non-Critical Task): Emits a pipeline run notification or writes an evaluation snapshot. Invoked in the flow using `return_state=True`.

### Rationale
- Prefect 3.x provides native async and sync flow execution, robust task state handling, built-in task retries, and result caching.
- By using `return_state=True`, the flow captures the returned Prefect `State` object directly (e.g., `state.is_completed()` or `state.is_failed()`), allowing the main flow to inspect whether the auxiliary task failed without raising a flow-terminating exception.

### Alternatives Considered
- *Airflow DAGs*: Rejected due to heavyweight scheduler and daemon infrastructure overhead that is unsuitable for lightweight CLI script execution (`python data/pipelines/pipeline.py`).
- *Celery / Dramatiq*: Rejected because they are distributed task queues lacking declarative dataflow orchestration, lineage tracking, and native caching semantics.
- *Vanilla Python try/except scripts*: Rejected because they lack standardized retry semantics, automated execution audit metadata, and enterprise orchestration interoperability required by the feature specification.

---

## 2. Smart Task Retries & Justifications

### Decision: 3 Retries with Exponential/Fixed Backoff for External I/O Tasks

External interaction tasks (`extract_telemetry_and_domain_data` and `load_reporting_snapshots`) will specify:
```python
@task(name="extract_telemetry_and_domain_data", retries=3, retry_delay_seconds=10)
```
and
```python
@task(name="load_reporting_snapshots", retries=3, retry_delay_seconds=10)
```

### Rationale & Justification
- **Transient Database Connection Glitches**: In both local SQLite (file locking during concurrent access) and remote PostgreSQL/Supabase (transient socket resets or pool exhaustion), transient errors typically resolve within 10 to 30 seconds.
- **Why 3 retries**: 3 retries strike the optimal balance between resilience against ephemeral network blips and avoiding extended pipeline blocking during genuine persistent outages.
- **Why 10-second delay**: Provides sufficient cooldown for transient database lock contention or gateway timeouts to subside without causing upstream scheduling delays.

### Alternatives Considered
- *Zero retries*: Fails on the first minor lock contention or network hiccup, resulting in false-positive alerts.
- *High retry count (> 5)*: Unnecessarily delays failure reporting during structural database outages (e.g., invalid credentials or missing tables).

---

## 3. Transformation Caching Strategy

### Decision: Input Parameter & Hash-Based Task Caching with 24-Hour Expiration

For `transform_executive_kpis`:
```python
def kpi_transformation_cache_key(context, parameters: dict) -> str:
    """Computes a deterministic cache key based on extraction window and record counts."""
    period_start = str(parameters.get("period_start", ""))
    period_end = str(parameters.get("period_end", ""))
    raw_data = parameters.get("raw_data", {})
    # Build composite hash from window bounds and row counts of extracted dataframes
    counts_sig = ",".join(f"{k}:{len(v)}" for k, v in sorted(raw_data.items()))
    return f"kpi_transform_{period_start}_{period_end}_{counts_sig}"

@task(
    name="transform_executive_kpis",
    cache_key_fn=kpi_transformation_cache_key,
    cache_expiration=timedelta(hours=24)
)
```

### Rationale
- **Deterministic Key**: Computes a stable hash based on reporting period bounds and input DataFrame row signatures. If the input data and window are identical, re-running transformation is pure duplicate compute.
- **Cache Expiration (24 Hours)**: In the TrackFlow weekly cycle, executive metrics for a finalized calendar week (`period_start` to `period_end`) do not change once Monday 06:00 UTC batch finishes. A 24-hour cache validity prevents duplicate computation during repeated manual status checks or dashboard refreshes while allowing subsequent backfills to recompute if needed.

### Alternatives Considered
- *In-memory memoization (`lru_cache`)*: Only works within a single process lifespan; does not persist across separate CLI script invocations.
- *Unconditional caching*: Risk of serving stale data if late-arriving events are reconciled within the lookback window.

---

## 4. Idempotency & Database Persistence Strategy

### Decision: Composite Unique Constraint with Upsert (`ON CONFLICT DO UPDATE`)

The destination table `reporting.executive_kpi_snapshots` enforces:
```sql
CONSTRAINT uq_kpi_snapshot_period_country UNIQUE (period_start, period_end, country);
```

The load task applies idempotent upsert semantics:
- In SQLite / PostgreSQL:
  ```sql
  INSERT INTO reporting.executive_kpi_snapshots (...)
  VALUES (...)
  ON CONFLICT (period_start, period_end, country)
  DO UPDATE SET
      shipments_volume = EXCLUDED.shipments_volume,
      on_time_delivery_rate = EXCLUDED.on_time_delivery_rate,
      operational_cost_eur = EXCLUDED.operational_cost_eur,
      returns_rate = EXCLUDED.returns_rate,
      customer_satisfaction_score = EXCLUDED.customer_satisfaction_score,
      generated_at = CURRENT_TIMESTAMP;
  ```
- All inserts/updates occur within an atomic database transaction (`session.begin()`), rolling back cleanly on any failure before updating `reporting.pipeline_execution_logs`.

### Rationale
- Guarantees mathematical idempotency: running the pipeline 1, 2, or 10 times over the same period produces exactly 3 records (`US`, `ES`, `GLOBAL`) with identical values and zero duplicate rows.
- Atomic transaction boundaries ensure no partial writes (e.g. `US` written, but `GLOBAL` missing).

### Alternatives Considered
- *Delete-and-insert*: Introduces a vulnerable time window where destination rows are deleted; if insertion fails midway, data is lost.
- *Append-only snapshots with versioning*: Increases query complexity for consumers (`GET /reporting/kpis`) which would have to filter `MAX(version)` across large historical tables.

---

## 5. Non-Critical Step Partial Failure Tolerance

### Decision: State Capture via `return_state=True`

In `executive_performance_pipeline_flow`:
```python
# Optional notification or eval snapshot step
notify_state = notify_pipeline_status(run_id=run_id, status="SUCCESS", return_state=True)
if notify_state.is_failed():
    logger.warning("Non-critical notification task failed: %s; continuing pipeline execution", notify_state.result(raise_on_failure=False))
```

### Rationale
- In production data engineering, peripheral operations (sending Slack/Teams notifications, pinging webhooks, exporting secondary S3 backups) frequently fail due to third-party outages.
- Catching the task state directly (`return_state=True`) prevents non-critical failures from terminating the primary ETL flow, ensuring executive metrics remain available on time for CEO Daniel Espinoza.

---

## 6. Decoupled Presentation Layer & Monorepo Architecture

### Decision: Boundary Interface in `data/pipelines/` Consumed by `services/reporting/`

Monorepo Constitution Principle I dictates strict service boundaries and zero code duplication:
- `data/pipelines/reporting_interface.py` exposes:
  - `get_pipeline_status() -> dict`: Queries `reporting.pipeline_execution_logs` for latest execution status.
  - `trigger_pipeline_run(period_start, period_end) -> dict`: Triggers or queues a flow run.
  - `get_executive_kpis(country, start_date, end_date) -> dict`: Queries `reporting.executive_kpi_snapshots`.
- `services/reporting/` implements FastAPI endpoints that validate parameters and serialize DTO responses using Pydantic, delegating 100% of pipeline and database logic to `data.pipelines.reporting_interface`.
- `services/telemetry/` remains completely untouched (zero changes to `analysis.py` or `telemetry_events`).

### Alternatives Considered
- *Direct ORM access inside FastAPI route handlers*: Violates monorepo layered architecture and leaks database details into presentation routes.
- *Subprocess execution of `pipeline.py` from HTTP routes*: Less observable, prone to zombie processes, and harder to unit-test than clean Python module invocation.
