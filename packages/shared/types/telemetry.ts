/**
 * Telemetry Report Types and Interfaces.
 *
 * Conforms strictly to TrackFlow Monorepo Constitution (strict TypeScript, zero any).
 */

export interface ReportingPeriod {
  /** ISO 8601 UTC start boundary of the report window. */
  from: string;
  /** ISO 8601 UTC end boundary of the report window. */
  to: string;
}

export interface DailyEventVolumeMetric {
  /** Calendar date formatted as YYYY-MM-DD. */
  date: string;
  /** Total count of captured events on this date. */
  count: number;
}

export interface ErrorDistributionMetric {
  /** Event taxonomy type name representing an operational error or failure. */
  event_type: string;
  /** Total count of errors of this type. */
  count: number;
  /** Percentage proportion of all operational errors within the window (0-100). */
  percentage: number;
}

export interface AuthFailureRateMetric {
  /** Calendar date formatted as YYYY-MM-DD. */
  date: string;
  /** Total login attempts (succeeded + failed) recorded on this date. */
  total_attempts: number;
  /** Failed login attempts recorded on this date. */
  failed_attempts: number;
  /** Ratio of failed attempts to total attempts (0.0 to 1.0). */
  failure_rate: number;
}

export interface TelemetryMetrics {
  /** Daily event volume time series. */
  events_per_day: DailyEventVolumeMetric[];
  /** Error distribution breakdown by event type. */
  error_rate_by_type: ErrorDistributionMetric[];
  /** Daily authentication failure rates. */
  auth_failure_rate: AuthFailureRateMetric[];
}

export interface TelemetryReportResponse {
  /** Active reporting period window. */
  period: ReportingPeriod;
  /** Aggregated operational metrics. */
  metrics: TelemetryMetrics;
}

export interface TelemetryReportQueryParams {
  /** Optional ISO 8601 UTC start date. */
  start_date?: string | undefined;
  /** Optional ISO 8601 UTC end date. */
  end_date?: string | undefined;
}
