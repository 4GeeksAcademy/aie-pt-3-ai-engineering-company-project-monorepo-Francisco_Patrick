# Implementation Plan: Real-Time RFP Ticket Notifications (SSE Part 1 of 2)

**Branch**: `034-sse-rfp-notifications` | **Date**: 2026-11-24 | **Spec**: [specs/034-sse-rfp-notifications/spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/034-sse-rfp-notifications/spec.md)

**Input**: Feature specification from `/specs/034-sse-rfp-notifications/spec.md`

---

## Summary

Replace manual dashboard refreshes and polling for new RFP ticket discovery with a real-time Server-Sent Events (SSE) push channel (`GET /api/v1/rfp/notifications/stream`, with legacy `/rfp/notifications/stream` and alias `/api/v1/rfp/events`) that immediately notifies connected commercial backoffice users (Miguel Torres's team) whenever a new RFP ticket enters TrackFlow with initial status `analyzing`.

The technical approach combines:
1. **Backend SSE Broadcaster & Streaming Endpoint (`services/api/`)**: A thread-safe and async-safe in-memory pub/sub broadcaster (`RFPNotificationBroadcaster` implementing `RFPNotificationBroadcasterPort`) with per-client `asyncio.Queue` fan-out, monotonic `id:` sequence numbers, a bounded ring buffer (`maxlen=256`) for `Last-Event-ID` missed-event replay, and periodic `: keep-alive` comment heartbeats every 15 seconds. Protected by backoffice Bearer JWT authentication (`Depends(get_current_user)`).
2. **Dual Non-LLM & Intake Emission Triggers**: Emits named `event: rfp_ticket_created` with a flat JSON payload (`ticket_id`, `rfp_id`, `client_name`, `client_country`, `services_requested`, `status: "analyzing"`, `created_at`) both from a direct non-LLM registration endpoint (`POST /api/v1/rfp/tickets`) and from the existing `RFPIntakePipeline._node_orchestrate` step once a document is classified as a valid RFP and its commercial metadata is extracted. Zero LLM or AI agent calls occur in the notification pipeline.
3. **Frontend Authenticated SSE Client, Progressive Backoff & Hybrid Recovery (`uis/backoffice/`)**: An authenticated `fetch()` + `ReadableStream` SSE consumer (`useRFPNotifications` + `rfpNotificationsClient.ts`) that passes `Authorization: Bearer <token>`, parses W3C SSE frames, prepends newly arrived tickets in real time with a visual highlight badge, reconnects with exponential backoff (`1s, 2s, 4s, 8s, 16s`, capped at `30s`, halting on HTTP `401`/`403`), recovers missed tickets via `Last-Event-ID` replay plus `GET /api/v1/rfp/tickets` fallback reconciliation, and deduplicates strictly by `ticket_id`.

---

## Technical Context

**Language/Version**: Python 3.14 (`services/api/`, `data/pipelines/`), TypeScript 5.9 (`packages/shared/`, `uis/backoffice/`)  
**Primary Dependencies**:
- Backend: `fastapi>=0.141.1` (`StreamingResponse`, `Depends`, `APIRouter`), `sqlmodel>=0.0.42`, `pydantic>=2.13.5`
- Frontend: `next@^14.2.5`, `react@^18.3.1`, native Web Fetch `ReadableStream` API
- Shared Contracts: `@repo/shared-types` (`packages/shared/types/rfp.ts`)  
**Storage**: Existing SQLModel database (`intake_tickets`, `rfp_metadata` tables) for persistent ticket state + bounded in-memory ring buffer (`collections.deque(maxlen=256)`) in `RFPNotificationBroadcaster` for `Last-Event-ID` SSE event replay  
**Testing**: `pytest` (`services/api/tests/test_rfp_sse_notifications.py`), Jest / React Testing Library (`uis/backoffice/__tests__/rfpNotifications.test.ts`), `npm run typecheck`  
**Target Platform**: Linux container / Windows development environment, modern evergreen web browsers  
**Project Type**: Full-Stack Monorepo Web Service (`services/api`) & Next.js Backoffice UI (`uis/backoffice`)  
**Performance Goals**:
- End-to-end notification arrival on connected dashboards in `< 2s` (in-process fan-out `< 10ms`)
- Idle connection preservation via `: keep-alive` comment frame every `15s`
- Backoffice Core Web Vitals maintained (LCP $\le$ 1.0s, TBT $\le$ 200ms, CLS = 0)  
**Constraints**:
- Zero LLM, ML model, or AI agent calls on the notification creation, broadcast, streaming, or test paths (FR-013, SC-005)
- Exact SSE wire format per `docs/real-time-notification/trackflow-BRIEFING.es.md` §3: named `event: rfp_ticket_created` and flat JSON `data:` (no nested `{"event", "data"}` wrapper)
- Strict TypeScript (`strict: true`, zero `any`, explicit return types, JSDoc comments, `import type`)
- Zero JWT leakage in URLs (Bearer token sent strictly via `Authorization` HTTP header)  
**Scale/Scope**: Immediate fan-out for 2 to 50+ concurrent commercial sales users, with documented architectural scaling path from single-process `asyncio.Queue` fan-out to multi-worker Redis Pub/Sub + Streams via `RFPNotificationBroadcasterPort`

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Requirement | Pre-Research Status | Post-Design Status | Verification Mechanism |
|---|---|---|---|---|
| **I. Service Boundaries & Domain Isolation** | Frontends in `uis/`, backend in `services/api/` with hexagonal boundaries (`domain/`, `application/`, `infrastructure/`, `presentation/`), shared DTOs in `packages/shared/`. | **PASSED** | **PASSED** | `RFPNotificationBroadcasterPort` is defined in `services/api/domain/rfp/ports.py`; in-memory adapter lives in `services/api/infrastructure/messaging/rfp_notification_broadcaster.py`; shared DTOs live in `packages/shared/types/rfp.ts`; frontend consumes only HTTP/SSE endpoints. |
| **II. Public API Compatibility & Strict Contract Serialization** | Explicit Pydantic `response_model` / OpenAPI schemas, `Depends` injection, non-blocking async execution, DTO projections, dual `/api/v1/*` and legacy route compatibility. | **PASSED** | **PASSED** | `POST /api/v1/rfp/tickets` declares `response_model=RFPTicketCreatedEventResponse` with ` status_code=201`; SSE stream uses async generator without blocking the event loop; `rfp.router` is dual-mounted at `/api/v1/rfp` and `/rfp`. |
| **III. Strict TypeScript & Static Type Safety** | `strict: true`, zero `any`, no `@ts-ignore`, explicit return types, JSDoc comments, `import type`. | **PASSED** | **PASSED** | `packages/shared/types/rfp.ts`, `uis/backoffice/lib/rfpNotificationsClient.ts`, and `uis/backoffice/hooks/useRFPNotifications.ts` enforce strict typing, zero `any`, and complete JSDoc annotations. |
| **IV. Defensive Error Handling & Zero Sensitive Data Leaks** | Zero raw stack traces in 500s, zero plaintext token/PII leaks in logs or URLs, no swallowed exceptions, resilient UI connection states. | **PASSED** | **PASSED** | Frontend passes Bearer JWT in `Authorization` header (never in URL query string); SSE disconnects surface clear connection badge states and retry backoff / auth failure feedback. |
| **V. Performance-First Architecture & Core Web Vitals** | LCP $\le$ 1.0s, TBT $\le$ 200ms, CLS = 0. Non-blocking SSR hydration. | **PASSED** | **PASSED** | SSE stream initiates asynchronously inside a client `useEffect` after initial render, never blocking SSR or LCP painting, and eliminates wasteful 3-second full-list polling when connected. |
| **VI. Test-First Development & Deterministic Verification Gates** | Automated unit/integration coverage (`pytest`, `jest`, `npm run typecheck`, `npm run build`). | **PASSED** | **PASSED** | Dedicated `pytest` suite (`test_rfp_sse_notifications.py`) and Jest suite (`rfpNotifications.test.ts`) run deterministically with zero external LLM or broker dependencies. |
| **VII. Vector Database & Qdrant SDK Governance** | Encapsulated vector adapters if vector search is used. | **N/A (PASSED)** | **N/A (PASSED)** | Feature operates strictly in the real-time notification layer and makes zero vector store or LLM calls. |

---

## Project Structure

### Documentation (this feature)

```text
specs/034-sse-rfp-notifications/
├── spec.md                                         # Feature specification
├── plan.md                                         # This file (/speckit-plan output)
├── research.md                                     # Phase 0 architectural decisions & trade-offs
├── data-model.md                                   # Phase 1 domain entities, SSE envelope & state machines
├── quickstart.md                                   # Phase 1 runnable validation & verification guide
├── contracts/                                      # Phase 1 API & event contracts
│   ├── sse-rfp-notifications-api.yaml              # OpenAPI 3.1 contract for SSE stream & ticket registration
│   └── rfp-ticket-created-event.schema.json        # JSON Schema for flat rfp_ticket_created SSE payload
└── tasks.md                                        # Phase 2 output (/speckit-tasks command)
```

### Source Code (repository root)

```text
packages/shared/
└── types/
    └── rfp.ts                                      # Extended with RFPTicketCreatedEventDTO, CreateRFPTicketRequestDTO, SSEConnectionStatus, and enriched IntakeTicketSummaryDTO

services/api/
├── domain/
│   └── rfp/
│       ├── entities.py                             # Extended with RFPTicketCreatedEvent and SSEEnvelope value objects
│       └── ports.py                                # Extended with RFPNotificationBroadcasterPort interface
├── infrastructure/
│   └── messaging/
│       ├── __init__.py                             # Messaging package exports
│       └── rfp_notification_broadcaster.py         # Thread-safe/async-safe in-memory SSE broadcaster with bounded ring buffer & Last-Event-ID replay
├── presentation/
│   ├── api/v1/
│   │   └── rfp.py                                  # Added GET /notifications/stream, GET /events alias, POST /tickets, and enriched GET /tickets summary fields
│   ├── dependencies.py                             # Added get_rfp_notification_broadcaster_dep singleton provider
│   └── schemas/
│       └── rfp.py                                  # Added CreateRFPTicketRequest, RFPTicketCreatedEventSchema, and enriched IntakeTicketSummary
└── tests/
    └── test_rfp_sse_notifications.py               # Automated pytest suite for SSE headers, wire framing, auth 401/403, heartbeats, fan-out, replay, and deduplication

data/pipelines/
└── rfp_intake/
    └── rfp_intake_pipeline.py                      # Emits rfp_ticket_created via broadcaster in _node_orchestrate once valid RFP metadata is saved in analyzing state

uis/backoffice/
├── app/
│   └── rfp/
│       └── page.tsx                                # Consumes useRFPNotifications hook, renders real-time arrival badge, live connection status, and deduplicated ticket table
├── components/
│   └── rfp/
│       └── RFPRealtimeNotificationBanner.tsx       # Visual connection status badge and newly arrived real-time RFP toast/banner indicator
├── hooks/
│   └── useRFPNotifications.ts                      # React hook managing SSE lifecycle, exponential backoff, Last-Event-ID replay, REST reconciliation, and ticket_id deduplication
├── lib/
│   └── rfpNotificationsClient.ts                   # Fetch + ReadableStream SSE frame parser, backoff calculator, and ticket deduplication utilities
└── __tests__/
    └── rfpNotifications.test.ts                    # Jest tests for SSE wire parsing, backoff schedule, 401 halt, recovery reconciliation, and ticket_id deduplication

docs/real-time-notification/
└── ARCHITECTURE_NOTES.md                           # Deliverable technical analysis: 2 vs. 50 concurrent users fan-out, hybrid recovery & deduplication, and SSE vs. WebSockets
```

**Structure Decision**: Follows the established TrackFlow monorepo hexagonal layout (`services/api/` for backend domain/infrastructure/presentation, `data/pipelines/rfp_intake/` for intake orchestration emission, `packages/shared/types/rfp.ts` for shared TypeScript contracts, and `uis/backoffice/` for the commercial dashboard frontend).

---

## Complexity Tracking

> **No Constitution violations detected.** All gates pass without exceptions.
