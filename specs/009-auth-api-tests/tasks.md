# Tasks: FastAPI Backend Authentication API Unit Testing

**Input**: Design documents from `/specs/009-auth-api-tests/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test directory structure and environment initialization

- [X] T001 Create test directory structure in services/api/tests/unit/ and services/api/tests/api/
- [X] T002 Verify pytest, pytest-cov, and httpx test dependencies in services/api/pyproject.toml

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared test fixtures and TestClient configuration MUST be complete before endpoint testing begins

- [X] T003 [P] Create mock repository fixtures and test user datasets in services/api/tests/conftest.py
- [X] T004 [P] Configure FastAPI TestClient and dependency override fixtures in services/api/tests/conftest.py

**Checkpoint**: Foundation ready - user story testing can now proceed in parallel

---

## Phase 3: User Story 1 - Authentication API Core Business Logic & Endpoint Test Suite (Priority: P1) 🎯 MVP

**Goal**: Implement unit & endpoint business logic tests for login, profile, password change, and user registration.

**Independent Test**: Execute `uv run pytest services/api/tests/unit/` and `uv run pytest services/api/tests/api/` to verify core login, me, change-password, and registration logic.

### Implementation for User Story 1

- [X] T005 [P] [US1] Unit test JwtSecurityAdapter token creation, expiration, and bcrypt hashing in services/api/tests/unit/test_security_adapter.py
- [X] T006 [P] [US1] Unit test AuthService.authenticate_user credential verification and inactive user lockout in services/api/tests/unit/test_auth_service.py
- [X] T007 [P] [US1] Endpoint business logic tests for POST /auth/login (Happy Path 200, Edge Case inactive user 403 / empty password 400, Failure Mode 401) in services/api/tests/api/test_login_api.py
- [X] T008 [P] [US1] Endpoint business logic tests for GET /auth/me (Happy Path 200, Edge Case expired token 401, Failure Mode missing auth header) in services/api/tests/api/test_me_api.py
- [X] T009 [P] [US1] Endpoint business logic tests for POST /auth/change-password (Happy Path 200, Edge Case wrong current password 400, Failure Mode unauthenticated) in services/api/tests/api/test_change_password_api.py
- [X] T010 [P] [US1] Endpoint business logic tests for POST /users (Happy Path 201, Edge Case duplicate email 400, Failure Mode missing fields) in services/api/tests/api/test_user_registration_api.py

**Checkpoint**: User Story 1 fully functional and testable independently.

---

## Phase 4: User Story 2 - Password Reset & Security Rules Verification (Priority: P2)

**Goal**: Implement tests for anti-enumeration, rate limiting, and single-use password reset tokens.

**Independent Test**: Execute `uv run pytest services/api/tests/api/test_password_reset_api.py`.

### Implementation for User Story 2

- [X] T011 [P] [US2] Unit test AuthService password reset request and token consumption logic in services/api/tests/unit/test_auth_service.py
- [X] T012 [P] [US2] Endpoint tests for POST /auth/forgot-password (Happy Path 200, Edge Case anti-enumeration & rate limiting 200, Failure Mode invalid format) in services/api/tests/api/test_password_reset_api.py
- [X] T013 [US2] Endpoint tests for POST /auth/reset-password (Happy Path 200, Edge Case reused token 400, Failure Mode expired/invalid token) in services/api/tests/api/test_password_reset_api.py

**Checkpoint**: User Stories 1 AND 2 work independently.

---

## Phase 5: User Story 3 - TypeScript Client Auth Helper Unit Testing (Priority: P3)

**Goal**: Implement Jest unit tests for frontend auth utilities in `uis/backoffice/`.

**Independent Test**: Execute `npm test -- --coverage` inside `uis/backoffice/`.

### Implementation for User Story 3

- [X] T014 [P] [US3] Configure Jest test runner in uis/backoffice/package.json and uis/backoffice/jest.config.js
- [X] T015 [P] [US3] Implement Jest tests for lib/auth.ts token storage and SSR window safety in uis/backoffice/__tests__/auth.test.ts
- [X] T016 [P] [US3] Implement Jest tests for lib/authApi.ts fetch wrappers and error detail parsing in uis/backoffice/__tests__/authApi.test.ts

**Checkpoint**: TypeScript client authentication utilities tested with coverage.

---

## Phase 6: User Story 4 - Documentation & AI-Assisted Test Workflow Tracking (Priority: P4)

**Goal**: Complete `TESTING.md` documentation detailing test execution, coverage targets, test matrix, and AI workflow notes.

**Independent Test**: Inspect root `TESTING.md` to ensure all required sections and test case matrices are fully documented.

### Implementation for User Story 4

- [X] T017 [P] [US4] Document test strategy, execution commands, coverage stats, and AI-assisted bug notes in TESTING.md

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final verification, coverage gates, and quickstart validation

- [X] T018 Execute uv run pytest --cov in services/api/ and confirm >= 70% code coverage
- [X] T019 Execute npm test -- --coverage in uis/backoffice/ and confirm 100% test pass rate
- [X] T020 Run end-to-end quickstart validation guide in specs/009-auth-api-tests/quickstart.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Can start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Stories (Phase 3+)**: Depend on Foundational completion.
- **Polish (Phase 7)**: Depends on completion of User Stories 1-4.

### Parallel Opportunities

- T003 and T004 in Foundational phase can run in parallel.
- All unit and endpoint test tasks T005, T006, T007, T008, T009, T010 (US1) can run in parallel.
- TypeScript Jest test tasks T014, T015, T016 (US3) can run in parallel.

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Run `uv run pytest` on US1 modules.

### Incremental Delivery

1. Setup + Foundational -> Core test fixtures ready
2. Add US1 -> Validate login, profile, change password, and registration
3. Add US2 -> Validate password reset & anti-enumeration
4. Add US3 -> Validate TypeScript auth helpers
5. Add US4 -> Finalize TESTING.md & verify 70%+ coverage gate
