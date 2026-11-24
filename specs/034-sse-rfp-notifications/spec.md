# Feature Specification: Real-Time RFP Ticket Notifications

**Feature Branch**: `034-sse-rfp-notifications`

**Created**: 2026-11-24

**Status**: Complete

**Input**: User description: "TrackFlow — Real-Time Systems: SSE Notifications (Part 1 of 2). Replace manual dashboard refreshes and polling with a Server-Sent Events (SSE) push channel that notifies the frontend when a new RFP ticket is registered in TrackFlow, with automatic reconnection, missed-event recovery, and deduplication."

## Clarifications

### Session 2026-11-24

- Q: How should a new RFP ticket be registered to trigger the `rfp_ticket_created` SSE notification? → A: Support both a direct non-LLM ticket registration endpoint (`POST /api/v1/rfp/tickets`) that immediately persists/registers a ticket with `status: "analyzing"` and broadcasts `rfp_ticket_created`, plus emission from the existing intake flow once an RFP is classified as valid and its metadata is extracted.
- Q: What missed-ticket recovery mechanism should the SSE notification pipeline use when a disconnected client reconnects? → A: Hybrid SSE `id:` + `Last-Event-ID` server-side bounded ring-buffer replay combined with client-side REST reconciliation (`GET /api/v1/rfp/tickets`) as fallback, deduplicated by `ticket_id`.
- Q: What canonical HTTP route path should expose the Server-Sent Events (SSE) stream for RFP notifications? → A: `GET /api/v1/rfp/notifications/stream` (and legacy `/rfp/notifications/stream` via dual-mount, with `/api/v1/rfp/events` / `/rfp/events` aliased to the same handler for compatibility).
- Q: Should either of the optional real-time events from Section 4 of the briefing (`sla_threshold_alert` or `ticket_escalated_to_senior`) be included in scope alongside `rfp_ticket_created`? → A: Keep mandatory scope strictly focused on `rfp_ticket_created` (no optional events implemented now), while keeping the SSE event broadcaster extensible by event name.
- Q: What quantitative targets should govern the SSE server keep-alive heartbeat interval and the frontend progressive reconnection backoff schedule? → A: Emit server keep-alive comment frames (`: keep-alive`) every 15 seconds (configurable for tests) and use exponential client reconnection backoff starting at 1s (`1s, 2s, 4s, 8s, 16s`, capped at 30s), halting retries on HTTP 401/403.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Real-Time New RFP Ticket Arrival on Commercial Dashboard (Priority: P1)

Commercial leadership and sales team members (such as Miguel Torres, Commercial Director, and his team) monitor the backoffice dashboard to see incoming Request for Proposal (RFP) opportunities. Previously, team members had to manually reload the page or rely on periodic polling to discover newly registered RFP tickets. With this capability, as soon as an incoming document is classified as a valid RFP and registered as a new ticket with initial status `analyzing`, every connected and authenticated commercial user sees the new ticket appear immediately on their dashboard with a distinct visual indicator, without refreshing the page or reloading the entire list.

**Why this priority**: Immediate visibility into incoming RFP tickets is the primary business driver of this feature, directly eliminating manual dashboard checks and latency in commercial response times.

**Independent Test**: Can be fully tested by opening the backoffice RFP dashboard as an authenticated user, registering a new RFP ticket in the system with status `analyzing`, and verifying that the ticket appears automatically on the dashboard with its identifying metadata and visual highlight within seconds, without any user interaction or full-list reload.

**Acceptance Scenarios**:

1. **Given** an authenticated commercial user is viewing the RFP dashboard with an active real-time notification connection, **When** a new RFP ticket is registered in the system with status `analyzing`, **Then** the dashboard automatically receives the `rfp_ticket_created` notification and displays the new ticket entry immediately without a page reload or full dataset refetch.
2. **Given** a new RFP ticket arrives via the real-time notification stream, **When** it is rendered on the dashboard, **Then** it displays the exact domain fields defined in the briefing (`ticket_id`, `rfp_id`, `client_name`, `client_country`, `services_requested`, `status: "analyzing"`, and `created_at`) and is visually distinguished as a newly arrived notification compared to pre-existing tickets.
3. **Given** multiple authenticated commercial users have the dashboard open simultaneously, **When** a single new RFP ticket is registered, **Then** all connected users receive the notification concurrently without interfering with one another's streams.

---

### User Story 2 - Authenticated Stream Access & Idle Connection Stability (Priority: P2)

Only authorized backoffice personnel may receive real-time commercial RFP notifications, as RFP metadata contains sensitive client and opportunity information. Furthermore, commercial users keep the dashboard open throughout the workday across corporate networks and proxies that may close idle connections if no traffic flows over the channel.

**Why this priority**: Enforcing backoffice authentication prevents unauthorized exposure of commercial pipeline activity, while keep-alive heartbeat frames ensure the real-time stream remains open during quiet periods between RFP arrivals.

**Independent Test**: Can be independently tested by attempting to connect to the real-time stream without valid credentials (verifying immediate rejection) and by holding an authenticated connection open during an idle period with no new tickets (verifying periodic heartbeat frames keep the connection alive).

**Acceptance Scenarios**:

1. **Given** a client without an authentication token or with an expired/invalid backoffice token, **When** the client requests a connection to the real-time notification stream, **Then** the system rejects the request before establishing a stream and emits zero events to the client.
2. **Given** an authenticated client connected to the real-time notification stream, **When** no new RFP tickets are registered for an extended period, **Then** the server periodically transmits keep-alive comment frames so the connection remains open and active.

---

### User Story 3 - Automatic Reconnection, Missed-Ticket Recovery & Deduplication (Priority: P3)

Network interruptions, laptop sleep cycles, or temporary backend restarts can sever a user's active notification stream. When connectivity drops and is later restored, the dashboard must automatically reconnect using progressive backoff, recover any RFP tickets that were registered while the connection was down, and deduplicate entries so no ticket ever appears more than once on the user's screen.

**Why this priority**: Real-time systems in production face transient network drops; without automated recovery and deduplication, commercial users would either miss critical RFPs registered during a brief outage or see confusing duplicate rows.

**Independent Test**: Can be independently tested by simulating a network disconnection on an open dashboard, registering one or more new RFP tickets while disconnected, restoring connectivity, and verifying that progressive backoff reconnects the stream, recovers the missed tickets, and displays each unique `ticket_id` exactly once.

**Acceptance Scenarios**:

1. **Given** an authenticated user has an active real-time stream on the dashboard, **When** the stream connection drops unexpectedly, **Then** the dashboard automatically attempts to reconnect using progressive backoff delays rather than flooding the server with immediate retries or requiring a manual browser refresh.
2. **Given** a user's real-time stream was disconnected while one or more new RFP tickets were registered, **When** the dashboard successfully reconnects, **Then** the recovery mechanism retrieves the missed tickets and merges them into the view alongside subsequent live events.
3. **Given** a ticket is delivered both through the missed-ticket recovery mechanism and through the live stream (or replayed across reconnects), **When** the dashboard processes incoming ticket data, **Then** it deduplicates entries by `ticket_id` so the ticket appears only once in the UI and notification list.

---

### Edge Cases

