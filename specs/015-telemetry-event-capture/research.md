# Phase 0: Research & Technical Decisions

**Feature**: Telemetry Event Capture  
**Feature Branch**: `015-telemetry-event-capture`  
**Date**: 2026-10-06  
**Status**: Completed  

---

## 1. Frontend Capture Service Architecture

### Decision 1.1: Local Queue Buffering & Batch Transmission
- **Decision**: Implement an in-memory FIFO queue array (`TelemetryEvent[]`) inside a singleton `TelemetryService` class in `uis/backoffice/app/services/telemetry.ts`. Events are buffered and flushed either when `queue.length >= 20` or after a 10-second debounce timer (`10,000ms`), whichever condition is met first.
- **Rationale**:
  - Eliminates network congestion and per-interaction HTTP overhead.
  - Guarantees capture timestamps reflect the exact moment of user interaction (`new Date().toISOString()`), not the moment of network flush.
  - Caps memory consumption at a maximum buffer limit (e.g., 100 events) to protect client memory during prolonged offline states.
- **Alternatives Considered**:
  - *Direct HTTP dispatch per event*: High network overhead, degrades client rendering performance, causes network bottlenecks during rapid scanning or filter actions.
  - *IndexedDB / LocalStorage persistence queue*: Adds unnecessary I/O complexity for non-critical telemetry data and requires storage quota/cleanup management.

---

### Decision 1.2: Tab Lifecycle & Reliable Flush via `sendBeacon`
- **Decision**: Bind to the browser `visibilitychange` event (and fallback `pagehide`/`beforeunload`). When `document.visibilityState === 'hidden'`, immediately flush all remaining queued events via `navigator.sendBeacon(endpoint, blob)` where `blob` is constructed with type `application/json`. If `sendBeacon` is unavailable or returns `false` (e.g., buffer quota exceeded), fallback to `fetch(endpoint, { method: 'POST', body, keepalive: true, headers: { 'Content-Type': 'application/json' } })`.
- **Rationale**:
  - Browsers routinely cancel in-flight `fetch`/`XMLHttpRequest` calls when tabs close or navigate away.
  - `navigator.sendBeacon` is explicitly designed for asynchronous background delivery during unloading without delaying page teardown.
  - `fetch` with `keepalive: true` provides modern fallback parity across browsers.
- **Alternatives Considered**:
  - *Synchronous `XMLHttpRequest` in `unload`*: Deprecated in modern browsers, blocks main thread, penalized by browser performance budgets.
  - *No exit flush*: Results in loss of the final 10 seconds of user interaction and exit navigation metrics.

---

### Decision 1.3: Exponential Backoff & Fault Isolation
- **Decision**: On network or server delivery failure (HTTP 5xx, network timeout), retry batch delivery up to 3 times with exponential backoff:
  - Attempt 1: 1,000 ms delay
  - Attempt 2: 2,000 ms delay
  - Attempt 3: 4,000 ms delay  
  If the third attempt fails, discard the batch and clear the retry buffer. Telemetry errors are logged to internal diagnostic debug channels but NEVER thrown to the calling component.
- **Rationale**:
  - Telemetry is non-critical operational observability; failures must never block, crash, or interrupt core warehouse workflows (picking, PO creation, scanning).
  - Exponential backoff prevents thundering herd retries against a recovering backend gateway.
- **Alternatives Considered**:
  - *Infinite retries*: Leaks client memory if backend service is unreachable.
  - *Bubble errors to UI*: Degrades user experience by showing telemetry error toasts on business screens.

---

### Decision 1.4: Automatic Envelope Metadata Enrichment
- **Decision**: Expose only `track(eventType: string, properties: Record<string, unknown>): void`. The service automatically injects all standard envelope fields:
  - `eventId`: UUIDv4 generated at call time using `crypto.randomUUID()`.
  - `sessionId`: Read from transient `sessionStorage` (or initialized once per session tab lifecycle).
  - `userId`: Derived from authenticated session / JWT claims, or `null` if unauthenticated.
  - `timestamp`: ISO 8601 UTC string (`new Date().toISOString()`).
  - `schemaVersion`: Shared constant `"1.0.0"`.
  - `requestId`: Correlation UUID generated per capture or inherited from active tracing span.
- **Rationale**:
  - Prevents envelope pollution in feature components and ensures uniform schema compliance.
  - Enforces isolation between application state and telemetry metadata.
