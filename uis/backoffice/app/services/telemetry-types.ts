/**
 * Telemetry types and schema constants for TrackFlow Backoffice.
 * Conforms strictly to docs/telemetry/event-schemas.json and telemetry-plan.md.
 */

export const SCHEMA_VERSION = "1.0.0";
export const DEFAULT_BATCH_INTERVAL_MS = 10000;
export const DEFAULT_BATCH_MAX_SIZE = 20;
export const MAX_QUEUE_CAPACITY = 100;
export const MAX_RETRY_ATTEMPTS = 3;

/**
 * Universal Event Envelope structure.
 */
export interface TelemetryEvent {
  /** Globally unique UUIDv4 identifying this event instance. */
  eventId: string;
  /** ISO 8601 UTC timestamp of event capture. */
  timestamp: string;
  /** Unique session identifier. */
  sessionId: string;
  /** Pseudonymized identifier of authenticated user or null if unauthenticated. */
  userId: string | null;
  /** Event name conforming strictly to entity_action taxonomy. */
  event_type: string;
  /** Semantic version of event schema. */
  schemaVersion: string;
  /** Distributed tracing correlation identifier. */
  requestId: string;
  /** Event-specific domain payload validated against property allowlist. */
  properties: Record<string, unknown>;
}

/**
 * Transport batch envelope payload.
 */
export interface TelemetryBatch {
  events: TelemetryEvent[];
}

/**
 * Server acknowledgment receipt response.
 */
export interface IngestReceipt {
  received: number;
}

/**
 * Technical Baseline Event Properties
 */
export interface FrontendErrorCapturedProps {
  errorName: string;
  errorMessage: string;
  stackTraceSnippet?: string;
  url: string;
  componentName?: string;
}

export interface ApiLatencyRecordedProps {
  endpointPath: string;
  httpMethod: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  durationMs: number;
  httpStatusCode: number;
  success: boolean;
}

export interface SectionNavigationTrackedProps {
  sourceSection: string;
  destinationSection: string;
  navigationDurationMs?: number;
}

/**
 * Business & Inventory Event Properties
 */
export interface InboundOrderCreatedProps {
  inboundOrderId: string;
  clientId: string;
  warehouseCode: "LA-01" | "ZAZ-01" | string;
  totalSkus: number;
  totalUnits: number;
  sourceChannel: "EDI" | "PORTAL" | "EMAIL_PARSER" | "MANUAL" | string;
}

export interface StockThresholdTriggeredProps {
  skuId: string;
  warehouseCode: "LA-01" | "ZAZ-01" | string;
  currentAvailableQuantity: number;
  safetyThresholdQuantity: number;
  triggerSeverity: "WARNING" | "CRITICAL";
}

export interface DirectStockEditRejectedProps {
  attemptedByUserId: string;
  warehouseCode: "LA-01" | "ZAZ-01" | string;
  skuId: string;
  attemptedDelta: number;
  rejectionReason: string;
}

export interface StockValidationFailedProps {
  orderId: string;
  warehouseCode: "LA-01" | "ZAZ-01" | string;
  skuId: string;
  expectedQuantity: number;
  actualQuantity: number;
  failureReason: string;
}

export interface OutboundOrderFulfilledProps {
  orderId: string;
  clientId: string;
  warehouseCode: "LA-01" | "ZAZ-01" | string;
  carrierCode: "UPS" | "FEDEX" | "DHL" | "MRW" | "SEUR" | string;
  fulfillmentDurationSeconds: number;
  totalItems: number;
}
