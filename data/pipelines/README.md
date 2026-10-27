# TrackFlow Data Pipelines (`data/pipelines`)

This directory houses TrackFlow's data movement, ETL/ELT pipelines, transformation workflows, and analytical persistence layers.

---

## 1. Executive Performance Data Pipeline (`pipeline.py`)

The **Executive Performance Pipeline** calculates core business performance telemetry and unit economics across dual fulfillment facilities (`US-LAX-01` in Los Angeles and `ES-ZAZ-01` in Zaragoza) and consolidated globally.

- **Orchestrator**: Prefect 3.x
- **Cadence**: Weekly on Mondays at 06:00 UTC (defaulting to the preceding Monday 00:00:00 to Sunday 23:59:59 UTC window)
- **Target Audience**: CEO Daniel Espinoza, CTO Andrés Kim, Executive Leadership Team

### 1.1 Architecture & Modular Subflows

The pipeline decomposes into four domain-named subflows (`@flow`) coordinated sequentially by an overarching master flow without shared mutable global state:

```text
executive_performance_pipeline_flow (Master Orchestrator Flow)
 ├── extract_fulfillment_and_telemetry_flow   (Stage 1: Raw telemetry extraction)
 ├── transform_executive_performance_kpis_flow (Stage 2: Vectorized KPI calculation)
 ├── load_executive_kpi_snapshots_flow        (Stage 3: Idempotent atomic upsert)
 └── dispatch_pipeline_notifications_flow     (Auxiliary: Non-critical notifications, return_state=True)
```

1. **`extract_fulfillment_and_telemetry_flow`**:
   - Queries `public.telemetry_events` within the reporting window watermark.
   - Extracts four domain DataFrames: `orders`, `tracking`, `returns`, `cx`.
   - Built with retries (`retries=2, retry_delay_seconds=15`).
2. **`transform_executive_performance_kpis_flow`**:
   - Receives extracted datasets and computes vectorized KPIs for `'US'`, `'ES'`, and `'GLOBAL'`.
   - Incorporates zero-division guardrails, neutral fallbacks, and defensive type coercion.
   - Uses deterministic hashing for caching results up to 24 hours.
3. **`load_executive_kpi_snapshots_flow`**:
   - Atomically upserts pre-aggregated snapshots into `reporting.executive_kpi_snapshots` using dialect-adaptive idempotent SQL (`ON CONFLICT DO UPDATE`).
   - Built with retries (`retries=3, retry_delay_seconds=10`).
4. **`dispatch_pipeline_notifications_flow`**:
   - Non-critical auxiliary subflow dispatching execution status alerts.
   - Invoked with `return_state=True` to guarantee auxiliary webhook failures never abort core business data persistence.
5. **`executive_performance_pipeline_flow`**:
   - Master flow coordinating the stages, maintaining lifecycle audit entries in `reporting.pipeline_execution_logs` (`RUNNING`, `SUCCESS`, `FAILED`).

---

## 2. Core Executive KPIs Computed

| KPI Name | Target SLA | Formula / Logic |
|---|---|---|
| **Shipments Volume** | Operational metric | Total fulfilled outbound orders |
| **Global On-Time Delivery Rate** | ≥ 95.0% | Ratio of deliveries completed within SLA transit windows |
| **Operational Cost (EUR)** | Unit economics | Total logistics, picking, packing, and last-mile spend |
| **Returns Rate** | &lt; 5.0% | (Returned items / Shipments volume) * 100 |
| **Customer Satisfaction (CSAT)** | ≥ 90.0 / 100 | Composite index: 70% average rating + 30% First Contact Resolution (FCR) |

---

## 3. CLI Usage

The pipeline can be executed as a standalone CLI script in container entrypoints, cron schedules, or developer workflows:

```bash
# 1. Run with default trailing 7-day calendar window:
python data/pipelines/pipeline.py

# 2. Run with custom ISO UTC date window:
python data/pipelines/pipeline.py --start-date 2026-10-12T00:00:00Z --end-date 2026-10-18T23:59:59Z
```

---

## 4. Verification and Testing

### 4.1 In-Memory Transformation Unit Tests (Fast & Isolated)

Executes in < 2 seconds with zero live database or network calls:

```bash
python -m pytest tests/pipelines/test_pipeline.py -v
```

### 4.2 Integration & Resilience Test Suites

```bash
# Integration ETL and vectorized calculations:
python -m pytest tests/pipelines/test_pipeline_etl.py -v

# Fault tolerance, retries, caching, and idempotency:
python -m pytest tests/pipelines/test_pipeline_resilience.py -v
```

---

## 5. Executive Web Dashboard

Business metrics are visualized on the dedicated backoffice dashboard:
- **Route**: `http://localhost:3000/reporting` (`uis/backoffice/`)
- **API Endpoint**: `GET /api/v1/reporting/kpis`
- **Features**: Hub toggling (`GLOBAL`, `US`, `ES`), date cadence badge, animated loading skeletons, accessible error alerts.

---

## 6. Automated Nightly Telemetry Export & Orchestration (`scripts/nightly_export.py`)

The **Nightly Telemetry Export Runner** runs as an autonomous, detached CLI process that extracts the previous calendar day's telemetry events into raw point-in-time CSV audit files (`data/raw/telemetry_YYYY-MM-DD.csv`) and triggers the Executive KPI pipeline as an isolated subprocess.

- **Orchestrator Service**: `NightlyExportRunner` (`services/jobs/runner.py`)
- **CLI Entry Point**: `scripts/nightly_export.py`
- **Audit Persistence**: `job_runs` table (`services/jobs/models.py`)
- **Default Target Date**: Preceding calendar day in UTC (`YYYY-MM-DD`)

### 6.1 Production Cron Schedule & Deployment

The export job is configured to run daily at **02:00 UTC** (`0 2 * * *`). The 2-hour window after midnight UTC guarantees that late-arriving events across dual fulfillment hubs (`US-LAX-01` and `ES-ZAZ-01`) are persisted before batch extraction begins.

```bash
# Production Crontab Entry (with standard log redirection and rotation)
0 2 * * * cd /workspace && python scripts/nightly_export.py >> /var/log/trackflow/nightly_export.log 2>&1
```

### 6.2 Environment Configuration

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///services/api/inventory.db` | PostgreSQL or local SQLite connection string |
| `RAW_DATA_DIR` | `data/raw` | Target directory for immutable audit CSV snapshots |
| `TARGET_DATE` | None (Yesterday UTC) | Optional default date override (`YYYY-MM-DD`) |

### 6.3 Operational Controls & Guards

1. **Database-Backed Concurrency Locking**: Active `processing` status in `job_runs` prevents overlapping runs. Secondary executions detect active locks, log an informational notice, and exit cleanly with code `0`.
2. **Per-Day Idempotency & Snapshot Preservation**: If `(nightly_export, target_date)` is already `completed`, subsequent runs skip execution and leave existing CSV files untouched.
3. **Historical Backfill**: Historical date cohorts can be processed on-demand without interfering with cron cadences:
   ```bash
   python scripts/nightly_export.py --date 2026-10-24
   ```
4. **Dry-Run Inspection**:
   ```bash
   python scripts/nightly_export.py --dry-run --verbose
   ```
5. **Defensive Error Sanitization**: All runtime failures mask credentials, passwords, and tokens, record diagnostic messages (max 500 chars) in `job_runs.error_message`, and exit with code `1`, leaving zero orphaned locks in `processing`.

