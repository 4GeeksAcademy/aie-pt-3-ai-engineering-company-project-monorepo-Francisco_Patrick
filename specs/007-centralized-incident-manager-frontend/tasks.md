# Tasks: Centralized Incident Manager - Frontend

**Input**: Design documents from `/specs/007-centralized-incident-manager-frontend/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/management-ui.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Export shared TypeScript interfaces and validation logic in `packages/shared/` for monorepo consumption.

- [x] T001 [P] Export incident TypeScript interfaces and types in `packages/shared/types/incidents.ts`
- [x] T002 [P] Implement client-side incident validation rules in `packages/shared/validation/incidents.ts`
- [x] T003 Re-export incident types and validation modules in `packages/shared/types/index.ts` and `packages/shared/index.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: API client network layer and shared branch selection UI component

- [x] T004 Create incident API HTTP client with plain-language error mapping in `uis/backoffice/lib/api/incidents.ts`
- [x] T005 [P] Create reusable `BranchSelect` dropdown component with context labels in `uis/backoffice/components/incidents/BranchSelect.tsx`

---

## Phase 3: User Story 1 - Incident Registration Form & Client Validation (Priority: P1) 🎯 MVP

**Goal**: Implement client-validated incident registration page with visual branch highlighting when `origin === 'branch'`, submit loading state, user-friendly error messages, and form reset on success.

**Independent Test**: Navigate to `/incidents/register`, submit empty form to verify client-side validation warnings; select `origin = branch` to verify highlight; submit valid form to verify submit loading state and success reset.

- [x] T006 [US1] Implement `IncidentRegistrationForm` component with validation, visual branch highlight, and submit spinner in `uis/backoffice/components/incidents/IncidentRegistrationForm.tsx`
- [x] T007 [US1] Create Incident Registration page route in `uis/backoffice/app/incidents/register/page.tsx`
- [x] T008 [P] [US1] Add Incident Registration link to main navigation menu in `uis/backoffice/components/Navigation.tsx`

---

## Phase 4: User Story 2 - Incident List Panel & Inline Status Updates (Priority: P2)

**Goal**: Implement incident listing panel with `status`, `origin`, and `branch` filters, loading/empty/error states with retry option, and inline status update dropdown with visual rollback on API error.

**Independent Test**: Navigate to `/incidents`, test filter controls; trigger status change to invalid transition (e.g., `open` -> `resolved`) to verify error alert and visual status dropdown rollback.

- [x] T009 [US2] Implement `IncidentListPanel` component with multi-attribute filters, loading/empty/error states, and inline status rollback in `uis/backoffice/components/incidents/IncidentListPanel.tsx`

---

## Phase 5: User Story 3 - Operational Summary Metrics Panel (Priority: P3)

**Goal**: Render 4-dimension operational metrics summary panel (`by_status`, `by_category`, `by_origin`, `by_branch`) resilient to API slow loads or 500 errors.

**Independent Test**: Load `/incidents` dashboard, verify 4-dimension summary cards render; simulate API 500 on `/summary` to verify isolated error container without breaking incident list.

- [x] T010 [US3] Implement `IncidentSummaryPanel` component rendering 4-dimension metrics (`by_status`, `by_category`, `by_origin`, `by_branch`) with isolated loading skeleton and error retry boundary in `uis/backoffice/components/incidents/IncidentSummaryPanel.tsx`
- [x] T011 [US3] Assemble Incident Dashboard page combining `IncidentSummaryPanel` and `IncidentListPanel` in `uis/backoffice/app/incidents/page.tsx`

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verification and complete build health pass

- [x] T012 Execute quickstart validation scenarios in `specs/007-centralized-incident-manager-frontend/quickstart.md`
- [x] T013 [P] Run Next.js build and TypeScript typecheck (`npm run build`) in `uis/backoffice` verifying 0 compiler errors

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
2. Implement User Story 1 (Registration form, client validation, navigation link)
3. Validate registration form end-to-end independently

### Incremental Delivery

1. Deliver Incident Registration Form & Client Validation (US1 - MVP)
2. Deliver Resilient Incident List Panel & Inline Status Updates (US2)
3. Deliver Operational Summary Metrics Panel & Dashboard (US3)
4. Execute Quickstart scenarios & Build Check (Polish)
