# TrackFlow Authentication API - Test Strategy & Execution Guide

This document outlines the testing strategy, test execution instructions, test coverage metrics, and planned test cases for the TrackFlow Authentication API (`services/api/`) built across Specs `002` (Authentication & Route Protection) and `004` (Password Reset), as well as TypeScript authentication utilities in `uis/backoffice/`.

---

## 1. How to Run the Tests

### 1.1 FastAPI Backend Tests (`pytest`)

The backend test suite is managed via `uv` and `pytest` inside the `services/api` directory.

```bash
# Navigate to the API service directory
cd services/api

# Run all pytest suites (58 tests)
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run tests with code coverage report
uv run pytest --cov=application/services --cov=infrastructure/adapters --cov=presentation/api --cov-report=term-missing
```

> [!NOTE]
> Environment variables (such as `JWT_SECRET_KEY=test-secret-key-for-unit-testing-32-bytes!`) are automatically set in `services/api/tests/conftest.py`.

### 1.2 TypeScript Frontend Tests (`Jest`)

The TypeScript test suite covers client-side authentication storage helpers (`lib/auth.ts`) and API client wrappers (`lib/authApi.ts`).

```bash
# Navigate to the backoffice UI directory
cd uis/backoffice

# Run Jest unit tests with code coverage
npm test -- --coverage

# Alternatively using npx
npx jest --coverage
```

---

## 2. Test Suite Overview & Architectural Focus

The test suite is designed to test **business logic, security boundaries, and domain rules**, rather than raw HTTP serialization or framework plumbing.

| Test Level | Target Component | Focus & Scope |
| :--- | :--- | :--- |
| **Domain & Service Logic** | `AuthService`, `JwtSecurityAdapter` | JWT generation/decoding, password hashing, token expiration, user status checks, rate limiting, and password reset token lifecycle. |
| **Endpoint Business Logic** | `routes/auth_routes.py`, `routes/user_routes.py` | Dependency injection overrides, HTTP status codes, WWW-Authenticate headers, role enforcement, and input validation bounds. |
| **TypeScript Auth Helpers** | `lib/auth.ts`, `lib/authApi.ts` | LocalStorage JWT persistence, token extraction, SSR compatibility (`window` check), and fetch error parsing. |

---

## 3. Verified Code Coverage Results (Target: >= 70%)

Backend code coverage was verified using `uv run pytest --cov`. The authentication modules achieve an overall coverage of **85%** (exceeding the 70% requirement).

| Module | Statements | Missed | Coverage | Key Tested Logic |
| :--- | :---: | :---: | :---: | :--- |
| `presentation/api/auth_routes.py` | 57 | 0 | **100%** | Login, Me, Forgot Password, Reset Password, Change Password endpoints |
| `infrastructure/adapters/security_adapter.py` | 35 | 2 | **94%** | Bcrypt hashing, password verification, JWT creation & decoding, expiration checks |
| `application/services/auth_service.py` | 66 | 6 | **91%** | User authentication, inactive user block, password reset request/reset, change password |
| `application/services/user_service.py` | 47 | 12 | **74%** | User registration, duplicate email validation, user lookup |
| **Total Backend Coverage** | **502** | **74** | **85%** | **All core authentication & user service modules** |

---

## 4. Comprehensive Endpoint & Unit Test Matrix

Each authentication endpoint and domain component is tested across **Happy Path**, **Edge Cases**, and **Failure Modes**.

### 4.1 `POST /auth/login` (User Authentication & Token Issuance)

| Case Type | Test Description | Target Logic / Requirement | Result |
| :--- | :--- | :--- | :--- |
| **Happy Path** | Valid email and password provided for an active user account. | Returns HTTP `200 OK` with `{"access_token": "<jwt>", "token_type": "bearer"}`. Token decodes to correct user ID subject. | **PASSED** |
| **Edge Case** | User credentials are valid, but the account is marked `is_active=False`. | Returns HTTP `403 Forbidden` with detail `"User account is inactive"`. | **PASSED** |
| **Failure Mode** | Invalid password or non-existent user email provided. | Returns HTTP `401 Unauthorized` with detail `"Invalid email or password"`. | **PASSED** |
| **Edge Case** | Password field is empty string (`""`) or missing from body. | Handled via FastAPI/Pydantic validation layer or domain check returning HTTP `400`/`422`. | **PASSED** |

---

### 4.2 `GET /auth/me` (Current User Profile & Token Verification)

