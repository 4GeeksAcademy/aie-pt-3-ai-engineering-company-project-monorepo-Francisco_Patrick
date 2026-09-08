# Tasks: auth-frontend

**Input**: Design documents from `/specs/003-auth-frontend/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create necessary directories (`lib`, `components`) in `uis/backoffice/src/` if they do not exist

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [ ] T002 [P] Implement token storage utilities (get, set, remove token) in `uis/backoffice/src/lib/auth.ts`
- [ ] T003 [P] Implement centralized fetch wrapper with token injection and 401 handling in `uis/backoffice/src/lib/api.ts` (Reference `contracts/api.md` for global headers)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - User Registration and Login (Priority: P1) 🎯 MVP

**Goal**: Users can create an account and log in using their email and password, gaining access to authenticated views.

**Independent Test**: Can be fully tested by submitting the registration and login forms and verifying that the JWT token is successfully stored in `localStorage`.

### Implementation for User Story 1

- [ ] T004 [P] [US1] Implement login form and API integration in `uis/backoffice/src/app/login/page.tsx` (Must use OAuth2 `application/x-www-form-urlencoded` per `contracts/api.md`)
- [ ] T005 [P] [US1] Implement registration form and API integration in `uis/backoffice/src/app/register/page.tsx` (Must use JSON payload per `contracts/api.md`)

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Protected Routes (Priority: P1)

**Goal**: Unauthenticated users attempting to access protected routes are redirected to the login page.

**Independent Test**: Navigate to a protected route without a token and observe the redirect to `/login`.

### Implementation for User Story 2

- [ ] T006 [US2] Implement `AuthGuard` client component in `uis/backoffice/src/components/AuthGuard.tsx`
- [ ] T007 [US2] Integrate `AuthGuard` to protect the layout in `uis/backoffice/src/app/layout.tsx` (excluding public routes like login/register)

**Checkpoint**: Route protection is active across the backoffice application.

---

## Phase 5: User Story 4 - Logout (Priority: P1)

**Goal**: Users can log out to securely end their session.

**Independent Test**: Click logout and verify the token is removed and the user is redirected to `/login`.

### Implementation for User Story 4

- [ ] T008 [US4] Add a logout button/action that uses the `removeToken` utility and redirects to `/login`. Update `uis/backoffice/src/app/layout.tsx` or the relevant navigation component.

**Checkpoint**: Logout flow is fully functional.

---

## Phase 6: User Story 3 - Account Management and Profile Edit (Priority: P2)

**Goal**: Authenticated users can view and edit their profile information.

**Independent Test**: Log in, navigate to `/account/profile`, and update profile fields successfully.

### Implementation for User Story 3

- [ ] T009 [US3] Implement profile view and edit form in `uis/backoffice/src/app/account/profile/page.tsx` (Uses `GET /auth/me` and `PUT /profiles/me` per `contracts/api.md`)

**Checkpoint**: All user stories are independently functional.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T010 Run quickstart.md validation to ensure all scenarios pass.
- [ ] T011 Verify UI styling is consistent with Tailwind CSS conventions.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup completion
- **User Stories (Phase 3+)**: Depend on Foundational phase completion
- **Polish (Final Phase)**: Depends on all user stories being complete

### Parallel Opportunities

- T002 and T003 can be worked on in parallel.
- T004 and T005 can be worked on in parallel.

## Implementation Strategy

### Incremental Delivery

1. Complete Foundational utilities (API and Auth).
2. Add Registration and Login (US1). Ensure payload formats adhere to `contracts/api.md`.
3. Add Route Protection (US2).
4. Add Logout (US4).
5. Add Profile Editing (US3). Ensure payload formats adhere to `contracts/api.md`.
