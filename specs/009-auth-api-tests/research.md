# Phase 0 Research: FastAPI Backend Authentication API Unit Testing

**Feature**: `009-auth-api-tests`  
**Date**: 2026-09-13

## Technical Decisions & Rationale

### 1. Test Framework & Runner Choice
- **Decision**: Use `pytest` with `pytest-cov` and `httpx` / `fastapi.testclient.TestClient` for Python backend testing in `services/api/`, and `Jest` with `@types/jest` and `ts-jest` for TypeScript client utilities in `uis/backoffice/`.
- **Rationale**: Meets project requirements for FastAPI API test execution via `uv run pytest` and TypeScript test execution via `jest --coverage`.
- **Alternatives Considered**: Standard `unittest` (rejected due to lack of fixture ecosystem and `uv` integration ease).

### 2. Isolation Strategy for Backend Endpoint & Service Logic
- **Decision**: Override FastAPI dependencies (`get_user_service_dep`, `get_auth_service_dep`, `get_security_adapter_dep`) and database instances with in-memory TinyDB / mock objects during test runs.
- **Rationale**: Isolates domain and endpoint logic from persistent file system side effects, guaranteeing fast, non-flaky test execution.
- **Alternatives Considered**: File system TinyDB (rejected due to state leakage between test runs).

### 3. Test Structure & Module Layout
- **Decision**:
  - Python tests under `services/api/tests/`:
    - `unit/test_security_adapter.py`: Tests `JwtSecurityAdapter` (token generation, expiration, bcrypt hashing/verification).
    - `unit/test_auth_service.py`: Tests `AuthService` logic (credentials authentication, inactive status check, password reset request/anti-enumeration, password reset execution, password change).
    - `api/test_login_api.py`: Tests `POST /auth/login` (Happy Path, Edge Case: inactive account & empty password, Failure Mode: invalid credentials).
    - `api/test_me_api.py`: Tests `GET /auth/me` (Happy Path: valid bearer token, Edge Case: expired token, Failure Mode: missing auth header).
    - `api/test_password_reset_api.py`: Tests `POST /auth/forgot-password` and `POST /auth/reset-password` (Happy Path, Edge Case: anti-enumeration & rate limiting, Failure Mode: malformed/expired reset token).
    - `api/test_change_password_api.py`: Tests `POST /auth/change-password` (Happy Path, Edge Case: wrong current password, Failure Mode: unauthenticated).
    - `api/test_user_registration_api.py`: Tests `POST /users` (Happy Path, Edge Case: duplicate email, Failure Mode: missing password/fields).
  - TypeScript tests under `uis/backoffice/__tests__/`:
    - `auth.test.ts`: Tests `lib/auth.ts` (`setToken`, `getToken`, `removeToken`, `isAuthenticated`, SSR window safety).
    - `authApi.test.ts`: Tests `lib/authApi.ts` (`requestPasswordReset`, `resetPassword`, `changePassword` error handling).

### 4. Code Coverage Metric Target (>= 70%)
- **Decision**: Configure pytest coverage via `uv run pytest --cov=application/services --cov=infrastructure/adapters --cov=presentation/api`.
- **Rationale**: Satisfies the 70%+ coverage acceptance criterion on core authentication modules.

### 5. Documenting AI-Assisted Workflow & Bugs Caught
- **Decision**: Explicitly record caught bugs (e.g. anti-enumeration generic messaging preservation and SSR undefined window handling) in `TESTING.md`.
