# Interface & Test Assertion Contracts: Authentication API

**Feature**: `009-auth-api-tests`  
**Date**: 2026-09-13

## Test Assertion Matrix

### 1. `POST /auth/login`
- **Happy Path Contract**:
  - Request: `username="user@example.com"`, `password="Password123!"`
  - Expected Response: `status_code == 200`, `json()["access_token"]` is non-empty string, `json()["token_type"] == "bearer"`.
- **Edge Case Contract (Inactive Account)**:
  - Request: `username="inactive@example.com"`, `password="Password123!"`
  - Expected Response: `status_code == 403`, `json()["detail"] == "User account is inactive"`.
- **Failure Mode Contract (Invalid Credentials)**:
  - Request: `username="user@example.com"`, `password="WrongPassword"`
  - Expected Response: `status_code == 401`, `json()["detail"] == "Invalid email or password"`.

---

### 2. `GET /auth/me`
- **Happy Path Contract**:
  - Request Header: `Authorization: Bearer <valid_jwt>`
  - Expected Response: `status_code == 200`, `json()["email"] == "user@example.com"`.
- **Edge Case Contract (Expired Token)**:
  - Request Header: `Authorization: Bearer <expired_jwt>`
  - Expected Response: `status_code == 401`, `json()["detail"] == "Could not validate credentials"`.
- **Failure Mode Contract (Missing Authorization Header)**:
  - Request Header: None
  - Expected Response: `status_code == 401`.

---

### 3. `POST /auth/forgot-password`
- **Happy Path Contract**:
  - Payload: `{"email": "user@example.com"}`
  - Expected Response: `status_code == 200`, `json()["message"] == "If that email is registered, you will receive a reset link shortly."`. Reset token record created in DB.
- **Edge Case Contract (Unregistered Email Anti-Enumeration)**:
  - Payload: `{"email": "unregistered@example.com"}`
  - Expected Response: `status_code == 200`, `json()["message"] == "If that email is registered, you will receive a reset link shortly."`. Zero emails dispatched.

---

### 4. `POST /auth/reset-password`
- **Happy Path Contract**:
  - Payload: `{"token": "<valid_raw_token>", "new_password": "NewPassword123!"}`
  - Expected Response: `status_code == 200`, `json()["message"] == "Password successfully updated."`. Password hash updated.
- **Edge Case Contract (Reused Token)**:
  - Payload: `{"token": "<used_raw_token>", "new_password": "NewPassword123!"}`
  - Expected Response: `status_code == 400`, `json()["detail"] == "Invalid, expired, or already used reset token."`.

---

### 5. `POST /auth/change-password`
- **Happy Path Contract**:
  - Header: `Authorization: Bearer <valid_jwt>`
  - Payload: `{"current_password": "Password123!", "new_password": "NewPassword456!"}`
  - Expected Response: `status_code == 200`, `json()["message"] == "Password successfully changed."`.
- **Edge Case Contract (Incorrect Current Password)**:
  - Header: `Authorization: Bearer <valid_jwt>`
  - Payload: `{"current_password": "WrongPassword", "new_password": "NewPassword456!"}`
  - Expected Response: `status_code == 400`, `json()["detail"] == "Incorrect current password."`.

---

### 6. `POST /users` (User Registration)
- **Happy Path Contract**:
  - Payload: `{"email": "newuser@example.com", "password": "Password123!", "full_name": "New User"}`
  - Expected Response: `status_code == 201`, `json()["email"] == "newuser@example.com"`, `hashed_password` absent from response payload.
- **Edge Case Contract (Duplicate Email)**:
  - Payload: `{"email": "existing@example.com", "password": "Password123!", "full_name": "Existing User"}`
  - Expected Response: `status_code == 400`, `json()["detail"] == "User with this email already exists"`.
