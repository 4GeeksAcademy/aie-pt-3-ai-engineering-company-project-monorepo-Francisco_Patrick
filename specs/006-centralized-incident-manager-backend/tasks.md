# Tasks: Centralized Incident Manager - Backend

**Input**: Design documents from `/specs/006-centralized-incident-manager-backend/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/management-api.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verification of shared imports and module layout

- [x] T001 [P] Verify domain exceptions module `services/api/domain/exceptions.py`
- [x] T002 [P] Verify incident schemas in `services/api/domain/schemas/incident_schema.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core exception mapping and repository search capabilities

- [x] T003 [P] Add `InvalidStatusTransitionError` and `IncidentNotFoundError` in `services/api/domain/exceptions.py`
- [x] T004 [P] Extend repository search and 4-dimension summary in `services/api/infrastructure/adapters/tiny_db_incident_repository.py`
- [x] T005 Register exception handlers for domain errors in `services/api/main.py`

---

## Phase 3: User Story 1 - Incident Lifecycle & Status State Machine (Priority: P1) 🎯 MVP

**Goal**: Implement status lifecycle transition rules (`open` -> `in_progress`/`discarded`, `in_progress` -> `resolved`/`discarded`, terminal: `resolved`/`discarded`) and `PATCH /api/incidents/{id}/status`.

**Independent Test**: Transitioning `open` -> `in_progress` succeeds; attempting `open` -> `resolved` or `resolved` -> `open` returns HTTP 400.

- [x] T006 [P] [US1] Add status transition validation logic to `domain/incident_model.py`
- [x] T007 [US1] Implement `update_incident_status` method in `services/api/application/services/incident_service.py`
- [x] T008 [US1] Create route handler `PATCH /api/incidents/{id}/status` in `services/api/presentation/api/incident_routes.py`
- [x] T009 [P] [US1] Add automated tests for status lifecycle transitions in `services/api/tests/test_incident_status_lifecycle.py`

---

## Phase 4: User Story 2 - Incident Creation & Field Validation (Priority: P2)

**Goal**: Enforce field validations on `POST /api/incidents` returning HTTP 400 JSON identifying problematic fields.

**Independent Test**: Valid creation payload returns HTTP 201; invalid payload with missing/blank fields returns HTTP 400 specifying field name.

- [x] T010 [P] [US2] Update `IncidentCreateSchema` validation rules in `services/api/domain/schemas/incident_schema.py`
- [x] T011 [US2] Wire creation route `POST /api/incidents` returning HTTP 201 in `services/api/presentation/api/incident_routes.py`
- [x] T012 [P] [US2] Add automated validation tests for HTTP 400 error payloads in `services/api/tests/test_incident_creation_api.py`

---

## Phase 5: User Story 3 - Filtering, Detail Lookup & Operational Summary (Priority: P3)

**Goal**: Expose `GET /api/incidents` with filters (`status`, `origin`, `branch`, `category`), `GET /api/incidents/{id}` (404 on missing), and 4-dimension `GET /api/incidents/summary` resilient on empty DB.

**Independent Test**: Filtering returns matching subsets; `GET /api/incidents/nonexistent` returns HTTP 404; `/summary` returns 4-dimension metric maps on empty and seeded DBs.

- [x] T013 [P] [US3] Implement multi-attribute repository filtering (`status`, `origin`, `branch`, `category`) in `services/api/infrastructure/adapters/tiny_db_incident_repository.py`
- [x] T014 [US3] Implement 4-dimension summary counts (`by_status`, `by_category`, `by_origin`, `by_branch`) in `services/api/infrastructure/adapters/tiny_db_incident_repository.py`
- [x] T015 [US3] Implement detail lookup and list filtering in `services/api/application/services/incident_service.py`
- [x] T016 [US3] Wire route handlers `GET /api/incidents`, `GET /api/incidents/{id}`, and `GET /api/incidents/summary` in `services/api/presentation/api/incident_routes.py`
- [x] T017 [P] [US3] Add automated tests for list filtering, detail 404, and empty database summary in `services/api/tests/test_incident_management_api.py`

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verification and complete test suite pass

- [x] T018 Execute full quickstart verification steps in `specs/006-centralized-incident-manager-backend/quickstart.md`
- [x] T019 [P] Run full pytest suite across `services/api/tests` verifying 100% pass rate

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational phase completion. (MVP Goal)
- **User Story 2 (Phase 4)**: Depends on Foundational phase completion.
- **User Story 3 (Phase 5)**: Depends on Foundational phase completion.
- **Polish (Phase 6)**: Depends on all User Stories being complete.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Setup (Phase 1) & Foundational (Phase 2)
2. Implement User Story 1 (Status Lifecycle State Machine & `PATCH /api/incidents/{id}/status`)
3. Validate state transitions independently

### Incremental Delivery

1. Deliver Status Lifecycle State Machine (US1 - MVP)
2. Deliver Enhanced Incident Creation & Field Validation (US2)
3. Deliver Multi-attribute Filtering, Detail Lookup & 4-Dimension Summary (US3)
4. Execute Quickstart & Full Test Suite (Polish)
