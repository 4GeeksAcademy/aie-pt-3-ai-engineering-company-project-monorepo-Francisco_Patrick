# TrackFlow Authentication API - Test Strategy & Execution Guide

This document outlines the testing strategy, test execution instructions, and planned test cases for the TrackFlow Authentication API (`services/api/`) built across Specs `002` (Authentication & Route Protection) and `004` (Password Reset), as well as TypeScript authentication utilities in `uis/backoffice/`.

---

## 1. How to Run the Tests

### 1.1 FastAPI Backend Tests (`pytest`)

The backend test suite is managed via `uv` and `pytest` inside the `services/api` directory.

```bash
# Navigate to the API service directory
cd services/api

# Run all pytest suites
uv run pytest

# Run tests with verbose output
uv run pytest -v

# Run tests with coverage report
uv run pytest --cov=. --cov-report=term-missing
```

> [!NOTE]
> Ensure environment variables (such as `JWT_SECRET_KEY=test-secret-key`) are set or loaded from `.env.example` when executing tests outside `uv`.

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

## 3. Comprehensive Endpoint & Unit Test Matrix

Each authentication endpoint and domain component is tested across **Happy Path**, **Edge Cases**, and **Failure Modes**.

### 3.1 `POST /auth/login` (User Authentication & Token Issuance)

| Case Type | Test Description | Target Logic / Requirement | Why Included |
| :--- | :--- | :--- | :--- |
| **Happy Path** | Valid email and password provided for an active user account. | Returns HTTP `200 OK` with `{"access_token": "<jwt>", "token_type": "bearer"}`. Token decodes to correct user ID subject. | Validates primary login flow and JWT signature generation. |
| **Edge Case** | User credentials are valid, but the account is marked `is_active=False`. | Returns HTTP `403 Forbidden` with detail `"User account is inactive"`. | Ensures disabled or deactivated users cannot obtain access tokens. |
| **Failure Mode** | Invalid password or non-existent user email provided. | Returns HTTP `401 Unauthorized` with detail `"Invalid email or password"`. | Protects against credential guessing and prevents username enumeration during login. |
| **Edge Case** | Password field is empty string (`""`) or missing from body. | Handled via FastAPI/Pydantic validation layer or domain check returning HTTP `400`/`422`. | Prevents unhandled server exceptions on empty payload fields. |

---

### 3.2 `GET /auth/me` (Current User Profile & Token Verification)

| Case Type | Test Description | Target Logic / Requirement | Why Included |
| :--- | :--- | :--- | :--- |
| **Happy Path** | Request sent with valid `Authorization: Bearer <valid_jwt>` header. | Dependency decodes subject ID, fetches user record, and returns HTTP `200 OK` with user profile. | Confirms active session verification and user profile retrieval. |
| **Edge Case** | Request sent with an expired JWT (e.g. `exp` timestamp in the past). | Returns HTTP `401 Unauthorized` with `"Could not validate credentials"` and `WWW-Authenticate: Bearer` header. | Guarantees expired tokens are strictly rejected. |
| **Failure Mode** | Missing `Authorization` header or malformed JWT token string. | Returns HTTP `401 Unauthorized`. | Enforces route protection on secured endpoints. |

---

### 3.3 `POST /auth/forgot-password` (Password Reset Request)

| Case Type | Test Description | Target Logic / Requirement | Why Included |
| :--- | :--- | :--- | :--- |
| **Happy Path** | Registered user email submitted for password reset. | Generates secure token in repository, logs `forgot_password_request_success`, dispatches reset email, and returns HTTP `200 OK` with standard message. | Validates reset token creation and notification dispatch. |
| **Edge Case** | Unregistered email submitted for password reset. | Logs `forgot_password_request_unregistered` and returns identical HTTP `200 OK` generic message without sending email. | **Anti-enumeration security requirement**: Prevents attackers from probing valid email addresses. |
| **Edge Case** | Multiple rapid requests for the same email address. | Rate limiter triggers, logs `forgot_password_request_rate_limited`, and returns generic `200 OK` message without sending duplicate emails. | Prevents email flooding and denial-of-service abuse. |
| **Failure Mode** | Malformed email string or empty payload payload. | Returns HTTP `400 Bad Request` or `422 Unprocessable Entity`. | Ensures invalid payload formats are rejected before domain processing. |

---

### 3.4 `POST /auth/reset-password` (Password Reset Execution)

| Case Type | Test Description | Target Logic / Requirement | Why Included |
| :--- | :--- | :--- | :--- |
| **Happy Path** | Valid reset token and valid new password provided. | Updates user's hashed password in repository, marks reset token as used, logs success, and returns HTTP `200 OK`. | Confirms successful password updates via reset link. |
| **Edge Case** | Re-submitting an already used password reset token. | Returns HTTP `400 Bad Request` with detail `"Invalid, expired, or already used reset token."`. | Prevents replay attacks using captured or old reset links. |
| **Failure Mode** | Invalid, tampered, or expired reset token submitted. | Returns HTTP `400 Bad Request` and logs `password_reset_failed`. | Ensures unauthorized password changes cannot occur with invalid tokens. |

---

### 3.5 `POST /auth/change-password` (Authenticated Password Change)

| Case Type | Test Description | Target Logic / Requirement | Why Included |
| :--- | :--- | :--- | :--- |
| **Happy Path** | Authenticated user submits correct current password and new password. | Verifies current password hash, hashes new password, updates user repository, logs event, and returns HTTP `200 OK`. | Validates standard password update for logged-in users. |
| **Edge Case** | Authenticated user provides incorrect current password. | Returns HTTP `400 Bad Request` with detail `"Incorrect current password."`. | Prevents unauthorized password updates if a session is left unattended. |
| **Failure Mode** | Request attempted without valid bearer token (unauthenticated). | Returns HTTP `401 Unauthorized`. | Verifies `get_current_user` dependency guard on password change endpoint. |

---

### 3.6 `POST /users` (User Registration & Auth Foundations)

| Case Type | Test Description | Target Logic / Requirement | Why Included |
| :--- | :--- | :--- | :--- |
| **Happy Path** | New user details (email, password, full name) submitted. | Hashes password via bcrypt, creates user & profile records, returns HTTP `201 Created` with sanitized user object (no password hash). | Validates account creation and password hashing during signup. |
| **Edge Case** | Registration attempt using an email address that already exists. | Throws domain validation exception and returns HTTP `400 Bad Request` `"User with this email already exists"`. | Enforces unique email constraints across the system. |
| **Failure Mode** | Password missing or shorter than minimum required length. | Returns HTTP `400 Bad Request` / `422 Unprocessable Entity`. | Enforces baseline password security requirements. |

---

## 4. Summary of Decided Test Cases & Rationale

1. **Anti-Enumeration Integrity (`/auth/forgot-password`)**:
   - *Rationale*: Both registered and unregistered emails return identical HTTP `200` response payloads to comply with security Spec `004`.
2. **Token Lifecycle & Expiration (`JwtSecurityAdapter`)**:
   - *Rationale*: Expiration logic (`exp` claim) must be strictly tested at unit level using time offset mocks to prevent standard JWT reuse vulnerability.
3. **Single-Use Reset Tokens (`TinyDBPasswordResetTokenRepository`)**:
   - *Rationale*: Once a password reset token is used, `is_used` must evaluate to `True` to prevent replay attacks.
4. **Inactive User Lockout (`get_current_user`)**:
   - *Rationale*: Even if a user possesses a non-expired JWT, setting `is_active=False` must immediately block access across all protected routes (`403 Forbidden`).
