# Research & Architectural Decisions: Business Performance Pipeline

**Feature**: `019-business-pipeline-design`  
**Date**: 2026-10-20  
**Status**: Completed  

---

## 1. Executive Summary & Context Analysis

### 1.1 Current State Assessment
TrackFlow currently possesses an operational engineering telemetry system structured around:
- **Relational Event Store**: The `telemetry_events` table (managed via SQLModel in PostgreSQL / Supabase with SQLite fallback in `services/api/inventory.db`) storing append-only events enveloped with `eventId`, `timestamp`, `sessionId`, `userId`, `event_type`, `schemaVersion`, `requestId`, and JSON `properties`.
- **Engineering Telemetry Engine**: `services/telemetry/analysis.py` contains vectorized Pandas functions (`calculate_events_per_day`, `calculate_error_rate_by_type`, `calculate_auth_failure_rate`, `generate_telemetry_report`) that evaluate technical health.
- **Engineering Telemetry Endpoint**: `GET /api/v1/telemetry/report` (also mounted at legacy `/telemetry/report`) served by `services/api/presentation/api/v1/telemetry.py`.
- **Questions Answered by Current Setup**:
  1. What is the daily total event throughput across system components?
  2. What is the distribution and breakdown of system errors (crashes, exceptions, threshold failures)?
  3. What is the daily authentication failure rate and login attempt volume?

### 1.2 The Business Gap
The existing engineering telemetry report completely fails to answer the strategic business questions required by executive leadership (CEO Daniel Espinoza and CTO Andrés Kim) as outlined in `CONTEXT.md`:
- **Cross-Border Fulfillment Volume**: How many actual orders were picked, packed, and fulfilled in Los Angeles (`US-LAX-01`) vs. Zaragoza (`ES-ZAZ-01`)?
- **Global On-Time Delivery (OTD) Rate**: What proportion of shipments met carrier SLA transit windows across UPS, FedEx, DHL, MRW, and SEUR?
- **Blended Logistics Cost**: What is the average operational cost in EUR per package or per kg across fulfillment and carrier lanes?
- **Reverse Logistics Return Rate**: What percentage of outbound shipments were returned, and how quickly are returns inspected and restocked?
- **Customer Satisfaction & Deflection**: What is the automated resolution rate (FCR) of customer inquiries and the prevailing customer sentiment?

Currently, directors spend 3–4 hours every Sunday evening manually assembling spreadsheets to answer these questions for the Monday 07:00 executive review. A dedicated data pipeline is required to ingest raw telemetry and domain records, aggregate them into business KPIs, and publish them into dedicated reporting tables without touching the operational engineering telemetry service.

---

## 2. Research Tasks & Architectural Decisions

### 2.1 Extraction Strategy, Source Formats & Cadence

#### Decision
Extract source records directly from `telemetry_events` (filtering for specific business event taxonomies) joined/supplemented with operational domain tables (`stock_entry`, `stock_exit`, `sku`, `orders`, `incidents`). Extraction runs on a scheduled weekly batch cadence every Monday at 06:00 UTC, extracting data for the preceding 7 calendar days (Monday 00:00:00 UTC through Sunday 23:59:59 UTC).

#### Source Event Mappings
| Business Metric | Source Telemetry Event Types | Relevant Payload Properties | Secondary Domain Tables |
| :--- | :--- | :--- | :--- |
| **Shipments Volume** | `outbound_order_fulfilled` | `orderId`, `warehouseCode`, `destinationCountry`, `packageWeightKg`, `itemCount` | `stock_exit`, `sku` |
| **On-Time Delivery Rate** | `shipment_tracking_updated` | `trackingNumberHash`, `carrierCode`, `normalizedStatus`, `isDeliveredOnTime` | Carrier SLA tables |
| **Logistics Cost in EUR** | `carrier_recommendation_selected`, `outbound_order_fulfilled` | `estimatedCostEur`, `packageWeightKg`, `carrierCode` | `stock_exit` |
| **Returns Rate** | `return_request_evaluated`, `return_item_inspected` | `returnId`, `warehouseCode`, `sku`, `evaluationOutcome`, `finalGrade` | `orders` |
| **Customer Satisfaction (CSAT)** | `cx_inquiry_resolved`, `cx_sentiment_flagged` | `ticketId`, `firstContactResolution`, `sentimentScore`, `resolvedBy` | CX tickets |

#### Extraction Payload Format
Extracted records from SQL are loaded into Pandas DataFrames with:
- Datetime fields parsed to timezone-aware UTC (`datetime64[ns, UTC]`).
- JSON `properties` parsed using vectorized Pandas transformations (`pd.json_normalize` or dict key extraction).
- Null-safe column defaults.

#### Rationale
- Weekly cadence aligns perfectly with Daniel Espinoza's executive briefing requirements (Monday 07:00).
- Running at 06:00 UTC provides a 60-minute window for pipeline execution, data verification, and caching before leadership reviews the dashboard.
- Utilizing existing operational events avoids redundant event emissions and guarantees consistency across operational logs and analytical rollups.