- **Client disconnects abruptly mid-stream**: When a user closes their browser tab or loses network connectivity, the server cleans up that client's subscription resources without leaking memory or disrupting events sent to other connected users.
- **High-concurrency fan-out (2 to 50+ simultaneous sales users)**: When dozens of sales users are connected concurrently and a new RFP ticket is registered, every connected client receives the event promptly without blocking ticket creation or degrading server responsiveness.
- **Rapid ticket creation during reconnection window**: If a ticket is created at the exact moment a client finishes reconnecting and running its recovery check, deduplication by `ticket_id` guarantees that overlapping recovery and live stream delivery never result in duplicate UI cards or duplicate notifications.
- **Malformed or unauthorized token expiration mid-session**: If a client's credentials are invalid upon a reconnection attempt, the reconnection is rejected cleanly and the UI surfaces an appropriate authentication/connection status rather than looping indefinitely without feedback.
- **No AI/Agent invocation on notification path**: Registering or broadcasting a new RFP ticket notification operates strictly within the communication layer and never triggers any language model, external AI service, or autonomous agent execution.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a real-time Server-Sent Events (SSE) stream endpoint in the backend service at `GET /api/v1/rfp/notifications/stream` (with legacy mount `GET /rfp/notifications/stream` and compatibility alias `GET /api/v1/rfp/events` / `GET /rfp/events`) that pushes notifications to connected clients using the `text/event-stream` content type and standard cache/connection stream headers (`Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`).
- **FR-002**: Whenever a new RFP ticket is registered in the system with initial status `analyzing`—either via a direct non-LLM ticket registration endpoint (`POST /api/v1/rfp/tickets` / `/rfp/tickets`) or via the document intake flow once classified as a valid RFP with extracted metadata—the stream MUST emit a named event `rfp_ticket_created` (not a generic unnamed `message` event).
- **FR-003**: The `rfp_ticket_created` event payload MUST be a flat JSON object in the `data:` field (without a nested `{"event", "data"}` wrapper) containing at least `ticket_id`, `rfp_id`, `client_name`, `client_country`, `services_requested`, `status` (set to `"analyzing"`), and `created_at`, matching the exact field names and domain values in `docs/real-time-notification/trackflow-BRIEFING.es.md`.
- **FR-004**: The real-time stream endpoint MUST enforce the same backoffice authentication policy as existing protected backoffice routes, rejecting unauthenticated or invalid-token requests before streaming any events.
- **FR-005**: The backend stream MUST emit periodic SSE keep-alive comment frames (`: keep-alive`) every 15 seconds (configurable for test overrides) during idle periods to prevent intermediate proxies or browsers from closing active connections prematurely.
- **FR-006**: The backend fan-out mechanism MUST support multiple simultaneous connected clients so that registering a new RFP ticket broadcasts the `rfp_ticket_created` event to all active subscribers and removes subscribers cleanly when they disconnect.
- **FR-007**: The backoffice dashboard MUST consume the real-time notification stream using an authenticated streaming request passing the `Authorization: Bearer <token>` header (rather than bare `EventSource`), replacing manual refresh and periodic polling for new RFP ticket discovery.
- **FR-008**: Upon receiving an `rfp_ticket_created` event, the dashboard MUST insert and display the new ticket in real time without performing a page reload or refetching the full ticket dataset on every event.
- **FR-009**: The dashboard MUST visually distinguish newly arrived real-time RFP ticket notifications from pre-existing dashboard ticket records so commercial users can immediately spot new arrivals.
- **FR-010**: When the real-time stream disconnects due to network loss or server interruption, the dashboard client MUST automatically attempt reconnection using exponential backoff delays starting at 1 second (`1s, 2s, 4s, 8s, 16s`, capped at 30 seconds maximum delay), and MUST halt automatic reconnection attempts immediately if rejected with HTTP 401 or 403.
- **FR-011**: The system MUST implement and document a hybrid missed-ticket recovery strategy: every SSE event frame MUST include a monotonic `id:` line, the server MUST replay missed events from a bounded in-memory ring buffer when a reconnecting client provides `Last-Event-ID` (header or query parameter), and the client MUST fall back to fetching `GET /api/v1/rfp/tickets` reconciliation on reconnect when the buffer was missed or reset.
- **FR-012**: The dashboard MUST deduplicate tickets by `ticket_id` across initial load, live SSE events, and post-reconnection recovery so that the same ticket is never rendered or notified more than once.
- **FR-013**: The implementation MUST remain strictly within the real-time communication and presentation layers and MUST NOT invoke any large language model (LLM), machine learning model, or AI agent.
- **FR-014**: Automated tests and verification documentation MUST validate wire-level SSE framing (`Content-Type: text/event-stream`, named `event: rfp_ticket_created`, flat JSON `data:` schema), authentication enforcement, reconnection backoff, missed-ticket recovery, deduplication, and architectural trade-off documentation (2 vs. 50 concurrent users fan-out, recovery/deduplication strategy, and SSE vs. WebSockets).

