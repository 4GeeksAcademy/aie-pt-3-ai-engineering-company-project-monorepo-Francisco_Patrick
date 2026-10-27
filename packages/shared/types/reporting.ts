/**
 * Executive Performance Reporting Types and Interfaces.
 *
 * Conforms strictly to TrackFlow Monorepo Constitution (strict TypeScript, zero any).
 */

/**
 * Geographic hub scope for executive reporting metrics.
 */
export type ReportingGeographicScope = 'US' | 'ES' | 'GLOBAL';

/**
 * Pre-aggregated executive business performance KPI snapshot.
 */
export interface ExecutiveKpiSnapshot {
  /** Unique snapshot record identifier (UUID). */
  readonly snapshot_id: string;
  /** Inclusive ISO 8601 UTC start boundary of the reporting window. */
  readonly period_start: string;
  /** Inclusive ISO 8601 UTC end boundary of the reporting window. */
  readonly period_end: string;
  /** Regional hub scope: 'US', 'ES', or 'GLOBAL'. */
  readonly country: ReportingGeographicScope;
  /** Total outbound packages fulfilled during the period (>= 0). */
  readonly shipments_volume: number;
  /** Ratio of delivered orders within SLA transit windows (range: 0.0 to 1.0). */
  readonly on_time_delivery_rate: number;
  /** Total fulfillment and logistics expenditure in EUR (>= 0.0). */
  readonly operational_cost_eur: number;
  /** Returned items as a percentage of total shipments (range: 0.0 to 100.0). */
  readonly returns_rate: number;
  /** Composite satisfaction index (range: 0.0 to 100.0). */
  readonly customer_satisfaction_score: number;
  /** Snapshot generation and persistence timestamp in UTC. */
  readonly generated_at: string;
}

/**
 * Response payload returned by GET /api/v1/reporting/kpis.
 */
export interface ExecutiveKpisResponse {
  /** Count of snapshots contained in response. */
  readonly count: number;
  /** Array of pre-aggregated KPI snapshots. */
  readonly snapshots: readonly ExecutiveKpiSnapshot[];
}

/**
 * Pipeline execution audit log entity.
 */
export interface PipelineExecutionLog {
  /** Unique execution run identifier (UUID). */
  readonly run_id: string;
  /** Name of the executed orchestrator flow. */
  readonly flow_name: string;
  /** Flow execution start timestamp in UTC. */
  readonly started_at: string;
  /** Flow execution completion or failure timestamp in UTC (or null if currently running). */
  readonly ended_at: string | null;
  /** Total count of raw events extracted and processed. */
  readonly records_processed: number;
  /** Execution lifecycle state. */
  readonly status: 'RUNNING' | 'SUCCESS' | 'FAILED';
  /** Sanitized error summary if execution failed (or null if successful). */
  readonly error_details: string | null;
}

/**
 * Response payload returned by GET /api/v1/reporting/status.
 */
export interface PipelineStatusResponse {
  /** Metadata of the most recent pipeline execution run. */
  readonly latest_run: PipelineExecutionLog | null;
  /** True if a pipeline execution is currently active in RUNNING state. */
  readonly is_running: boolean;
  /** True if the pipeline is healthy (latest execution succeeded). */
  readonly healthy: boolean;
}

/**
 * Query parameters supported by GET /api/v1/reporting/kpis.
 */
export interface ReportingQueryParams {
  /** Filter snapshots by regional hub scope. */
  readonly country?: ReportingGeographicScope | undefined;
  /** Inclusive ISO 8601 UTC start boundary filter. */
  readonly start_date?: string | undefined;
  /** Inclusive ISO 8601 UTC end boundary filter. */
  readonly end_date?: string | undefined;
}
