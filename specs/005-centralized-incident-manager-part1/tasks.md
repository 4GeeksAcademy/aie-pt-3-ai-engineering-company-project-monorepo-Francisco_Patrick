# Tasks: Centralized Incident Manager - Part I

**Input**: Design documents from `/specs/005-centralized-incident-manager-part1/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/incidents-api.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project layout setup and shared module preparation

- [ ] T001 [P] Ensure shared package directory `shared/incidents` exists with `shared/incidents/__init__.py`
- [ ] T002 [P] Configure environment setup and verify dependencies in `services/api/requirements.txt`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Data model definitions, repository adapters, and database wiring

- [ ] T003 [P] Define Incident domain entity and enum types in `services/api/domain/models/incident.py`
- [ ] T004 Define TinyDB database initialization and incidents table getter in `services/api/infrastructure/database.py`
- [ ] T005 Create TinyDB Incident Repository adapter in `services/api/infrastructure/adapters/tiny_db_incident_repository.py`
- [ ] T006 Configure centralized JSON exception middleware for FastAPI in `services/api/main.py`

---

## Phase 3: User Story 1 - Historical Data Seeding (Priority: P1) 🎯 MVP

**Goal**: Extract shared CSV validation/transformation routines and implement the idempotent CLI seeding script (`scripts/seed_incidents.py`).

**Independent Test**: Running `python scripts/seed_incidents.py scripts/incidents-COMPANY.csv` loads valid historical records into TinyDB with origin `"customer"`. Running it twice inserts 0 duplicate records.

- [ ] T007 [P] [US1] Extract CSV transformation and validation helpers into `shared/analyzer/engine.py`
- [ ] T008 [US1] Implement CLI historical seed script with CSV-to-Model transformation in `scripts/seed_incidents.py`
- [ ] T009 [US1] Add idempotency logic checking existing `legacy_id` in `scripts/seed_incidents.py`
- [ ] T010 [US1] Add invalid row reporting and terminal summary outputs in `scripts/seed_incidents.py`
- [ ] T011 [P] [US1] Add unit and idempotency tests for seeding script in `services/api/tests/test_seed_incidents.py`

---

## Phase 4: User Story 2 - Incident Data Integrity & Constraints (Priority: P2)

**Goal**: Enforce field validations (`title`, `description`, `category`, `status`, `origin`, `branch`) and allowed enum restrictions.

**Independent Test**: Submitting incomplete or invalid incident objects fails validation with clean, structured error responses.

- [ ] T012 [P] [US2] Implement Pydantic input schemas and validation rules in `services/api/domain/schemas/incident_schema.py`
- [ ] T013 [US2] Implement Incident application service for record validation in `services/api/application/services/incident_service.py`
- [ ] T014 [P] [US2] Add unit tests for validation rules and allowed enum sets in `services/api/tests/test_incident_validation.py`

---

## Phase 5: User Story 3 - Operational Incident Summary & Metrics (Priority: P3)

**Goal**: Expose `GET /api/incidents/summary` endpoint returning totals grouped by `status` and `category`.

**Independent Test**: `GET /api/incidents/summary` returns counts by status and category matching expected transformed historical figures.

- [ ] T015 [US3] Implement summary aggregation logic in `services/api/application/services/incident_service.py`
- [ ] T016 [US3] Create API route handler for `GET /api/incidents/summary` in `services/api/routes/incidents.py`
- [ ] T017 [US3] Register incident router in FastAPI main application in `services/api/main.py`
- [ ] T018 [P] [US3] Add API integration tests for summary endpoint in `services/api/tests/test_incident_summary_api.py`

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end verification and documentation check

- [ ] T019 Execute full quickstart verification steps documented in `specs/005-centralized-incident-manager-part1/quickstart.md`
- [ ] T020 [P] Verify zero raw unhandled stack traces are returned on error conditions in `services/api/main.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational phase completion. (MVP Goal)
- **User Story 2 (Phase 4)**: Depends on Foundational phase completion.
- **User Story 3 (Phase 5)**: Depends on Foundational phase and User Story 1 (requires seeded database records to verify totals).
- **Polish (Phase 6)**: Depends on all User Stories being complete.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup (Phase 1) & Foundational (Phase 2)
2. Implement User Story 1 (`scripts/seed_incidents.py` and shared validation)
3. Validate seed script idempotency independently using `scripts/incidents-COMPANY.csv`

### Incremental Delivery

1. Deliver Seeding CLI & Data Model (US1 - MVP)
2. Add Domain Validation Schemas & Service Constraints (US2)
3. Expose Summary API Endpoint `GET /api/incidents/summary` (US3)
4. Execute Quickstart Validation & Error Handling Check (Polish)