#### Alternatives Considered
- *Real-time Streaming Aggregation (Kafka/Flink)*: Rejected because executive rollups are reviewed only once a week; maintaining continuous streaming aggregations would introduce unnecessary cloud operational overhead and cost for a weekly cadence.
- *Daily Rollups with Dynamic Weekly Summation*: While valuable for intra-week tracking, the primary deliverable for Part 1 & 2 is the weekly snapshot. Daily rollups will be retained as intermediate representations inside the transform task.

---

### 2.2 Record Updates & Deduplication Strategy

#### Decision
Implement a **Watermark & Windowed Last-Write-Wins (LWW)** deduplication strategy in the Transformation stage, combined with **Deterministic Composite Key Upserts** in the Load stage.

#### Concrete Mechanism
1. **Source Event Handling**:
   - Carrier tracking updates (`shipment_tracking_updated`) and order milestones emit multiple events over the lifecycle of a shipment.
   - The extraction query fetches all events within the target period plus a configurable lookback buffer (e.g. 7 days).
   - In Pandas:
     ```python
     # Deduplicate tracking events by shipment identifier, keeping the terminal or latest status
     latest_shipment_states = (
         tracking_df.sort_values(by="timestamp", ascending=True)
         .groupby("trackingNumberHash", as_index=False)
         .last()
     )
     ```
2. **Domain Table Synchronization**:
   - For domain tables with mutable records (e.g., `orders` updating from `PENDING` to `FULFILLED`), extraction utilizes `updated_at` watermarks:
     `SELECT * FROM orders WHERE updated_at >= :period_start AND updated_at <= :period_end`.
3. **Destination Upsert Strategy**:
   - The destination table `reporting.executive_kpi_snapshots` enforces a UNIQUE constraint on `(period_start, period_end, country)`.
   - In PostgreSQL / Supabase:
     ```sql
     INSERT INTO reporting.executive_kpi_snapshots (
         snapshot_id, period_start, period_end, country,
         shipments_volume, on_time_delivery_rate, operational_cost_eur,
         returns_rate, customer_satisfaction_score, generated_at
     ) VALUES (...)
     ON CONFLICT (period_start, period_end, country)
     DO UPDATE SET
         shipments_volume = EXCLUDED.shipments_volume,
         on_time_delivery_rate = EXCLUDED.on_time_delivery_rate,
         operational_cost_eur = EXCLUDED.operational_cost_eur,
         returns_rate = EXCLUDED.returns_rate,
         customer_satisfaction_score = EXCLUDED.customer_satisfaction_score,
         generated_at = EXCLUDED.generated_at;
     ```
   - In SQLite (local dev fallback):
     ```sql
     INSERT INTO executive_kpi_snapshots (...) VALUES (...)
     ON CONFLICT(period_start, period_end, country) DO UPDATE SET ...;
     ```

#### Rationale
- Completely eliminates duplicate counting when carriers emit repeated tracking webhooks.
- Guarantees that updating a record in operational systems does not create duplicate KPI entries in the analytical store.

#### Alternatives Considered
- *Append-only Snapshot Versioning*: Adding a `version` integer to every snapshot. Rejected because leadership dashboards require the authoritative latest state for a given period, and versioning introduces query complexity without operational necessity.

---

### 2.3 Resilience, Idempotency & Failure Recovery

#### Decision
Enforce strict **Transactional Atomicity** and **Deterministic Partition Replacement**.

#### Failure Scenarios & Recovery Strategy
1. **Failure During Load Stage**:
   - All destination writes for a pipeline run execute within a single database transaction (`with session.begin():`).
   - If the database disconnects, a constraint fails, or a server crashes midway through inserting rows:
     - The transaction automatically rolls back.
     - Zero partial records persist in `reporting.executive_kpi_snapshots`.
     - The exception handler logs a `FAILED` execution record in `reporting.pipeline_execution_logs` with sanitized error details and duration.
2. **Second Run (Retry / Manual Re-trigger)**:
   - When the pipeline is executed a second time for the same reporting window:
     - The extraction phase re-reads source events deterministically based on timestamp boundaries.
     - The transformation phase re-computes identical aggregations.
     - The load phase executes the upsert statement (`ON CONFLICT DO UPDATE`), cleanly writing the full snapshot.
     - Already-loaded data is neither duplicated nor corrupted.
3. **Execution Audit Log Fields**:
   The table `reporting.pipeline_execution_logs` records 6 audit attributes:
   - `run_id` (`UUID`, Primary Key): Uniquely identifies each flow invocation.
   - `flow_name` (`VARCHAR(100)`): Names the executed pipeline (e.g. `executive_performance_pipeline_flow`).
   - `started_at` (`TIMESTAMPTZ`): UTC start timestamp; needed to measure SLA and detect stalled pipelines.
   - `ended_at` (`TIMESTAMPTZ`, Nullable): UTC completion timestamp; needed to calculate execution duration.
   - `records_processed` (`INTEGER`): Total number of raw source records ingested; essential for anomaly detection (e.g. sudden drop to 0).
   - `status` (`VARCHAR(20)`): State enum (`RUNNING`, `SUCCESS`, `FAILED`); required for monitoring and alerting.
   - `error_details` (`TEXT`, Nullable): Sanitized error message and stack summary; vital for on-call triage without exposing credentials.

