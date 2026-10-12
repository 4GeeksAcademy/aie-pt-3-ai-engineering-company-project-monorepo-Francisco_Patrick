# Feature Specification: Telemetry Event Capture

**Feature Branch**: `015-telemetry-event-capture`

**Created**: 2026-10-06

**Status**: Draft

**Input**: User description: "/speckit-specify Feature: Telemetry Event Capture (Phase 1 plan: docs/telemetry/telemetry-plan.md, Phase 1 schemas: docs/telemetry/event-schemas.json)"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resilient Client-Side Event Capture & Batch Delivery (Priority: P1)

As a TrackFlow engineer and systems operator, I need frontend user actions and system health events in the Backoffice UI to be captured seamlessly and dispatched in batches without degrading UI performance or losing data during navigation and tab closures.

**Why this priority**: Forms the primary data collection pipeline in the frontend. All UI instrumentation depends on an efficient, buffered capture mechanism that isolates UI components from network calls and prevents event loss on page exits.

**Independent Test**: Trigger multiple UI interactions, verify events accumulate in memory and flush automatically when either 20 events accumulate or 10 seconds elapse, and verify pending events are flushed immediately when changing tab visibility or closing the tab.

**Acceptance Scenarios**:

1. **Given** a user interacts with the Backoffice UI, **When** components call `track(eventType, properties)`, **Then** the event is enriched with mandatory envelope metadata (`eventId`, `sessionId`, `userId`, `timestamp`, `schemaVersion`, `requestId`) and queued in memory without initiating immediate synchronous network requests.
2. **Given** queued events in memory, **When** the queue size reaches 20 events or the 10-second timer elapses, **Then** the entire batch is sent via an HTTP POST request to the configured telemetry endpoint.
3. **Given** pending events in the queue, **When** the user closes the tab or switches tab visibility to hidden, **Then** the service immediately flushes the remaining queue using `navigator.sendBeacon`.
4. **Given** a network failure during batch delivery, **When** the batch dispatch fails, **Then** the service retries up to 3 times with exponential backoff before discarding the batch without blocking the application or throwing unhandled errors to the user.

---

### User Story 2 - Backend Telemetry Ingestion & Contract Validation (Priority: P1)

As a backend data engineer, I need a dedicated telemetry endpoint to receive, validate, and log batches of structured telemetry events matching the approved event envelope contract so that downstream pipeline components can ingest verified payloads.

**Why this priority**: Required to verify end-to-end data transmission from the frontend, ensuring payload contract adherence before full database/stream processing sinks are attached.

**Independent Test**: Send a valid telemetry event batch to `POST /telemetry/events` and observe a `200 OK` response returning `{ "received": N }` along with server-side structured log entries for each received `event_type`.

**Acceptance Scenarios**:

1. **Given** a valid JSON payload containing `{ "events": [...] }` conforming to the `TelemetryEvent` envelope schema, **When** a client posts to `/telemetry/events`, **Then** the server validates the schema, logs the event count and each `event_type`, and returns `200 OK` with `{ "received": N }`.
2. **Given** a payload with missing mandatory envelope fields or invalid types, **When** posted to `/telemetry/events`, **Then** the server rejects the request with standard `422 Unprocessable Entity` validation errors.
3. **Given** backend service initialization, **When** the server starts, **Then** the telemetry endpoint routing and target destinations are configured via environment variables (`TELEMETRY_ENDPOINT`).

---

### User Story 3 - Cross-Cutting Technical Telemetry Baseline (Priority: P2)

As a platform reliability engineer, I need automatic capture of application errors, core performance metrics, and navigation paths across all backoffice sections so that unexpected regressions and user friction can be detected immediately.

**Why this priority**: Technical observability provides immediate visibility into frontend crashes, slow network requests, and overall navigation health across all operational modules.

**Independent Test**: Intentionally trigger an unhandled rejection/error, complete page navigation, and execute an API call, then verify that `frontend_error_captured`, `section_navigation_tracked`, and `api_latency_recorded` events are emitted with strict property allowlists.

**Acceptance Scenarios**:

1. **Given** an uncaught runtime JavaScript exception or unhandled promise rejection in the backoffice, **When** the error occurs, **Then** a `frontend_error_captured` event is captured containing error name, message, stack trace snippet, and component context without sensitive user credentials.
2. **Given** a user navigates between backoffice sections (e.g., Inventory, Orders, Incidents), **When** route transitions occur, **Then** a `section_navigation_tracked` event is emitted recording source section, destination section, and navigation duration.
3. **Given** standard API interactions in the backoffice, **When** an API call completes, **Then** an `api_latency_recorded` event captures the endpoint path, HTTP method, duration in milliseconds, and status code.

---

### User Story 4 - Departmental Business & Operational Flow Instrumentation (Priority: P2)

As an operations manager (Warehouse, Logistics, Reverse, CX), I need business operations and workflow milestones to be instrumented according to the approved telemetry plan without exposing personally identifiable information (PII).

**Why this priority**: Powers real-time operational metrics, low-stock alerts, picking discrepancy counts, return triage automation, and SLA tracking defined in TrackFlow business requirements.

**Independent Test**: Perform key warehouse actions (creating an inbound PO, triggering low stock, picking items, attempting direct stock modification), and verify that the corresponding events (`inbound_order_created`, `stock_threshold_triggered`, `direct_stock_edit_rejected`, `stock_validation_failed`, `outbound_order_fulfilled`) are emitted with exact property allowlists.

**Acceptance Scenarios**:

1. **Given** an operator accesses the inventory workspace and registers an inbound order, **When** the action completes, **Then** `inbound_order_created` is emitted with warehouse ID, SKU count, and total units.
2. **Given** an inventory stock level crosses below the safety buffer, **When** the threshold is detected, **Then** `stock_threshold_triggered` is emitted with SKU ID, current quantity, and threshold level.
3. **Given** an operator attempts an ad-hoc un-audited direct stock edit that is rejected by system policy, **When** the rejection occurs, **Then** `direct_stock_edit_rejected` is recorded with actor ID, target SKU, and attempted mutation.
4. **Given** any emitted business event, **When** properties are checked, **Then** zero raw PII (such as plaintext customer emails, full names, or passwords) is included in the payload.

---

### Edge Cases

- **Offline / Network Disconnection**: When the client loses network connectivity, events accumulate in the local memory queue up to a reasonable cap (e.g., 100 events); failed batches retry with exponential backoff and are gracefully dropped after maximum retry attempts without crashing the UI.
- **Rapid Navigation / Multiple Tab Closes**: When multiple rapid tab switches or sudden browser terminations occur, `visibilitychange` triggers `sendBeacon` synchronously with current pending batches to avoid losing in-flight events.
- **Malformed Event Properties**: If a component passes invalid or extra non-allowlisted properties, the event capture service sanitizes or drops invalid properties while logging a developer warning in non-production environments.
- **High Event Bursts**: Under rapid consecutive user interactions (e.g. rapid scanning or bulk filtering), the 20-event queue threshold triggers an immediate flush, keeping memory footprint low.
- **Unauthenticated State**: When events occur before user login (or during session expiration), `userId` is set to `null` while maintaining a persistent `sessionId`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a centralized `TelemetryService` in `uis/backoffice/app/services/telemetry.ts` exposing a single `track(eventType: string, properties: Record<string, unknown>): void` function.
- **FR-002**: UI components MUST NOT perform direct `fetch` or `axios` calls for telemetry; all telemetry emission MUST route through `track()`.
- **FR-003**: The `TelemetryService` MUST automatically generate and populate standard envelope fields for every event: `eventId` (UUIDv4), `sessionId` (persistent across session memory), `userId` (authenticated user ID or null), `timestamp` (ISO 8601 UTC string at capture time), `schemaVersion` (e.g., "1.0.0"), and `requestId` (distributed trace correlation UUID).
- **FR-004**: The `TelemetryService` MUST maintain an in-memory event queue that buffers events and dispatches them in batches to the telemetry endpoint when 20 events accumulate OR 10 seconds elapse since the previous batch.
- **FR-005**: The `TelemetryService` MUST attach a `visibilitychange` listener to flush pending queued events using `navigator.sendBeacon` when the document visibility becomes hidden or the window unloads.
- **FR-006**: The `TelemetryService` MUST implement exponential backoff retry logic (up to 3 retry attempts) on network failures before dropping a failed batch.
- **FR-007**: The frontend telemetry target URL MUST be read from the environment variable `NEXT_PUBLIC_TELEMETRY_ENDPOINT` and MUST NOT be hardcoded.
- **FR-008**: The backend MUST expose a `POST /telemetry/events` endpoint in a dedicated FastAPI router under `services/api/routers/telemetry.py`.
- **FR-009**: The backend `POST /telemetry/events` endpoint MUST validate the incoming payload against a Pydantic `TelemetryBatch` model containing an array of `TelemetryEvent` items matching the standard envelope schema (`eventId`, `timestamp`, `sessionId`, `userId`, `event_type`, `schemaVersion`, `requestId`, `properties`).
- **FR-010**: The backend endpoint MUST log the number of events received and the `event_type` of each item, returning HTTP `200 OK` with `{ "received": N }` where N is the total event count.
- **FR-011**: The backend MUST declare and read `TELEMETRY_ENDPOINT` in its configuration environment.
- **FR-012**: The system MUST instrument a cross-cutting technical baseline including uncaught frontend errors (`frontend_error_captured`), API/page performance metrics (`api_latency_recorded`), and section navigation (`section_navigation_tracked`).
- **FR-013**: The system MUST instrument mandatory business operational metrics from `CONTEXT.md` and `docs/telemetry/telemetry-plan.md` (including warehouse inventory flows: `inbound_order_created`, `stock_threshold_triggered`, `direct_stock_edit_rejected`, `stock_validation_failed`, and `outbound_order_fulfilled`).
- **FR-014**: All instrumented events MUST adhere strictly to event names and property allowlists defined in `docs/telemetry/event-schemas.json` and MUST NOT include unvetted attributes.
- **FR-015**: No raw Personally Identifiable Information (PII) such as passwords, cleartext emails, or unmasked credit cards MUST be transmitted in any telemetry payload.
- **FR-016**: User profile and core application state MUST remain strictly separated from append-only telemetry event streams.

