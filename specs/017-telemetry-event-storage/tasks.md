# Tasks: Telemetry Event Storage

**Input**: Design documents from `specs/017-telemetry-event-storage/`
**Prerequisites**: [plan.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/017-telemetry-event-storage/plan.md), [spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/017-telemetry-event-storage/spec.md), [data-model.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/017-telemetry-event-storage/data-model.md), [contracts/telemetry-api.yaml](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/017-telemetry-event-storage/contracts/telemetry-api.yaml), [research.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/017-telemetry-event-storage/research.md), [quickstart.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/017-telemetry-event-storage/quickstart.md)

## Format: `- [ ] [ID] [P?] [Story] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (`[US1]`, `[US2]`, `[US3]`, `[US4]`)
- Every task includes an exact file path

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify dependencies and database connection environment for telemetry storage

- [X] T001 Verify backend dependency specifications including SQLModel, Pydantic, and database drivers in `services/api/pyproject.toml`
- [X] T002 [P] Verify relational database connection configuration and local SQLite fallback resolution in `services/api/infrastructure/persistence/sqlmodel/client.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core domain models, port interfaces, ORM entities, and database sink infrastructure that MUST be completed before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this foundational phase is complete.

- [X] T003 [P] Extend `IngestReceipt` with `stored` and `rejected` counter fields and define `RawTelemetryBatch` in `services/api/domain/telemetry/models.py`
- [X] T004 [P] Update `TelemetrySinkPort` with `record_events` method for bulk persistence in `services/api/domain/telemetry/ports.py`
- [X] T005 [P] Create `TelemetryEventRecord` SQLModel table entity with UUID primary key, indexed timestamp/session/user/type/request, and cross-dialect JSON properties in `services/api/infrastructure/persistence/sqlmodel/models.py`
- [X] T006 Wire `TelemetryEventRecord` into schema initialization in `services/api/infrastructure/persistence/sqlmodel/client.py`
- [X] T007 Implement `SQLModelTelemetrySink` implementing `TelemetrySinkPort` with atomic bulk insert and write-only immutability in `services/api/infrastructure/persistence/sqlmodel/telemetry_sink.py`
- [X] T008 Update `get_telemetry_service_dep` to wire `SQLModelTelemetrySink` into `TelemetryService` in `services/api/presentation/dependencies.py`

**Checkpoint**: Foundation ready — User Story implementation can now proceed.

---

## Phase 3: User Story 1 - Fault-Tolerant Telemetry Ingestion with Partial Batch Persistence (Priority: P1) 🎯 MVP

**Goal**: Ingest batches of telemetry events, individually validate each event against `TelemetryEvent`, commit all valid events in a single atomic bulk transaction, and return receipt with `received`, `stored`, and `rejected`.

**Independent Test**: Submit a mixed batch containing 3 valid events and 2 malformed events to `POST /telemetry/events`. Verify HTTP 200 OK with `{ "received": 5, "stored": 3, "rejected": 2 }` and confirm only the 3 valid events are persisted to the database.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T009 [P] [US1] Unit tests for `RawTelemetryBatch` accepting raw dictionaries and `IngestReceipt` default counts in `services/api/tests/unit/test_domain_models.py`
- [X] T010 [P] [US1] Unit tests for `TelemetryService` per-item validation isolating malformed items and invoking sink for valid items in `services/api/tests/unit/test_application_services.py`
- [X] T011 [P] [US1] API integration test for mixed batch ingestion returning HTTP 200 OK with `{ "received": 5, "stored": 3, "rejected": 2 }` in `services/api/tests/api/test_telemetry.py`
- [X] T012 [P] [US1] API integration test for 100% malformed batch committing zero database writes and returning `{ "received": N, "stored": 0, "rejected": N }` in `services/api/tests/api/test_telemetry.py`

### Implementation for User Story 1

- [X] T013 [US1] Implement per-item validation loop and bulk sink invocation in `services/api/application/telemetry/telemetry_service.py`
- [X] T014 [US1] Update `LoggingTelemetrySink` to implement `record_events` in `services/api/application/telemetry/telemetry_service.py`
- [X] T015 [US1] Update ingestion route handler to accept `RawTelemetryBatch` and return `IngestReceipt` in `services/api/presentation/api/v1/telemetry.py`

**Checkpoint**: User Story 1 is functional and testable independently (MVP ready!).

---

## Phase 4: User Story 2 - Seamless Integration with Existing Frontend Telemetry Clients (Priority: P1)

**Goal**: Maintain 100% backward compatibility for existing frontend clients (`uis/backoffice`), guaranteeing HTTP 200 OK for evaluated batches, `/api/v1/telemetry/events` alias, and proper HTTP 422 for malformed outer envelopes.

**Independent Test**: Dispatch batches from `uis/backoffice/app/services/telemetry.ts` (and via TestClient), verifying HTTP 200 OK without triggering client retry loops, empty batch handling, and HTTP 422 for envelope schema violations.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T016 [P] [US2] API test confirming empty batch `{"events": []}` returns HTTP 200 OK with `{ "received": 0, "stored": 0, "rejected": 0 }` in `services/api/tests/api/test_telemetry.py`
- [X] T017 [P] [US2] API test confirming missing `events` field or non-list payload returns HTTP 422 Unprocessable Entity in `services/api/tests/api/test_telemetry.py`
- [X] T018 [P] [US2] API test confirming canonical alias `/api/v1/telemetry/events` shares identical behavior with `/telemetry/events` in `services/api/tests/api/test_telemetry.py`

### Implementation for User Story 2

- [X] T019 [US2] Enforce outer envelope strict validation rules (`extra="forbid"`, non-null `events: List[Dict[str, Any]]`) in `services/api/domain/telemetry/models.py`
- [X] T020 [US2] Verify client payload compatibility and response handling against frontend contract in `uis/backoffice/app/services/telemetry.ts`

**Checkpoint**: User Stories 1 and 2 operate in harmony with full frontend backward compatibility.

---

## Phase 5: User Story 3 - End-to-End Operational Traceability & Audit Verification (Priority: P2)

**Goal**: Persist business events (`inbound_order_created`, `stock_exit_recorded`) and technical observability events (`auth_login_failed`, `frontend_error_captured`) immutably in `telemetry_events` table with exact taxonomies, ISO UTC timestamps, session ID, user ID, request ID, and structured JSON properties. Table is append-only with zero update/delete capabilities.

**Independent Test**: Execute inbound order, outbound order, and technical error workflows, query `telemetry_events` directly, and verify three distinct records exist with matching `event_type`, ISO UTC `timestamp`, and properties payload.

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T021 [P] [US3] Integration test verifying persistent database storage and direct query retrieval of business and technical event records in `services/api/tests/api/test_telemetry_persistence.py`
- [X] T022 [P] [US3] Immutability test asserting `SQLModelTelemetrySink` and domain ports provide no `UPDATE` or `DELETE` capabilities in `services/api/tests/api/test_telemetry_persistence.py`

### Implementation for User Story 3

- [X] T023 [US3] Ensure `TelemetryEventRecord` mappings correctly serialize cross-dialect JSON properties and timezone-aware UTC datetimes in `services/api/infrastructure/persistence/sqlmodel/models.py`
- [X] T024 [US3] Ensure `SQLModelTelemetrySink.record_events()` atomically maps and commits all domain attributes to `telemetry_events` in `services/api/infrastructure/persistence/sqlmodel/telemetry_sink.py`

**Checkpoint**: Operational traceability and immutable audit logs are fully queryable and verified.

---

## Phase 6: User Story 4 - Granular Ingestion Diagnostics for Data Quality Monitoring (Priority: P2)

**Goal**: Guarantee the invariant `received = stored + rejected` across 100% of processed requests, and record sanitized internal diagnostic logs (with zero PII or credential leaks) when events are rejected.

**Independent Test**: Submit automated requests with known valid/invalid distributions, verify response receipt invariant holds, and check that internal logs contain masked diagnostic info with no raw PII.

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T025 [P] [US4] Unit test asserting `received == stored + rejected` invariant validation in `services/api/tests/unit/test_domain_models.py`
- [X] T026 [P] [US4] Unit test verifying internal warning logging upon event rejection with PII masking and zero credential leakage in `services/api/tests/unit/test_application_services.py`

### Implementation for User Story 4

- [X] T027 [US4] Add `@model_validator(mode="after")` enforcing `received == stored + rejected` on `IngestReceipt` in `services/api/domain/telemetry/models.py`
- [X] T028 [US4] Implement sanitized warning logger in `TelemetryService` reporting event index and validation error without leaking sensitive properties in `services/api/application/telemetry/telemetry_service.py`

**Checkpoint**: Ingestion receipt invariants and security-hardened diagnostics are validated.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Monorepo build and test validation, automated verification gates, and quickstart scenario execution

- [X] T029 [P] Update database seed or startup validation to ensure `telemetry_events` table exists in `services/api/seed.py`
- [X] T030 Execute full backend test suite (`pytest`) across all unit and API suites in `services/api/tests/`
- [X] T031 Execute quickstart validation scenarios covering mixed batches and direct database inspection in `specs/017-telemetry-event-storage/quickstart.md`
- [X] T032 [P] Verify TypeScript frontend typecheck (`npm run typecheck`) to confirm zero regressions in `uis/backoffice`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately.
- **Foundational (Phase 2)**: Depends on Setup (Phase 1) — **BLOCKS all user stories**.
- **User Story 1 (Phase 3)**: Depends on Foundational (Phase 2).
- **User Story 2 (Phase 4)**: Depends on Foundational (Phase 2) and User Story 1 (Phase 3).
- **User Story 3 (Phase 5)**: Depends on Foundational (Phase 2) and User Story 1 (Phase 3).
- **User Story 4 (Phase 6)**: Depends on User Story 1 (Phase 3).
- **Polish (Phase 7)**: Depends on completion of all desired user stories.

### User Story Dependencies

- **User Story 1 (P1)**: Can start as soon as Foundational (Phase 2) completes. No dependency on other stories.
- **User Story 2 (P1)**: Extends US1 endpoint by verifying client compatibility, empty batch handling, and error codes.
- **User Story 3 (P2)**: Extends US1 persistence by verifying audit domain queries and immutability.
- **User Story 4 (P2)**: Builds upon US1 receipt and service logic to add strict invariant enforcement and sanitized diagnostics.

### Within Each User Story

1. Write tests FIRST and confirm failure before implementation.
2. Models and ports before service logic.
3. Service logic before endpoint handlers.
4. Verify independent test criteria at phase checkpoint.

---

## Parallel Opportunities

- **Phase 1**: T001 and T002 can run in parallel.
- **Phase 2**: T003, T004, and T005 can be implemented in parallel across domain and infrastructure models.
- **Phase 3 (US1 Tests)**: T009, T010, T011, and T012 can all be written in parallel.
- **Phase 4 (US2 Tests)**: T016, T017, and T018 can run in parallel.
- **Phase 5 (US3 Tests)**: T021 and T022 can run in parallel.
- **Phase 6 (US4 Tests)**: T025 and T026 can run in parallel.
- **Phase 7 (Polish)**: T029 and T032 can run in parallel.

---

## Parallel Execution Examples

### User Story 1 Tests

```bash
# Launch test creation for User Story 1 in parallel:
Task: "T009 [P] [US1] Unit tests for RawTelemetryBatch in services/api/tests/unit/test_domain_models.py"
Task: "T010 [P] [US1] Unit tests for TelemetryService in services/api/tests/unit/test_application_services.py"
Task: "T011 [P] [US1] API integration test for mixed batch in services/api/tests/api/test_telemetry.py"
Task: "T012 [P] [US1] API integration test for malformed batch in services/api/tests/api/test_telemetry.py"
```

### Foundational Phase Models & Adapters

```bash
# Implement foundational abstractions across layers in parallel:
Task: "T003 [P] Extend IngestReceipt and define RawTelemetryBatch in services/api/domain/telemetry/models.py"
Task: "T004 [P] Update TelemetrySinkPort in services/api/domain/telemetry/ports.py"
Task: "T005 [P] Create TelemetryEventRecord in services/api/infrastructure/persistence/sqlmodel/models.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001 - T002).
2. Complete Phase 2: Foundational (T003 - T008) — **BLOCKS all user stories**.
3. Complete Phase 3: User Story 1 (T009 - T015).
4. **STOP and VALIDATE**: Test User Story 1 independently with mixed batch ingestion.
5. Deploy/demo MVP increment.

### Incremental Delivery

1. Setup + Foundation → Core domain entities, ORM tables, and sink adapter ready.
2. Add User Story 1 → Partial validation and atomic bulk persistence (MVP!).
3. Add User Story 2 → Frontend client compatibility, empty batch handling, HTTP 422 envelope validation.
4. Add User Story 3 → Operational traceability, business/technical event persistence, immutability audit.
5. Add User Story 4 → Strict invariant receipt check, sanitized diagnostic logs.
6. Polish & Quality Gates → Full test suite passes, quickstart verified, TypeScript typecheck clean.