---

### 2.4 Workflow Orchestration Mapping (Prefect)

#### Decision
Map pipeline stages to **Prefect 2.x/3.x** orchestration primitives using `@flow` and `@task` decorators, with secure credential handling via Prefect Blocks.

#### Orchestration Structure
- **Main Flow**: `executive_performance_pipeline_flow(period_start: Optional[datetime], period_end: Optional[datetime])`
- **Granular Tasks**:
  1. `extract_telemetry_and_domain_data(period_start, period_end) -> Dict[str, pd.DataFrame]`:
     - Connects to database and extracts source events into isolated DataFrames.
     - Configured with `retries=3, retry_delay_seconds=30`.
  2. `transform_executive_kpis(dataframes: Dict[str, pd.DataFrame]) -> List[ExecutiveKpiSnapshot]`:
     - Pure vectorized computation of metrics for `US`, `ES`, and `GLOBAL`.
     - Pure in-memory transformation with zero database side-effects.
  3. `load_reporting_snapshots(snapshots: List[ExecutiveKpiSnapshot], run_id: UUID) -> int`:
     - Atomically upserts snapshot records into `reporting.executive_kpi_snapshots`.
     - Updates `reporting.pipeline_execution_logs` with final status and count.
- **State Handling**:
  - `Pending` $\rightarrow$ `Running` $\rightarrow$ `Completed` or `Failed`.
  - On `Failed` state hook: Emits alerts to ops webhook and writes error entry to audit log.
- **Prefect Configuration & Blocks**:
  - `SqlAlchemyConnector` block (named `trackflow-reporting-db`): Securely holds the PostgreSQL/Supabase connection string with pooling parameters.
  - `Secret` block (named `trackflow-ops-alert-webhook`): Holds alert webhook URL.

---

### 2.5 Application Integration & Architectural Boundaries

#### Decision
Expose reporting metrics via a new, completely isolated service module `services/reporting/` (integrated into FastAPI under prefix `/api/v1/reporting`), strictly prohibiting ETL logic within HTTP route handlers.

#### Decoupled Route Sketched
1. `GET /api/v1/reporting/status`
   - Purpose: Returns the latest pipeline execution status, timestamp of last successful run, and pipeline health.
   - Internal Call: `from data.pipelines.reporting_interface import get_pipeline_status`
2. `POST /api/v1/reporting/trigger`
   - Purpose: Allows authorized administrators (CTO Andrés Kim, CEO Daniel Espinoza) to trigger an immediate ad-hoc or backfill run.
   - Internal Call: `from data.pipelines.reporting_interface import trigger_pipeline_run`
3. `GET /api/v1/reporting/kpis`
   - Purpose: Serves the weekly executive KPI snapshots consumed by the backoffice dashboard (`uis/backoffice`). Supports query filters: `country` (`US`, `ES`, `GLOBAL`), `start_date`, `end_date`.
   - Internal Call: `from data.pipelines.reporting_interface import get_executive_kpis`

#### Boundary Isolation Invariants
- `services/telemetry/analysis.py` and `GET /telemetry/report` remain 100% untouched.
- `telemetry_events` table remains append-only; this pipeline NEVER writes into `telemetry_events`.
- All analytics output resides under `reporting` schema tables (`reporting.executive_kpi_snapshots` and `reporting.pipeline_execution_logs`).
- Route handlers only validate HTTP request parameters and serialize responses; 100% of pipeline invocation and query retrieval logic resides in `data/pipelines/`.

---

## 3. Summary of Resolved Clarifications

| Item | Status | Resolution |
| :--- | :--- | :--- |
| **Pipeline Purpose Statement** | Resolved | Unified single-sentence formulation incorporating deliverable, recipient, cadence, 5 KPIs, and source events. |
| **Extraction Format & Cadence** | Resolved | Vectorized query into Pandas DataFrame, weekly batch every Monday at 06:00 UTC. |
| **Source Record Updates** | Resolved | LWW grouping by entity key + PostgreSQL/SQLite `ON CONFLICT DO UPDATE`. |
| **Idempotency Strategy** | Resolved | Atomic single-transaction load + deterministic `(period_start, period_end, country)` upsert. |
| **Audit Log Fields** | Resolved | 6 concrete fields (`run_id`, `flow_name`, `started_at`, `ended_at`, `records_processed`, `status`, `error_details`) with operational justifications. |
| **Prefect Concepts** | Resolved | 1 main flow, 3 distinct tasks, state lifecycle hooks, `SqlAlchemyConnector` blocks. |
| **Application Endpoints** | Resolved | 3 endpoints (`/reporting/status`, `/reporting/trigger`, `/reporting/kpis`) delegating to `data/pipelines/reporting_interface.py`. |
| **Constitution Compliance** | Resolved | Strict domain isolation, no direct DB from UI, zero `any` in TypeScript DTOs, sanitized errors. |