- **Alternatives Considered**:
  - *Requiring components to pass metadata*: High boilerplate, risk of inconsistent timestamps, missing fields, or incorrect UUID generation.

---

## 2. Backend Stub Endpoint & Contract Validation

### Decision 2.1: FastAPI Router & Pydantic Schema
- **Decision**: Create `services/api/routers/telemetry.py` mounting `POST /telemetry/events` (and prefix-compatible `/api/v1/telemetry/events`). Define Pydantic models:
  - `TelemetryEvent`: Strict model with `eventId: UUID`, `timestamp: datetime`, `sessionId: str`, `userId: Optional[str]`, `event_type: str` (regex validated `^[a-z0-9]+(_[a-z0-9]+)+$`), `schemaVersion: str` (regex `^[0-9]+\.[0-9]+\.[0-9]+$`), `requestId: str`, and `properties: Dict[str, Any]`.
  - `TelemetryBatch`: `events: List[TelemetryEvent]` with validation that `events` is a non-empty list.
- **Decision on Response**: Return HTTP 200 with JSON payload `{"received": len(batch.events)}`. Log received count and each `event_type` using Python's standard `logging` module.
- **Rationale**:
  - Enforces schema validation at the HTTP boundary. Invalid envelopes immediately return `422 Unprocessable Entity` without polluting server logs.
  - Establishes the exact Pydantic contract that will be connected to analytical storage (BigQuery/Kafka) in future phases without breaking frontend compatibility.
- **Alternatives Considered**:
  - *Accepting arbitrary unvalidated JSON*: Fails contract enforcement and risks schema drift.

---

### Decision 2.2: Environment Variable Configuration
- **Decision**:
  - Frontend: Read `NEXT_PUBLIC_TELEMETRY_ENDPOINT` (e.g. `http://localhost:8000/telemetry/events` or `/api/telemetry/events`). Fallback default: `http://localhost:8000/telemetry/events`.
  - Backend: Read `TELEMETRY_ENDPOINT` from environment (e.g., in `.env` / `config.py`) to establish endpoint URL configuration pattern across services.
- **Rationale**:
  - Enables independent backend / frontend deployments across local dev, staging, and production environments without code modification.
- **Alternatives Considered**:
  - *Hardcoded URLs*: Breaks containerized deployments and cross-environment CI testing.

---

## 3. Cross-Cutting Technical & Business Event Instrumentation

### Decision 3.1: Technical Baseline Instrumentation
- **Decision**:
  1. `frontend_error_captured`: Hook into `window.onerror`, `window.onunhandledrejection`, and Next.js React Error Boundary to record unhandled crashes (`error_name`, `error_message`, `stack_trace`, `url`, `component_name`).
  2. `api_latency_recorded`: Instrument central API fetch utilities (`fetchWithAuth` or API service wrappers) to measure round-trip milliseconds (`endpoint_path`, `http_method`, `duration_ms`, `http_status_code`, `success`).
  3. `section_navigation_tracked`: Instrument backoffice layout / router change observer to log transitions (`source_section`, `destination_section`, `navigation_duration_ms`).
- **Rationale**:
  - Provides instant observability across the entire Backoffice without depending on specific business module views.

---

### Decision 3.2: Business Flow Instrumentation & Strict Property Allowlists
- **Decision**: Instrument primary inventory flows conforming strictly to `docs/telemetry/event-schemas.json`:
  - `inbound_order_created`: `inboundOrderId`, `clientId`, `warehouseCode`, `totalSkus`, `totalUnits`, `sourceChannel`
  - `stock_threshold_triggered`: `skuId`, `warehouseCode`, `currentAvailableQuantity`, `safetyThresholdQuantity`, `triggerSeverity`
  - `direct_stock_edit_rejected`: `attemptedByUserId`, `warehouseCode`, `skuId`, `attemptedDelta`, `rejectionReason`
  - `stock_validation_failed`: `orderId`, `warehouseCode`, `skuId`, `expectedQuantity`, `actualQuantity`, `failureReason`
  - `outbound_order_fulfilled`: `orderId`, `clientId`, `warehouseCode`, `carrierCode`, `fulfillmentDurationSeconds`, `totalItems`
- **Zero PII Policy**: Strip or omit all plaintext customer emails, personal names, and passwords.
- **Rationale**:
  - Aligns 100% with the approved TrackFlow telemetry taxonomy and EU GDPR / California CCPA privacy standards.
