# Feature Specification: Telemetry Event Storage

**Feature Branch**: `017-telemetry-event-storage`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User description: "/speckit-specify # Company's Telemetry – Storage - Replace stub telemetry endpoint with real persistent storage in FastAPI and Supabase, supporting partial validation and bulk insert"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Fault-Tolerant Telemetry Ingestion with Partial Batch Persistence (Priority: P1)

As a data and reliability engineer, I need the telemetry ingestion service to validate each event individually and persist valid events in bulk even when some events in the batch are malformed, so that telemetry data collection remains resilient and one bad event does not drop an entire batch of operational insights.

**Why this priority**: Essential to the data pipeline. High-throughput telemetry streams often encounter malformed or legacy event payloads; dropping entire batches causes significant data loss and blind spots in operational monitoring.

**Independent Test**: Submit a mixed batch containing 3 valid events and 2 malformed events to the telemetry ingestion endpoint. Verify that the endpoint returns HTTP 200 OK with `{ "received": 5, "stored": 3, "rejected": 2 }`, and confirm that only the 3 valid events are saved to persistent storage in a single transaction.

**Acceptance Scenarios**:

1. **Given** a batch of events where all events conform to the event contract, **When** the batch is submitted, **Then** all events are validated, persisted to storage in a single bulk operation, and the receipt reports `received: N`, `stored: N`, and `rejected: 0`.
2. **Given** a batch containing both valid events and malformed events (missing fields, wrong types, or invalid formats), **When** the batch is submitted, **Then** the service individually isolates and rejects the malformed events, persists all valid events in a single bulk operation, and returns a receipt indicating the exact count of received, stored, and rejected events.
3. **Given** a batch where all submitted events are malformed, **When** the batch is submitted, **Then** the service rejects each event without persisting any records, commits zero database writes, and returns a receipt with `received: N`, `stored: 0`, and `rejected: N`.

---

### User Story 2 - Seamless Integration with Existing Frontend Telemetry Clients (Priority: P1)

As a frontend developer and backoffice operator, I need the persistent telemetry endpoint to maintain full backward compatibility with the existing client-side telemetry service so that client instrumentation continues operating without modifications or broken workflows.

**Why this priority**: Zero-disruption migration is required. The frontend telemetry service dispatches buffered event batches and evaluates HTTP response status codes without inspecting receipt payload internals.

**Independent Test**: Trigger user workflows in the Backoffice UI that dispatch telemetry events (e.g. inventory registrations, navigation, errors) and observe that all batch dispatches complete successfully with HTTP 200 OK status codes and no retry loops or network failures.

**Acceptance Scenarios**:

1. **Given** the active Backoffice user interface, **When** client-side buffered events are flushed via POST request to `/telemetry/events`, **Then** the endpoint accepts the existing `{ "events": [...] }` envelope format and responds with HTTP 200 OK.
2. **Given** the frontend client inspecting response status codes, **When** a batch containing mixed or valid events is processed, **Then** the HTTP 200 OK status ensures the client does not trigger exponential retry delays or drop queued events.

---

### User Story 3 - End-to-End Operational Traceability & Audit Verification (Priority: P2)

As an operations manager and systems auditor, I need business actions (such as inbound inventory registrations and outbound dispatches) and technical system events (such as errors and authentication failures) to be persisted immutably with accurate event types, timestamps, and contextual properties so that system history can be queried reliably.

**Why this priority**: Provides the business and operational audit trail necessary for compliance, troubleshooting, inventory discrepancy investigations, and SLA tracking.

**Independent Test**: Execute an inbound order registration, an outbound order registration, and an intentional technical error in the backoffice. Query the persistent storage table directly to confirm that three distinct records exist with corresponding `event_type`, ISO UTC `timestamp`, and complete property/tag payloads.

**Acceptance Scenarios**:

1. **Given** an operator registers an inbound shipment in the inventory module, **When** the action completes and telemetry flushes, **Then** a persistent record with the corresponding event type and contextual attributes appears in storage.
2. **Given** an operator registers an outbound fulfillment order, **When** the action completes, **Then** a persistent record reflecting the outbound event type and related details is stored.
3. **Given** an unhandled technical error or failed login attempt occurs in the application, **When** the event is captured and ingested, **Then** a diagnostic telemetry record appears in storage with relevant error tags and zero leaked sensitive credentials.

---

### User Story 4 - Granular Ingestion Diagnostics for Data Quality Monitoring (Priority: P2)

As a telemetry platform maintainer, I need explicit visibility into event rejection rates and processing counts on every ingestion call so that anomalous clients or schema drifts can be detected immediately via automated monitoring.

**Why this priority**: Without explicit receipt statistics, upstream schema drift or malformed client instrumentation can silently corrupt data streams without operator awareness.

**Independent Test**: Send automated requests with known valid/invalid distributions and verify that response receipts always satisfy the invariant `received = stored + rejected`.

