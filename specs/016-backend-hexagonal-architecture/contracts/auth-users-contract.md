# Auth, Users, Profiles & Telemetry API Contracts

**Service**: `services/api`  
**Domains**: Authentication, User Management, Profiles, Telemetry  
**Storage**: TinyDB (`users`, `profiles`, `password_reset_tokens`, `audit_logs`)  

---

## 1. Authentication Domain (`/auth` & `/api/v1/auth`)

### 1.1 Login & Issue JWT
* **Method**: `POST`
* **Path**: `/auth/login` & `/api/v1/auth/login`
* **Request Payload**: Form-encoded `OAuth2PasswordRequestForm` (`username` = email, `password`)
* **Status**: `200 OK`
* **Response Payload (`Token`)**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
    "token_type": "bearer"
  }
  ```
* **Errors**: `401 Unauthorized` (bad credentials), `403 Forbidden` (account inactive)

### 1.2 Get Current User
* **Method**: `GET`
* **Path**: `/auth/me` & `/api/v1/auth/me`
* **Security**: Bearer JWT
* **Status**: `200 OK`
* **Response Payload (`UserResponse`)**:
  ```json
  {
    "id": "usr_9f81a7b2",
    "email": "user@example.com",
    "role": "user",
    "is_active": true,
    "created_at": "2026-10-13T10:00:00Z"
  }
  ```

### 1.3 Forgot Password (Rate Limited)
* **Method**: `POST`
* **Path**: `/auth/forgot-password` & `/api/v1/auth/forgot-password`
* **Request Payload**: `{"email": "user@example.com"}`
* **Status**: `200 OK`
* **Response Payload**: `{"message": "If the email is registered, a password reset link has been sent."}`

### 1.4 Reset Password
* **Method**: `POST`
* **Path**: `/auth/reset-password` & `/api/v1/auth/reset-password`
* **Request Payload**: `{"token": "secure_reset_token", "new_password": "newSecurePassword123"}`
* **Status**: `200 OK`
* **Response Payload**: `{"message": "Password successfully reset."}`
* **Errors**: `400 Bad Request` (expired/used token, weak password)

### 1.5 Change Password
* **Method**: `POST`
* **Path**: `/auth/change-password` & `/api/v1/auth/change-password`
* **Security**: Bearer JWT
* **Request Payload**: `{"current_password": "...", "new_password": "..."}`
* **Status**: `200 OK`
* **Response Payload**: `{"message": "Password successfully changed."}`
* **Errors**: `400 Bad Request` (incorrect current password or weak new password)

---

## 2. User Administration Domain (`/users` & `/api/v1/users`)

### 2.1 Register User (Public)
* **Method**: `POST`
* **Path**: `/users` & `/api/v1/users`
* **Request Payload (`UserCreate`)**:
  ```json
  {
    "email": "lead@company.com",
    "password": "strongPassword123",
    "profile": {
      "name": "Alex Mercer"
    }
  }
  ```
* **Status**: `201 Created`
* **Response Payload**: `UserResponse`
* **Errors**: `400 Bad Request` (duplicate email or password < 8 chars)

### 2.2 List Users (Admin Only)
* **Method**: `GET`
* **Path**: `/users` & `/api/v1/users`
* **Security**: Admin Bearer JWT (`Depends(get_current_admin_user)`)
* **Status**: `200 OK`
* **Response Payload**: `List[UserResponse]`

### 2.3 User Detail & Mutations (Admin Only)
* `GET /users/{user_id}`: Returns `UserResponse` (Status 200)
* `PUT /users/{user_id}`: Updates user role, active status, or credentials (Status 200)
* `DELETE /users/{user_id}`: Deletes user and associated profile (Status 204)

---

## 3. User Profiles Domain (`/profiles` & `/api/v1/profiles`)

### 3.1 Get Profile
* **Method**: `GET`
* **Path**: `/profiles/me` & `/api/v1/profiles/me`
* **Security**: Bearer JWT
* **Status**: `200 OK`
* **Response Payload (`Profile`)**:
  ```json
  {
    "user_id": "usr_9f81a7b2",
    "name": "Alex Mercer",
    "phone": "+15551234567",
    "address": "456 Logistics Blvd, Suite 200",
    "updated_at": "2026-10-13T10:00:00Z"
  }
  ```

### 3.2 Update Profile
* **Method**: `PUT`
* **Path**: `/profiles/me` & `/api/v1/profiles/me`
* **Security**: Bearer JWT
* **Request Payload (`ProfileBase`)**: `{"name": "...", "phone": "...", "address": "..."}`
* **Status**: `200 OK`
* **Response Payload**: `Profile`

---

## 4. Telemetry Domain (`/telemetry` & `/api/v1/telemetry`)

### 4.1 Ingest Telemetry Batch
* **Method**: `POST`
* **Path**: `/telemetry/events` & `/api/v1/telemetry/events`
* **Security**: Public
* **Status**: `200 OK`
* **Request Payload (`TelemetryBatch`)**:
  ```json
  {
    "events": [
      {
        "event_id": "c1f2e4d6-84d2-4e4b-9c6f-998246e7f1a3",
        "session_id": "sess_81729",
        "event_type": "page.view",
        "timestamp": "2026-10-13T10:00:00Z",
        "schema_version": "1.0.0",
        "payload": {
          "url": "/dashboard/inventory"
        }
      }
    ]
  }
  ```
* **Response Payload (`IngestReceipt`)**:
  ```json
  {
    "received": 1
  }
  ```
