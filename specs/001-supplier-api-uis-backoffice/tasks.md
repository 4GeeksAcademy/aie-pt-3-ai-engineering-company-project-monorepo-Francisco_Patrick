# Tasks: supplier-api-uis-backoffice

**Input**: Design documents from `/specs/001-supplier-api-uis-backoffice/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project preparation and dependency verification

- [x] T001 Ensure `services/api/routes` directory exists for the new router
- [x] T002 Ensure `uis/backoffice/app/suppliers` and `components` directories exist
- [x] T003 Add `tinydb` and `pydantic` (if missing) to backend dependencies
- [x] T004 [P] Verify existing Next.js and Tailwind configuration in `uis/backoffice/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Implement TinyDB database initialization in `services/api/database.py` (ensure non-destructive to existing states)
- [x] T006 Refactor `services/api/main.py` to support `APIRouter` without modifying existing incident endpoints
- [x] T007 Create Supplier base Pydantic models in `services/api/models.py`
- [x] T008 [P] Add Navigation link to Supplier Directory in existing `uis/backoffice` layout/menu

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Registering a New Carrier/Supplier (Priority: P1) 🎯 MVP

**Goal**: Operations Manager can register new carriers/suppliers into the system.

**Independent Test**: Send POST to `/suppliers` and verify `201/200` with TinyDB ID.

### Implementation for User Story 1

- [x] T009 [US1] Implement `POST /suppliers` endpoint in services/api/routes/suppliers.py
- [x] T010 [US1] Create seed script in services/api/seed.py
- [x] T011 [US1] Register suppliers router in services/api/main.py

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Querying and Filtering Carriers (Priority: P1)

**Goal**: Logistics Coordinator can list all carriers or filter by country/category.

**Independent Test**: GET requests to `/suppliers` with and without query parameters return expected subsets.

### Implementation for User Story 2

- [x] T012 [P] [US2] Implement `GET /suppliers` endpoint in services/api/routes/suppliers.py
- [x] T013 [P] [US2] Implement `GET /suppliers/{id}` endpoint in services/api/routes/suppliers.py

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 4 - Backoffice Supplier Directory (Priority: P1)

**Goal**: Visual directory in backoffice application to manage supplier data.

**Independent Test**: Navigate to `/suppliers` in backoffice UI, view, filter, and interact with the table.

### Implementation for User Story 4

- [x] T014 [US4] Create Supplier directory layout in uis/backoffice/app/suppliers/layout.tsx
- [x] T015 [US4] Create Supplier directory page in uis/backoffice/app/suppliers/page.tsx
- [x] T016 [P] [US4] Implement SupplierTable component in uis/backoffice/components/SupplierTable.tsx
- [x] T017 [P] [US4] Implement SupplierForm component in uis/backoffice/components/SupplierForm.tsx
- [x] T018 [US4] Integrate API calls (fetch and POST) in frontend components

**Checkpoint**: Backoffice directory view and creation works

---

## Phase 6: User Story 3 - Updating Carrier Rates and Status (Priority: P2)

**Goal**: Update rate (`cost_per_kg`) or status (`active/suspended`) for a carrier.

**Independent Test**: PATCH endpoints update the record and refresh `updated_at`.

### Implementation for User Story 3

- [x] T019 [US3] Implement `PATCH /suppliers/{id}/rate` endpoint in services/api/routes/suppliers.py
- [x] T020 [US3] Implement `PATCH /suppliers/{id}/status` endpoint in services/api/routes/suppliers.py
- [x] T021 [US3] Implement `DELETE /suppliers/{id}` endpoint in services/api/routes/suppliers.py
- [x] T022 [US3] Update uis/backoffice/components/SupplierTable.tsx to trigger PATCH API calls

**Checkpoint**: All user stories should now be independently functional

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T023 [P] Verify CORS middleware in `services/api/main.py` covers the new routes
- [x] T024 Test backend with frontend integrated end-to-end (run quickstart.md validation)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### Parallel Opportunities

- Foundational tasks (T005-T008) can largely run in parallel after basic setup.
- US1, US2, and US4 frontend components can be worked on in parallel.

## Implementation Strategy

### MVP First (User Story 1 & 2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational 
3. Complete Phase 3: User Story 1 (POST route)
4. Complete Phase 4: User Story 2 (GET route)
5. **STOP and VALIDATE**: Test Backend Independently

### Incremental Delivery

1. Backend MVP (US1 & US2)
2. Frontend MVP (US4 base list & create)
3. Backend Extensions (US3 PATCH/DELETE)
4. Frontend Extensions (US4 inline updates)
