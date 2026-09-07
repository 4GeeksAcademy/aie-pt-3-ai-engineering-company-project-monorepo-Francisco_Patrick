# Tasks: Auth & Route Protection

**Input**: Design documents from `/specs/002-auth-and-route-protection/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create project structure directories under `services/api/` (domain, application, infrastructure, presentation).
- [X] T002 Update `requirements.txt` or `pyproject.toml` with `python-jose[cryptography]` and `libpass[bcrypt]`.

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

- [X] T003 Implement TinyDB connection setup in `services/api/infrastructure/database.py`.
- [X] T004 Define domain exceptions in `services/api/domain/exceptions.py`.
- [X] T005 [P] Define Security and Repository port interfaces in `services/api/domain/ports.py`.
- [X] T006 Implement JWT and hashing security adapter in `services/api/infrastructure/adapters/security_adapter.py`. (Ensure it crashes at startup if JWT secret is missing).
- [X] T007 Implement TinyDB base repository adapter in `services/api/infrastructure/adapters/tiny_db_repository.py`.
- [X] T008 Scaffold FastAPI app and wiring in `services/api/main.py`.

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel.

## Phase 3: User Story 1 - User Registration and Profile Creation (Priority: P1) 🎯 MVP

**Goal**: Users can register for a new account by providing their email and password, along with optional profile information. The system creates a user and linked profile.

**Independent Test**: Can be tested via POST `/users`. Calling the endpoint with valid credentials creates a user and profile in the database.

### Implementation for User Story 1

- [X] T009 [P] [US1] Create User and Profile domain entities in `services/api/domain/models.py`. Include validation for 8-char password minimum.
- [X] T010 [US1] Implement UserService in `services/api/application/services/user_service.py` to handle registration logic. Enforce default role 'user' and `is_active=True`.
- [X] T011 [US1] Implement POST `/users` endpoint in `services/api/presentation/api/user_routes.py`.
- [X] T012 [US1] Wire user routes into FastAPI app in `services/api/main.py`.

**Checkpoint**: User Registration is fully functional and testable independently.

## Phase 4: User Story 2 - User Login (Priority: P1)

**Goal**: Users can log in with their email and password to receive a JWT token for accessing protected resources.

**Independent Test**: Can be tested via POST `/auth/login`. Providing valid credentials returns a signed JWT token containing the user's ID.

### Implementation for User Story 2

- [X] T013 [P] [US2] Implement AuthService in `services/api/application/services/auth_service.py` for credential validation and token generation. Must explicitly reject if `is_active=False`.
- [X] T014 [US2] Implement POST `/auth/login` endpoint in `services/api/presentation/api/auth_routes.py`. Must explicitly use FastAPI `OAuth2PasswordBearer` and accept `application/x-www-form-urlencoded`.
- [X] T015 [US2] Wire auth routes into FastAPI app in `services/api/main.py`.

**Checkpoint**: User Login works independently and returns valid JWTs.

## Phase 5: User Story 3 - Accessing Protected Resources (Priority: P1)

**Goal**: Authenticated users can access their own protected data and use protected endpoints by including their JWT token.

**Independent Test**: Can be tested by calling GET `/auth/me` or GET `/profiles/me` with and without a valid token.

### Implementation for User Story 3

- [X] T016 [US3] Implement `get_current_user` dependency in `services/api/presentation/dependencies.py`. Must explicitly reject token if user is not found or `is_active=False`.
- [X] T017 [US3] Implement ProfileService in `services/api/application/services/profile_service.py` for retrieving profile data.
- [X] T018 [US3] Implement GET `/auth/me` endpoint in `services/api/presentation/api/auth_routes.py`.
- [X] T019 [US3] Implement GET `/profiles/me` and PUT `/profiles/me` endpoints in `services/api/presentation/api/profile_routes.py`.
- [X] T020 [US3] Wire profile routes into FastAPI app in `services/api/main.py`.
- [X] T021 [US3] Apply `get_current_user` to at least 5 existing sensitive routes outside `/users` and `/auth`.

**Checkpoint**: Protected resources are secured, and authenticated users can access their profile data.

## Phase 6: User Story 4 - Admin Managing Users (Priority: P2)

**Goal**: Admin users can list, view, and manage all users in the system, including updating roles or deleting accounts.

**Independent Test**: Can be tested by calling GET `/users`, PUT `/users/{id}`, and DELETE `/users/{id}` with an admin user's token.

### Implementation for User Story 4

- [X] T022 [US4] Expand UserService in `services/api/application/services/user_service.py` to handle list, get, update, and delete logic.
- [X] T023 [US4] Implement GET `/users`, GET `/users/{id}`, PUT `/users/{id}`, and DELETE `/users/{id}` in `services/api/presentation/api/user_routes.py`.
- [X] T024 [US4] Add role-based authorization checks to these endpoints (e.g., using `get_current_admin_user` or directly checking the role in the route).

**Checkpoint**: All user stories are independently functional.

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T025 [P] Create automated tests for auth and users in `services/api/tests/api/test_auth.py` and `test_users.py`.
- [X] T026 [P] Create automated tests for profiles in `services/api/tests/api/test_profiles.py`.
- [ ] T027 Run quickstart.md validation manually to ensure full end-to-end functionality.

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Can start immediately.
- **Foundational (Phase 2)**: Depends on Setup. BLOCKS all user stories.
- **User Stories (Phase 3+)**: Depend on Foundational.
- **Polish (Final Phase)**: Depends on completion of User Stories.

### User Story Dependencies

- **User Story 1 (P1)**: Registration. No dependencies.
- **User Story 2 (P1)**: Login. Technically depends on US1 to have a user to log in with.
- **User Story 3 (P1)**: Protected Routes. Depends on US2 to get a token.
- **User Story 4 (P2)**: Admin actions. Depends on US1/US2/US3 to manage users effectively.

### Parallel Opportunities

- Port definitions (T005), entity creation (T009), and tests (T025, T026) can be parallelized since they don't depend on implementation details in other files.

## Implementation Strategy

### MVP First (User Stories 1 & 2 & 3)

1. Complete Phase 1 and Phase 2.
2. Complete Phase 3 (Registration).
3. Complete Phase 4 (Login).
4. Complete Phase 5 (Protected Routes).
5. **STOP and VALIDATE**: Validate the full auth flow manually.