**Acceptance Scenarios**:

1. **Given** an ingestion request, **When** processing completes, **Then** the response body contains `{ "received": N, "stored": M, "rejected": R }` where N, M, and R are non-negative integers satisfying `N = M + R`.
2. **Given** individual events rejected during processing, **When** the rejection occurs, **Then** the service logs diagnostic details (e.g., event index, validation issue) internally without terminating or rolling back valid events.

---

### Edge Cases

- **Empty Batch Submission**: When a client submits `{ "events": [] }`, the service processes the empty list gracefully, performs zero database writes, and returns `{ "received": 0, "stored": 0, "rejected": 0 }` with HTTP 200 OK.
- **Envelope Structure Violations**: When a request body is completely missing the `events` field or passes non-list content (e.g. `{ "events": "invalid" }` or `{}`), the service rejects the request with HTTP 422 Unprocessable Entity.
- **Database Connection or Transaction Failure**: If the persistent storage layer suffers an outage or transaction failure during bulk insertion, the transaction rolls back cleanly, avoiding duplicate or partially inserted batches, and returns an appropriate server error without corrupting storage.
- **Max Batch Size / Flood Protection**: Batches containing an excessive number of events (e.g. exceeding 100 items) are capped or rejected according to maximum batch capacity limits to prevent memory exhaustion and denial of service.
- **Partial or Non-Standard Event Identifiers**: If an event contains malformed UUIDs, invalid ISO timestamps, or extra prohibited fields, that specific event is counted as rejected while adjacent valid events in the same payload are persisted.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose an HTTP POST endpoint at `/telemetry/events` that accepts a JSON envelope containing an `events` array.
- **FR-002**: The ingestion handler MUST parse the incoming `events` list flexibly without enforcing all-or-nothing request-level schema rejection on the outer batch container.
- **FR-003**: The ingestion handler MUST validate each event element individually against the standard `TelemetryEvent` envelope schema (`eventId`, `timestamp`, `sessionId`, `userId`, `event_type`, `schemaVersion`, `requestId`, `properties`).
- **FR-004**: System MUST NOT reject or cancel the processing of valid events when invalid or malformed events are present in the same batch.
- **FR-005**: System MUST accumulate all validated events from a batch and persist them in a single, atomic bulk insert transaction into the `telemetry_events` table.
- **FR-006**: System MUST return an ingestion receipt containing the exact numeric counts: `received` (total events evaluated), `stored` (events successfully persisted), and `rejected` (events failing schema validation).
- **FR-007**: The endpoint response MUST maintain backward compatibility with frontend clients by returning an HTTP 200 OK status for all successfully evaluated batches.
- **FR-008**: The underlying storage table (`telemetry_events`) MUST be write-only and immutable, preventing updates or row modifications after persistence.
- **FR-009**: The storage schema MUST record standard event attributes including unique event identifier, timestamp, session identity, user identity, event classification type, schema version, request trace identifier, and domain properties/tags.
- **FR-010**: System MUST record business events (inbound inventory orders, outbound inventory orders) and technical observability events (errors, authentication failures) generated by system applications with accurate taxonomy names and metadata.

### Key Entities *(include if feature involves data)*

- **Telemetry Event Record**: Represents a persisted, immutable telemetry occurrence containing event identifier, capture timestamp, session identifier, optional user identifier, event type name, schema version, request correlation identifier, and structured properties/tags payload.
- **Telemetry Batch Envelope**: The incoming JSON container carrying an array of raw event objects dispatched from client services.
- **Ingestion Outcome Receipt**: The response payload communicating the operational outcome of a batch ingestion operation, specifying total events received, events stored, and events rejected.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of valid events submitted in a mixed batch are successfully persisted regardless of the presence of malformed events in the same batch.
- **SC-002**: Batch ingestion processing completes in under 200ms for batches containing up to 50 events.
- **SC-003**: Ingestion outcome receipts strictly satisfy `received = stored + rejected` across 100% of processed requests.
- **SC-004**: Frontend client applications experience zero delivery failures or breaking changes when communicating with the persistent ingestion endpoint.
- **SC-005**: 100% of recorded business and technical events from user workflows are queryable in persistent storage with exact matching event type and timestamp fields.

## Assumptions

- The frontend telemetry service continues to transmit batches matching `{ "events": [...] }` and depends solely on the HTTP status code (200 OK) to confirm delivery.
- The existing Pydantic `TelemetryEvent` domain model remains unchanged and serves as the authoritative specification for individual event contract validation.
- The persistent database connection utilizes the configured relational database environment variables with fallback to local relational storage during isolated testing.
- An immutable table structure named `telemetry_events` will store persisted records with append-only access patterns.
- High-volume ingestion is optimized by batching database writes into a single bulk insert statement per HTTP request.