### Key Entities *(include if feature involves data)*

- **TelemetryEvent**: Standard envelope entity containing unique event identifier (`eventId`), capture timestamp (`timestamp`), session context (`sessionId`), user context (`userId`), event taxonomy type (`event_type`), version string (`schemaVersion`), distributed correlation token (`requestId`), and domain properties dictionary (`properties`).
- **TelemetryBatch**: Collection payload structure wrapping an array of `TelemetryEvent` items sent in a single transport request (`events: TelemetryEvent[]`).
- **TelemetryQueue**: In-memory transient buffer holding un-flushed `TelemetryEvent` objects awaiting batch interval dispatch or immediate beacon flush.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of telemetry emissions across the backoffice pass through the single `track()` entrypoint with zero direct telemetry fetch calls elsewhere in application code.
- **SC-002**: Under normal navigation, telemetry events are buffered and delivered in batches of up to 20 events or every 10 seconds, reducing client HTTP request overhead by over 80% compared to per-event transmission.
- **SC-003**: 100% of pending queued events are dispatched via `navigator.sendBeacon` upon page unload or tab hiding, achieving zero telemetry drop on normal tab navigation.
- **SC-004**: The backend `POST /telemetry/events` endpoint successfully parses, validates, and responds with HTTP 200 within under 50ms for standard batch payloads up to 50 events.
- **SC-005**: 100% of mandatory operational metrics from `CONTEXT.md` and all 3 baseline technical metrics (errors, latency, navigation) are actively instrumented with schema-compliant payloads and zero PII leakage.

## Assumptions

- The backend stub endpoint operates in-memory/structured-logging mode for Phase 1 without writing directly to analytical databases (BigQuery/ClickHouse/Kafka) until downstream processing pipelines are connected in subsequent phases.
- `navigator.sendBeacon` is supported by all target modern browsers (Chrome, Firefox, Safari, Edge); a standard `fetch` with `keepalive: true` or fallback synchronous flush is used where appropriate.
- User identity (`userId`) is acquired from the authenticated session context when available, or passed as `null` for unauthenticated pre-login interactions.
- Configuration variables `NEXT_PUBLIC_TELEMETRY_ENDPOINT` (frontend) and `TELEMETRY_ENDPOINT` (backend) are provided via environment configuration (`.env` / process environment).
