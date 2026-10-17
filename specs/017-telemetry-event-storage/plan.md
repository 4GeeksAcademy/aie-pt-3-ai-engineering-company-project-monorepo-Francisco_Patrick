# Implementation Plan: Telemetry Event Storage

**Branch**: `017-telemetry-event-storage` | **Date**: 2026-10-15 | **Spec**: [specs/017-telemetry-event-storage/spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/017-telemetry-event-storage/spec.md)

**Input**: Feature specification from `specs/017-telemetry-event-storage/spec.md`

---

## Summary

Replace the temporary stub logging sink in FastAPI with real persistent relational storage using SQLModel and Supabase PostgreSQL (with automatic resilient fallback to local SQLite). The ingestion endpoint (`POST /telemetry/events` and canonical alias `/api/v1/telemetry/events`) will accept batch envelopes flexibly, validate each event item individually against the domain `TelemetryEvent` model, commit valid events to the immutable `telemetry_events` table in a single atomic bulk transaction, and return a comprehensive receipt `{ "received": N, "stored": M, "rejected": R }` with HTTP 200 OK. This ensures 100% backward compatibility with existing frontend clients while preventing malformed items from dropping an entire batch of operational insights.

---

## Technical Context

**Language/Version**: Python 3.11+ (running in `services/api/.venv` managed via `uv`)

**Primary Dependencies**: FastAPI, Pydantic v2, SQLModel, SQLAlchemy, psycopg2-binary

**Storage**: Relational database (Supabase PostgreSQL in production, SQLite `inventory.db` / in-memory in local testing/development) via `SQLModelClientManager`. Storage target: immutable, append-only `telemetry_events` table.

**Testing**: `pytest` test runner with FastAPI `TestClient`, SQLModel in-memory/isolated sessions, and unit/integration coverage.

**Target Platform**: Linux container (Docker) / Windows development host.

**Project Type**: Monorepo Web Service (`services/api/`).

**Performance Goals**: Batch ingestion processing completes in under 200ms for batches containing up to 50 events (SC-002).

**Constraints**:
- Strict HTTP backward compatibility: HTTP 200 OK returned for all evaluated batches.
- Receipt invariant: `received = stored + rejected` across 100% of processed requests.
- Single atomic bulk insert transaction for all valid events in a batch.
- Write-only immutability: zero `UPDATE` or `DELETE` operations permitted on `telemetry_events`.
- Zero PII logged; internal warnings for rejected events must sanitize and mask sensitive data.
- Envelope structural errors (e.g. missing `events` field or non-list payload) return HTTP 422 Unprocessable Entity.

**Scale/Scope**: High-volume telemetry stream supporting frontends (`uis/backoffice`) and future service producers, handling batches up to 100 events per request.

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Monorepo Requirement | Plan Compliance Status | Notes |
|---|---|---|---|
| **I. Service Boundaries & Domain Isolation** | Monorepo boundaries strictly preserved. Frontends never access DB files directly; backend maintains hexagonal layers (`domain/`, `application/`, `infrastructure/`, `presentation/`). | **PASS** | Domain entities in `domain/telemetry/`, application service in `application/telemetry/`, SQLModel persistence adapter in `infrastructure/persistence/sqlmodel/`, router in `presentation/api/v1/telemetry.py`. |
| **II. Public API Compatibility & Strict Contract Serialization** | 100% of FastAPI endpoints declare explicit Pydantic `response_model`, typed bodies, and status codes. No internal models leaked. | **PASS** | Endpoint returns `response_model=IngestReceipt` with explicit status `200 OK`. `received` attribute is preserved for backward compatibility; `stored` and `rejected` added. |
| **III. Strict TypeScript & Static Type Safety** | Strict compiler flags, zero `any`, explicit return types and JSDoc annotations across TypeScript code. | **PASS** | Monorepo TypeScript frontends (`uis/backoffice/app/services/telemetry.ts`) remain 100% compatible without breaking types. Python backend enforces strict type annotations. |
| **IV. Defensive Error Handling & Zero Sensitive Data Leaks** | Zero raw stack traces exposed in HTTP responses. Zero PII/credentials logged. No swallowed failures. | **PASS** | Malformed individual events are counted as `rejected` with diagnostic warnings logged internally. Database transaction failures roll back cleanly and return sanitized 500 errors. |
| **V. Performance-First Architecture** | Latency and throughput standards. Zero unnecessary overhead. | **PASS** | Valid events are inserted in a single atomic bulk operation (`session.add_all()` / `session.commit()`), easily meeting the <200ms target for 50 events. |
| **VI. Test-First Development & Deterministic Verification Gates** | Unit and integration coverage for critical paths. Deterministic seeding and zero regression gates. | **PASS** | Comprehensive pytest coverage for valid batches, partial batches, empty batches, all-rejected batches, and envelope schema violations. |

**Gate Status**: **PASSED** (Zero architectural violations, zero unjustified exceptions).

---

## Project Structure

### Documentation (this feature)

```text
specs/017-telemetry-event-storage/
├── spec.md              # Feature specification
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   └── telemetry-api.yaml
└── checklists/
    └── requirements.md  # Quality checklist
```

### Source Code (repository root)

```text
services/api/
├── domain/
│   └── telemetry/
│       ├── models.py           # TelemetryEvent, IngestReceipt, RawTelemetryBatch
│       └── ports.py            # TelemetrySinkPort (record_events)
├── application/
│   └── telemetry/
│       └── telemetry_service.py # TelemetryService orchestrating per-item validation & bulk dispatch
├── infrastructure/
│   └── persistence/
│       └── sqlmodel/
│           ├── models.py       # TelemetryEventRecord SQLModel table
│           ├── client.py       # init_db schema initialization & engine
│           └── telemetry_sink.py # SQLModelTelemetrySink implementing TelemetrySinkPort
├── presentation/
│   ├── dependencies.py         # Wire SQLModelTelemetrySink into get_telemetry_service_dep
│   └── api/
│       └── v1/
│           └── telemetry.py    # POST /events endpoint with RawTelemetryBatch & IngestReceipt
└── tests/
    ├── api/
    │   └── test_telemetry.py   # API integration tests (partial validation, receipts, 200 OK)
    └── unit/
        ├── test_domain_models.py # TelemetryEvent & IngestReceipt validation tests
        └── test_application_services.py # TelemetryService & sink unit tests
```

**Structure Decision**: Fully adheres to the established Hexagonal Architecture in `services/api/`. Extends domain models and ports, implements a driven SQLModel sink adapter under `infrastructure/persistence/sqlmodel/`, wires dependencies via `presentation/dependencies.py`, and preserves presentation routing at `presentation/api/v1/telemetry.py` (mounted at both `/telemetry` and `/api/v1/telemetry`).

---

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*No violations detected. Zero entries required.*
