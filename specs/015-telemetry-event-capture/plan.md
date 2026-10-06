# Implementation Plan: Telemetry Event Capture

**Branch**: `015-telemetry-event-capture` | **Date**: 2026-10-06 | **Spec**: [specs/015-telemetry-event-capture/spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/015-telemetry-event-capture/spec.md)

**Input**: Feature specification from `specs/015-telemetry-event-capture/spec.md`

---

## Summary

Implement the client-side `TelemetryService` in the Next.js Backoffice (`uis/backoffice/app/services/telemetry.ts`) featuring local queue buffering, 10s / 20-event batching & debouncing, tab-exit flush via `navigator.sendBeacon`, exponential backoff retries (up to 3 attempts), and a single public `track()` entrypoint with automatic standard envelope enrichment (`eventId`, `sessionId`, `userId`, `timestamp`, `schemaVersion`, `requestId`). Provide a FastAPI stub ingestion endpoint `POST /telemetry/events` in `services/api/routers/telemetry.py` validating the `TelemetryBatch` envelope contract via Pydantic and returning HTTP 200 with `{ "received": N }`. Broadly instrument cross-cutting technical metrics (uncaught errors, API latencies, section navigation) and mandatory business operations (warehouse inventory flows) adhering strictly to `docs/telemetry/event-schemas.json` without PII.

---

## Technical Context

**Language/Version**: TypeScript 5.9 (Frontend) / Python 3.14 (Backend)  
**Primary Dependencies**: Next.js 14.2, React 18.3, FastAPI, Pydantic v2  
**Storage**: In-memory FIFO queue buffer on frontend; transient logging / validation gateway on backend (analytical database sink in subsequent phases)  
**Testing**: Jest + ts-jest (Frontend unit tests), Pytest + TestClient (Backend endpoint tests)  
**Target Platform**: Node.js / Modern Evergreen Browsers (Chrome, Edge, Firefox, Safari) & Linux/Windows server runtimes  
**Project Type**: Web Application Frontend (`uis/backoffice`) + REST API Service (`services/api`)  
**Performance Goals**: Sub-50ms backend validation & response time; 80%+ reduction in client HTTP requests via batching; zero UI blocking or main thread lag during event capture  
**Constraints**: Zero PII transmission; strict TypeScript typing without `any` annotations; strict allowlist schema enforcement (`additionalProperties: false`); non-blocking fire-and-forget telemetry  
**Scale/Scope**: ~70 active warehouse operators across 2 fulfillment hubs (LA & Zaragoza), capturing up to 10k events/day with 20-event micro-batches  

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Requirement | Status | Verification Notes |
| :--- | :--- | :--- | :--- |
| **I. Clean Architecture & Isolation** | Telemetry logic must be encapsulated in dedicated service module (`telemetry.ts`) without scattered fetch calls. | **PASS** | Centralized in `uis/backoffice/app/services/telemetry.ts` and `services/api/routers/telemetry.py`. |
| **II. Strict TypeScript Typing** | Comply with `strict: true`, zero `any`, explicit return types, and explicit type imports. | **PASS** | Strong typing using `Record<string, unknown>`, typed event interfaces, and JSDoc documentation. |
| **III. Contract & Schema Integrity** | Envelope and event payloads must match `docs/telemetry/event-schemas.json` and `telemetry-plan.md`. | **PASS** | Formally defined in `data-model.md`, `contracts/telemetry-api.yaml`, and Pydantic models. |
| **IV. Privacy & Zero PII** | Zero customer names, unhashed emails, or passwords in telemetry streams. | **PASS** | Strict schema validation; only allowlisted entity IDs and operational metrics are accepted. |
| **V. Test-First & Resilience** | Independent testability of queue, debouncing, backoff, and ingestion validation. | **PASS** | Comprehensive unit & contract tests planned for both backend router and frontend service. |

---

## Project Structure

### Documentation (this feature)

```text
specs/015-telemetry-event-capture/
├── spec.md              # Feature specification
├── plan.md              # Implementation plan (this file)
├── research.md          # Phase 0: Technical decisions & research findings
├── data-model.md        # Phase 1: Entities, payload schemas & lifecycle diagrams
├── quickstart.md        # Phase 1: Verification scenarios & test run guide
├── contracts/           # Phase 1: Interface contracts
│   └── telemetry-api.yaml
└── checklists/
    └── requirements.md  # Quality validation checklist
```

### Source Code Layout

```text
services/api/
├── routers/
│   └── telemetry.py            # Phase 1: FastAPI stub endpoint POST /telemetry/events & Pydantic models
├── main.py                     # Router inclusion & middleware registration
└── tests/
    └── api/
        └── test_telemetry.py   # Unit & contract tests for POST /telemetry/events

uis/backoffice/
├── app/
│   ├── services/
│   │   └── telemetry.ts        # Phase 2: Centralized TelemetryService with local queue, batching, sendBeacon & retries
│   ├── components/
│   │   └── TelemetryProvider.tsx # Global error boundary & route navigation tracking wrapper
│   └── inventory/              # Phase 3: Broad business instrumentation across inventory flows
├── lib/
│   └── api.ts                  # API fetch wrapper instrumented with api_latency_recorded
└── __tests__/
    └── services/
        └── telemetry.test.ts   # Frontend unit tests (batching, debouncing, sendBeacon, retries)
```

**Structure Decision**: Multi-project monorepo layout leveraging existing `services/api` (FastAPI backend) and `uis/backoffice` (Next.js frontend). Telemetry service resides cleanly in `uis/backoffice/app/services/` with global lifecycle listeners hooked into the app layout and shared API client.

---

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
| :--- | :--- | :--- |
| *None* | N/A (Standard architecture conforming fully to monorepo rules) | N/A |