### Key Entities *(include if feature involves data)*

- **RFP Ticket (`Ticket`)**: Represents an operational tracking record created when an incoming document is classified as a valid RFP. Key attributes include `ticket_id` (unique identifier, e.g., `tkt_0225`), `rfp_id` (linked RFP identifier, e.g., `rfp_0071`), `status` (lifecycle state: `analyzing`, `intake_complete`, `drafting`, `under_evaluation`, `waiting_for_approval`, `done`, `discarded`; always `analyzing` at initial notification time), and `created_at` (ISO-8601 registration timestamp).
- **RFP Metadata**: Commercial context associated with the RFP ticket and included in the summary notification payload so commercial users can triage priority at a glance. Key attributes in the notification include `client_name`, `client_country`, and `services_requested` (list of requested logistics services such as `warehouse`, `lastmile`), alongside broader RFP attributes (`monthly_volume`, `deadline`, `budget_range`, `departments_needed`).
- **Real-Time Notification Event (`rfp_ticket_created`)**: A transient push message formatted according to the SSE specification (`event: rfp_ticket_created` and `data: <JSON>`) carrying the newly created RFP ticket summary to all connected commercial dashboard subscribers.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Authenticated commercial users viewing the dashboard see newly registered RFP tickets (`status = analyzing`) appear on screen within 2 seconds of ticket registration without any manual refresh or user interaction.
- **SC-002**: 100% of unauthenticated or invalid-token connection attempts to the notification stream are rejected immediately with zero events leaked.
- **SC-003**: When network connectivity is interrupted and restored, the dashboard automatically initiates reconnection using progressive backoff and recovers 100% of tickets registered during the disconnection window.
- **SC-004**: 0 duplicate ticket entries or duplicate notifications appear on the dashboard for any single `ticket_id`, even across concurrent live events, reconnect replays, and recovery reconciliation.
- **SC-005**: The notification pipeline executes 0 calls to any LLM, AI model, or agent during ticket creation broadcasting, streaming, reconnection, or testing.
- **SC-006**: Simultaneous connections from multiple commercial users (tested with multiple concurrent subscribers and documented for 2 to 50 concurrent users) receive every `rfp_ticket_created` event reliably without dropped notifications or leaked subscriptions after client disconnect.

## Assumptions

- The existing RFP intake and ticket registration flow (built in specs `031-rfp-intake` through `033-rfp-approval-completion`) already defines the `Ticket` and RFP metadata domain structures in `services/api/` and `uis/backoffice/`; this feature extends those existing paths rather than creating a separate application.
- Existing backoffice JWT authentication utilities and token storage in the backoffice UI are reused to authenticate the streaming connection.
- Only the required `rfp_ticket_created` event is in scope for Part 1; the optional business threshold alert (`sla_threshold_alert`) and agent escalation (`ticket_escalated_to_senior`) mentioned in Section 4 of the briefing are explicitly out of scope for implementation, while the SSE broadcaster interface remains extensible by event name.
- Single-instance in-memory pub/sub broadcasting is sufficient for the local/containerized runtime, while architectural analysis for scaling from 2 to 50+ concurrent users across processes (e.g., shared broker vs. in-process fan-out) will be documented in the pull request deliverables.
