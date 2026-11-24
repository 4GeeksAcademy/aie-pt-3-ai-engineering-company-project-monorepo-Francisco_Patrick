# Phase 0 Research: Real-Time RFP Ticket Notifications (SSE Part 1)

**Feature Branch**: `034-sse-rfp-notifications`  
**Date**: 2026-11-24  
**Specification**: [spec.md](./spec.md)  
**Briefing Reference**: [docs/real-time-notification/trackflow-BRIEFING.es.md](../../docs/real-time-notification/trackflow-BRIEFING.es.md)

---

## 1. Unknowns & Architectural Decisions Resolved

### 1.1 SSE Wire Framing & FastAPI Streaming Architecture

- **Decision**: Use FastAPI `StreamingResponse` (from `fastapi.responses`) with `media_type="text/event-stream"` and explicit HTTP headers (`Cache-Control: no-cache`, `Connection: keep-alive`, `X-Accel-Buffering: no`) backed by an asynchronous generator yielding W3C SSE frames.
- **Rationale**:
  - FastAPI / Starlette natively supports `StreamingResponse` with async generators without adding third-party SSE framework dependencies that could conflict with FastAPI `0.141+` or Pydantic `v2`.
  - Section 3 of `trackflow-BRIEFING.es.md` mandates exact named event framing:
    ```text
    id: <monotonic_event_id>
    event: rfp_ticket_created
    data: {"ticket_id":"tkt_0225","rfp_id":"rfp_0071","client_name":"Northline Apparel","client_country":"US","services_requested":["warehouse","lastmile"],"status":"analyzing","created_at":"2026-07-24T14:32:00Z"}

    ```
  - Each frame includes `id: <seq>\n`, `event: rfp_ticket_created\n`, `data: <compact-flat-json>\n\n` (no nested `{"event", "data"}` wrapper in `data:`).
- **Alternatives Considered**:
  - `sse-starlette` external library: Rejected because native Starlette/FastAPI `StreamingResponse` gives complete deterministic control over `id:`, `event:`, `data:`, and `: keep-alive` comment framing without extra dependencies.
  - WebSockets (`ws://`): Rejected for Part 1 because RFP arrival notifications are strictly unidirectional server-to-client push events; SSE works over standard HTTP, supports automatic `Last-Event-ID` semantics, and reserves WebSockets for Part 2 (bidirectional chat).

---

### 1.2 In-Memory Pub/Sub Broadcaster, Fan-Out & Scaling Analysis (2 vs. 50+ Users)

- **Decision**: Implement a thread-safe and async-safe `RFPNotificationBroadcaster` (implementing `RFPNotificationBroadcasterPort`) using per-subscriber `asyncio.Queue` instances and a bounded in-memory ring buffer (`collections.deque(maxlen=256)`) for recent event replay. Allow cross-thread publication (`publish_sync` / `publish`) so both async FastAPI route handlers and synchronous background pipeline threads (`run_rfp_pipeline_background`) can safely broadcast `rfp_ticket_created`.
- **Rationale**:
  - **2 Concurrent Users (Single Worker Process)**: In-process `asyncio.Queue` fan-out has sub-millisecond latency ($O(N)$ queue puts where $N=2$), zero external broker overhead, and automatic cleanup via `try/finally` when a client disconnects.
  - **50+ Concurrent Users (Multi-Worker / Multi-Instance Production)**:
    - Within a single Uvicorn async worker, 50 concurrent open SSE streams consume minimal memory (~50 lightweight `asyncio.Queue` objects and coroutines) and fan-out takes `< 1ms`.
    - Across multiple Uvicorn workers (`--workers 4`) or horizontally scaled containers, in-process memory is isolated per process: a ticket created on Worker A would only notify SSE clients connected to Worker A. To scale to 50+ users across multiple workers/pods, `RFPNotificationBroadcasterPort` is designed as a hexagonal port in `domain/rfp/ports.py` so the in-memory adapter can be swapped for a Redis Pub/Sub + Redis Streams (`XADD` / `XRANGE` for `Last-Event-ID` replay) or PostgreSQL `LISTEN/NOTIFY` adapter without changing any route handler or domain service.
- **Alternatives Considered**:
  - Mandatory Redis broker dependency in local/test runtime: Rejected to preserve deterministic zero-external-broker test execution in CI while documenting and abstracting the multi-worker scaling architecture via `RFPNotificationBroadcasterPort`.

---

### 1.3 Dual Trigger Points for `rfp_ticket_created` (Direct Non-LLM Endpoint + Intake Flow)

- **Decision**: Emit `rfp_ticket_created` from two complementary entry points:
  1. **Direct Non-LLM Ticket Registration Endpoint (`POST /api/v1/rfp/tickets` and legacy `POST /rfp/tickets`)**: Accepts commercial RFP ticket registration fields (`client_name`, `client_country`, `services_requested`, plus optional `ticket_id`, `rfp_id`, `monthly_volume`, `deadline`, `budget_range`, `currency`), persists the `IntakeTicket` (with status `analizando` / `"analyzing"`) and `RFPMetadata` in SQLModel, and immediately broadcasts `rfp_ticket_created` with `status: "analyzing"`. Executes **zero LLM or AI agent calls** (FR-013, SC-005).
  2. **Document Intake Flow (`RFPIntakePipeline._node_orchestrate`)**: When an uploaded PDF document is classified as a valid RFP (`is_rfp = True`) and its commercial metadata (`client_name`, `client_country`, `services_requested`) is extracted while the ticket is in initial analyzing status, the pipeline emits the same `rfp_ticket_created` SSE notification event.
