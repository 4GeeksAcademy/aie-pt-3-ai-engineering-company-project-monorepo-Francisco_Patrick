/**
 * Shared TypeScript Contracts for TrackFlow Business Reporting.
 *
 * Conforms strictly to TrackFlow Monorepo Constitution (strict TypeScript, zero any).
 */

export type GeographicScope = 'US' | 'ES' | 'GLOBAL';

export type PipelineExecutionStatus = 'RUNNING' | 'SUCCESS' | 'FAILED';

export interface PipelineExecutionLog {
  /** Globally unique execution run identifier. */
  run_id: string;
  /** Name of the executed Prefect flow. */
  flow_name: string;
  /** ISO 8601 UTC start timestamp. */
  started_at: string;
  /** ISO 8601 UTC completion timestamp, or null if still running. */
  ended_at: string | null;
  /** Count of raw source records processed. */
  records_processed: number;
  /** Execution status enum. */
  status: PipelineExecutionStatus;
  /** Sanitized error traceback or failure description. */
  error_details: string | null;
}

export interface PipelineStatusResponse {
  /** Metadata of the latest pipeline execution run. */
  latest_run: PipelineExecutionLog | null;
  /** True if a flow execution is actively running. */
  is_running: boolean;
  /** True if the latest run completed successfully without errors. */
  healthy: boolean;
}

export interface PipelineTriggerRequest {
  /** Optional ISO 8601 UTC start datetime for backfill. */
  start_date?: string | undefined;
  /** Optional ISO 8601 UTC end datetime for backfill. */
  end_date?: string | undefined;
}

export interface PipelineTriggerResponse {
  /** Initiated execution run identifier. */
  run_id: string;
  /** Trigger status (INITIATED or QUEUED). */
  status: 'INITIATED' | 'QUEUED';
  /** Human-readable status message. */
  message: string;
}

export interface ExecutiveKpiSnapshot {
  /** Unique snapshot record UUID. */
  snapshot_id: string;
  /** ISO 8601 UTC start timestamp of the weekly rollup period. */
  period_start: string;
  /** ISO 8601 UTC end timestamp of the weekly rollup period. */
  period_end: string;
  /** Geographic scope of the snapshot. */
  country: GeographicScope;
  /** Total outbound packages fulfilled and dispatched. */
  shipments_volume: number;
  /** Ratio of packages delivered within carrier SLA transit windows (0.0 - 1.0). */
  on_time_delivery_rate: number;
  /** Blended total operational and logistics cost in EUR. */
  operational_cost_eur: number;
  /** Returned package volume expressed as percentage of total shipments (0.0 - 100.0). */
  returns_rate: number;
  /** Composite customer satisfaction index (0.0 - 100.0). */
  customer_satisfaction_score: number;
  /** ISO 8601 UTC timestamp when the snapshot was generated. */
  generated_at: string;
}

export interface ExecutiveKpisQueryParams {
  /** Regional scope filter. */
  country?: GeographicScope | undefined;
  /** Optional start boundary in ISO 8601 UTC format. */
  start_date?: string | undefined;
  /** Optional end boundary in ISO 8601 UTC format. */
  end_date?: string | undefined;
}

export interface ExecutiveKpisResponse {
  /** Number of returned snapshot records. */
  count: number;
  /** Array of executive KPI snapshot records. */
  snapshots: ExecutiveKpiSnapshot[];
}
