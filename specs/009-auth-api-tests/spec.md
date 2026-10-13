# Feature Specification: FastAPI Backend Authentication API Unit Testing

**Feature Branch**: `009-auth-api-tests`

**Created**: 2026-09-13

**Status**: Draft

**Input**: User description: "You are a senior software engineer testing the FastAPI Backend Authentication endpoints. Your task is to add a comprehensive battery of unit tests to the authentication API (`services/api/`) you built in the previous specs `002` AND `004`. Scope: Test suite must cover all endpoints in the authentication API; Each endpoint must have at minimum: one happy-path test, one edge-case test, and one failure-mode test; Use pytest for the FastAPI backend and Jest for any TypeScript logic; Tests must pass cleanly with uv run pytest and jest --coverage; Do not test HTTP serialisation — test the logic. Deliverable: A working test suite committed alongside the existing API code, with a brief TESTING.md explaining how to run it. Acceptance Criteria: A TESTING.md file is present; uv run pytest runs without errors; Test coverage on auth module at or above 70%; Tests assert business logic; Jest tests present if TS utilities exist; AI-assisted workflow documented in TESTING.md."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Authentication API Core Business Logic & Endpoint Test Suite (Priority: P1)

As a backend developer maintaining the TrackFlow Authentication API, I need a comprehensive suite of unit tests for all authentication endpoints (`/auth/login`, `/auth/me`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/change-password`, `/users`) and domain services (`AuthService`, `JwtSecurityAdapter`) so that regression issues, security flaws, and edge cases are automatically caught without testing HTTP plumbing or framework serialization.

**Why this priority**: Core security and authentication endpoints protect the entire platform. Ensuring 70%+ coverage and zero compiler/runtime test failures is critical for build integrity and system reliability.

**Independent Test**: Can be independently verified by running `uv run pytest` from `services/api/` and validating that all authentication endpoint test modules pass cleanly with code coverage at or above 70%.

**Acceptance Scenarios**:

1. **Given** valid active user credentials, **When** submitting `POST /auth/login`, **Then** return HTTP 200 with a signed JWT bearer access token.
2. **Given** invalid user credentials or non-existent email, **When** submitting `POST /auth/login`, **Then** raise `AuthenticationError` and return HTTP 401 Unauthorized with generic error messaging.
3. **Given** an inactive user account (`is_active=False`), **When** attempting login or accessing `/auth/me`, **Then** block access with HTTP 403 Forbidden.
4. **Given** a valid bearer token, **When** requesting `GET /auth/me`, **Then** return current user profile payload.
5. **Given** an expired or malformed token, **When** requesting `GET /auth/me`, **Then** reject with HTTP 401 Unauthorized and `WWW-Authenticate: Bearer` header.

---

### User Story 2 - Password Reset & Security Rules Verification (Priority: P2)

As a security engineer, I need unit test cases verifying anti-enumeration, rate-limiting, and single-use reset token logic so that password reset workflows (`/auth/forgot-password` and `/auth/reset-password`) strictly adhere to security specifications.

**Why this priority**: Password reset mechanisms are primary targets for account takeover attacks (probing valid emails, token replay attacks). Testing business logic prevents security vulnerabilities.

**Independent Test**: Can be tested by running `uv run pytest` targeting `test_forgot_password` and `test_reset_password` scenarios, asserting that unregistered email requests return identical generic success messages and reused tokens are rejected.

**Acceptance Scenarios**:

1. **Given** a registered user email, **When** requesting `POST /auth/forgot-password`, **Then** create a 30-minute reset token, log audit event, send reset email, and return HTTP 200 generic message.
2. **Given** an unregistered email address, **When** requesting `POST /auth/forgot-password`, **Then** return identical HTTP 200 generic message without throwing an error or sending an email (anti-enumeration).
3. **Given** a valid, unexpired reset token and new password, **When** submitting `POST /auth/reset-password`, **Then** update hashed password in storage, mark token as used, and return HTTP 200 success.
4. **Given** an already used reset token, **When** submitting `POST /auth/reset-password`, **Then** reject with HTTP 400 Bad Request.

---

### User Story 3 - TypeScript Client Auth Helper Unit Testing (Priority: P3)

As a frontend developer, I need unit tests for client-side authentication utilities (`lib/auth.ts` and `lib/authApi.ts`) in `uis/backoffice/` using Jest so that token storage, token retrieval, SSR environment safety, and API response error handling are verified.

**Why this priority**: Client-side authentication persistence and API wrapper functions must handle token storage safely and parse backend error responses consistently.

**Independent Test**: Can be independently verified by executing `npm test -- --coverage` or `npx jest --coverage` in `uis/backoffice/` and confirming clean test pass with code coverage.

**Acceptance Scenarios**:

1. **Given** a valid token string, **When** calling `setToken`, **Then** persist token in `localStorage` and ensure `isAuthenticated()` returns `true`.
2. **Given** an existing token, **When** calling `removeToken`, **Then** clear token from `localStorage` and ensure `isAuthenticated()` returns `false`.
3. **Given** a non-OK HTTP response from `/auth/*` endpoints, **When** executing `requestPasswordReset` or `changePassword`, **Then** throw meaningful Error containing backend error detail.

---

### User Story 4 - Documentation & AI-Assisted Test Workflow Tracking (Priority: P4)

As a team lead, I need a comprehensive `TESTING.md` document at the project root explaining how to run backend and frontend test suites, listing planned test cases (Happy Path, Edge Case, Failure Mode) per endpoint, documenting code coverage results (>= 70%), and recording AI-assisted test discovery/bug catching notes.

**Why this priority**: Provides maintainability and clear onboarding instructions for developers to run tests and verify business logic compliance.

**Independent Test**: Can be verified by inspecting root `TESTING.md` for complete coverage matrix, test execution commands, coverage verification steps, and AI-assisted workflow documentation.

**Acceptance Scenarios**:

1. **Given** the workspace root, **When** checking for `TESTING.md`, **Then** confirm file presence with test run instructions (`uv run pytest`, `jest --coverage`), endpoint matrix, and minimum 70% backend coverage section.

---

### Edge Cases

- What happens when a user attempts password reset with an expired token? (System must reject with HTTP 400 Bad Request and log `password_reset_failed`).
- What happens when password fields are empty strings or contain whitespace? (System must fail validation or return HTTP 400/422 without unhandled server exceptions).
- What happens when `localStorage` is accessed in a Server-Side Rendering (SSR) context (`window === undefined`)? (TypeScript helper must handle undefined window gracefully without throwing exceptions).
- What happens when multiple rapid password reset requests are initiated for the same email? (Rate-limiter triggers, returning generic success response while suppressing duplicate emails).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Test suite MUST cover all authentication API endpoints (`/auth/login`, `/auth/me`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/change-password`, `/users`).
- **FR-002**: Every authentication endpoint MUST have at minimum one Happy Path test, one Edge Case test, and one Failure Mode test.
- **FR-003**: Test suite MUST assert business logic and domain rules (credentials validation, token creation/decoding, active status, token consumption, anti-enumeration), rather than HTTP serialization plumbing.
- **FR-004**: FastAPI backend test suite MUST pass cleanly using `uv run pytest` from `services/api/` (or project root).
- **FR-005**: Backend test suite MUST achieve at least 70% code coverage across the authentication module (`services/api/application/services/auth_service.py`, `infrastructure/adapters/security_adapter.py`, `presentation/api/auth_routes.py`, `presentation/api/user_routes.py`).
- **FR-006**: Client-side TypeScript authentication utilities (`lib/auth.ts`, `lib/authApi.ts`) MUST have corresponding Jest unit tests passing with `jest --coverage`.
- **FR-007**: A `TESTING.md` file MUST be maintained at project root detailing how to execute tests, test suite coverage strategy, test case matrix, coverage results, and AI-assisted workflow notes (documenting cases identified or bugs caught).
- **FR-008**: Test functions MUST be clearly named (e.g. `test_login_happy_path_returns_jwt_token`, `test_login_inactive_user_forbidden`, `test_forgot_password_anti_enumeration_unregistered_email`) and include descriptive docstrings explaining assertion rationale.

### Key Entities *(include if feature involves data)*

- **AuthService Test Double / Fixture**: Isolated domain service fixture configured with TinyDB in-memory or mock repositories for reproducible test execution.
- **Test User Credentials**: Standard test user dataset containing active users, inactive users, admin users, and password hash credentials.
- **Password Reset Token Record**: In-memory reset token document tracking `raw_token`, `user_id`, `expires_at`, and `is_used` state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of authentication API endpoints (`/auth/login`, `/auth/me`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/change-password`, `/users`) have verified happy-path, edge-case, and failure-mode test coverage.
- **SC-002**: Backend test suite (`uv run pytest`) achieves at least 70% line coverage on authentication modules without failing tests or unhandled warnings.
- **SC-003**: Frontend Jest test suite (`npm test -- --coverage`) passes 100% of tests for `lib/auth.ts` and `lib/authApi.ts`.
- **SC-004**: `TESTING.md` exists at project root, documenting execution commands, complete test case matrices, coverage stats, and AI-assisted test engineering notes.

## Assumptions

- Target backend environment uses Python >=3.14 with `pytest`, `pytest-cov`, `httpx`, and `fastapi.testclient`.
- Target frontend environment uses Node.js and Jest for running TypeScript tests in `uis/backoffice/`.
- In-memory TinyDB or test repository instances will be used to ensure test isolation and fast execution.