- **Rationale**:
  - Directly satisfies Clarification 1, FR-002, and FR-013: automated tests, E2E verification, and commercial operators can register an RFP ticket deterministically via `POST /api/v1/rfp/tickets` without invoking any LLM, while PDF intake also triggers the real-time notification as soon as metadata is available.
  - Bilingual status harmonization: The existing SQLModel database stores `TicketStatus.ANALIZANDO = "analizando"`, while the briefing (`trackflow-BRIEFING.es.md` §2-§3) specifies `"status": "analyzing"` in the SSE `rfp_ticket_created` JSON payload. The SSE event payload strictly emits `"status": "analyzing"` (matching the briefing contract), and the REST ticket summary/list endpoints expose the briefing-aligned fields (`rfp_id`, `client_country`, `services_requested`) so client reconciliation and live SSE events share identical domain semantics.
- **Alternatives Considered**:
  - Emitting only on PDF upload before metadata extraction: Rejected because at raw file upload (`POST /api/v1/rfp/intake`), `client_name`, `client_country`, and `services_requested` are not yet known and the document hasn't been classified as a valid RFP.

---

### 1.4 Authenticated SSE Streaming & Keep-Alive Heartbeats

- **Decision**:
  - **Backend Auth**: Protect `GET /api/v1/rfp/notifications/stream` (and compatibility alias `GET /api/v1/rfp/events`, plus legacy mounts `/rfp/notifications/stream` and `/rfp/events`) using FastAPI `Depends(get_current_user)` backed by `OAuth2PasswordBearer` (`Authorization: Bearer <token>`). Invalid, missing, or expired tokens are rejected with HTTP `401 Unauthorized` (or `403 Forbidden` for inactive users) before starting `StreamingResponse`.
  - **Keep-Alive Heartbeats**: The SSE async generator uses `asyncio.wait_for(queue.get(), timeout=heartbeat_interval)` with a default `heartbeat_interval` of `15.0` seconds (overridable via query/config in tests) to yield `: keep-alive\n\n` SSE comment frames during idle periods.
  - **Frontend Authenticated Client**: Because the browser's native `EventSource` API does not support custom `Authorization: Bearer <token>` headers, `uis/backoffice` will use a dedicated streaming client hook/service (`useRFPNotifications` + `connectRFPNotificationStream`) built on `fetch()` with `Authorization: Bearer ${getToken()}`, `Accept: text/event-stream`, `Last-Event-ID` header support, and a `ReadableStreamDefaultReader` line-buffered SSE parser.
- **Rationale**:
  - Passing JWTs in URL query strings leaks credentials into server access logs, proxy logs, and browser history, violating Constitution Principle IV (Zero PII & Credential Leakage). Using `fetch()` with `ReadableStream` keeps the JWT strictly inside the `Authorization` HTTP header while supporting full SSE frame parsing (`id:`, `event:`, `data:`, and `: keep-alive` comments).
- **Alternatives Considered**:
  - Native `EventSource` with `?token=<jwt>` query param: Rejected due to Constitution Principle IV security guardrails against logging bearer tokens in URLs.

---

### 1.5 Reconnection Backoff, Hybrid Missed-Ticket Recovery & Deduplication

- **Decision**:
  - **Exponential Backoff**: When the stream closes unexpectedly or encounters a network/5xx error, the frontend schedules a reconnect using exponential backoff: `min(1000 * 2^attempt, 30000)` ms (`1s, 2s, 4s, 8s, 16s, 30s`). Upon a successful stream handshake and event receipt, the attempt counter resets to `0`. If the server responds with HTTP `401` or `403`, reconnection halts immediately and surfaces an authentication error state.
  - **Hybrid Missed-Ticket Recovery**:
    1. **Primary (SSE Replay)**: Every broadcast event is assigned a monotonically increasing integer ID (`1, 2, 3, ...`) and stored in the broadcaster's bounded ring buffer (`maxlen=256`). On reconnect, the client sends the last seen event ID in the `Last-Event-ID` request header (and optional `last_event_id` query parameter). The server immediately replays all buffered events with `int(event.id) > int(last_event_id)` before streaming live events.
    2. **Fallback (REST Reconciliation)**: Whenever the client reconnects after a disconnect (or if the server restarted and its in-memory buffer reset), the client also triggers a background reconciliation call to `GET /api/v1/rfp/tickets?limit=50` and merges any tickets not yet present in dashboard state.
  - **Deduplication**:
    - Both the broadcaster ring buffer and the frontend state manager deduplicate tickets using a `Map<string, ...>` / `Set<string>` keyed by canonical `ticket_id` (and `rfp_id`), guaranteeing that a ticket delivered via live SSE, `Last-Event-ID` replay, and REST reconciliation is rendered and highlighted at most once.
- **Rationale**:
  - Satisfies FR-010, FR-011, FR-012, SC-003, and SC-004 with defense-in-depth: fast in-memory replay handles brief network blips in milliseconds, while REST reconciliation guarantees zero missed tickets even if the backend process restarted during the outage.
- **Alternatives Considered**:
  - Client-only polling fallback: Rejected because polling adds continuous load; event-driven reconciliation triggered only on reconnect is deterministic and lightweight.