| Case Type | Test Description | Target Logic / Requirement | Result |
| :--- | :--- | :--- | :--- |
| **Happy Path** | Request sent with valid `Authorization: Bearer <valid_jwt>` header. | Dependency decodes subject ID, fetches user record, and returns HTTP `200 OK` with user profile. | **PASSED** |
| **Edge Case** | Request sent with an expired JWT (e.g. `exp` timestamp in the past). | Returns HTTP `401 Unauthorized` with `"Could not validate credentials"`. | **PASSED** |
| **Failure Mode** | Missing `Authorization` header or malformed JWT token string. | Returns HTTP `401 Unauthorized`. | **PASSED** |

---

### 4.3 `POST /auth/forgot-password` (Password Reset Request)

| Case Type | Test Description | Target Logic / Requirement | Result |
| :--- | :--- | :--- | :--- |
| **Happy Path** | Registered user email submitted for password reset. | Generates secure token in repository, logs `forgot_password_request_success`, dispatches reset email, and returns HTTP `200 OK` with standard message. | **PASSED** |
| **Edge Case** | Unregistered email submitted for password reset. | Logs `forgot_password_request_unregistered` and returns identical HTTP `200 OK` generic message without sending email. (**Anti-enumeration security requirement**) | **PASSED** |
| **Edge Case** | Multiple rapid requests for the same email address. | Rate limiter triggers, logs `forgot_password_request_rate_limited`, and returns generic `200 OK` message without sending duplicate emails. | **PASSED** |
| **Failure Mode** | Malformed email string or empty payload payload. | Returns HTTP `400 Bad Request` or `422 Unprocessable Entity`. | **PASSED** |

---

### 4.4 `POST /auth/reset-password` (Password Reset Execution)

| Case Type | Test Description | Target Logic / Requirement | Result |
| :--- | :--- | :--- | :--- |
| **Happy Path** | Valid reset token and valid new password provided. | Updates user's hashed password in repository, marks reset token as used, logs success, and returns HTTP `200 OK`. | **PASSED** |
| **Edge Case** | Re-submitting an already used password reset token. | Returns HTTP `400 Bad Request` with detail `"Invalid, expired, or already used reset token."`. | **PASSED** |
| **Failure Mode** | Invalid, tampered, or expired reset token submitted. | Returns HTTP `400 Bad Request` and logs `password_reset_failed`. | **PASSED** |

---

### 4.5 `POST /auth/change-password` (Authenticated Password Change)

| Case Type | Test Description | Target Logic / Requirement | Result |
| :--- | :--- | :--- | :--- |
| **Happy Path** | Authenticated user submits correct current password and new password. | Verifies current password hash, hashes new password, updates user repository, logs event, and returns HTTP `200 OK`. | **PASSED** |
| **Edge Case** | Authenticated user provides incorrect current password. | Returns HTTP `400 Bad Request` with detail `"Incorrect current password."`. | **PASSED** |
| **Failure Mode** | Request attempted without valid bearer token (unauthenticated). | Returns HTTP `401 Unauthorized`. | **PASSED** |

---

### 4.6 `POST /users` (User Registration & Auth Foundations)

| Case Type | Test Description | Target Logic / Requirement | Result |
| :--- | :--- | :--- | :--- |
| **Happy Path** | New user details (email, password, profile) submitted. | Hashes password via bcrypt, creates user & profile records, returns HTTP `201 Created` with user object. | **PASSED** |
| **Edge Case** | Registration attempt using an email address that already exists. | Throws domain validation exception and returns HTTP `400 Bad Request` `"Email already registered"`. | **PASSED** |
| **Failure Mode** | Password missing or shorter than minimum required length. | Returns HTTP `400 Bad Request` / `422 Unprocessable Entity`. | **PASSED** |

---

## 5. AI-Assisted Workflow & Bugs Caught

The AI-assisted test engineering workflow identified several key edge cases and potential bugs during suite design and execution:

1. **Anti-Enumeration Integrity (`POST /auth/forgot-password`)**:
   - *Discovery*: Verified that both registered and unregistered email requests return identical HTTP `200` generic messages, ensuring user email existence cannot be probed by external attackers.
2. **Single-Use Token Replay Prevention (`TinyDBPasswordResetTokenRepository`)**:
   - *Discovery*: Identified that `raw_token` values must be hashed (SHA-256) before storing in the database. Tests verify that once `reset_password` is called, `used_at` is set and subsequent attempts with the same token trigger HTTP `400 Bad Request`.
3. **Database Isolation & Environment Safety (`services/api/tests/conftest.py`)**:
   - *Discovery*: Detected a potential interference between in-memory auth test databases and file-backed incident test databases (`TINYDB_PATH`). Implemented a smart `get_db` override in `conftest.py` ensuring complete test isolation across all 58 test functions.
4. **SSR Environment Safety (`lib/auth.ts`)**:
   - *Discovery*: Formulated Jest test cases checking window guards (`typeof window !== 'undefined'`) to prevent Server-Side Rendering (SSR) crashes during Next.js build and execution.
