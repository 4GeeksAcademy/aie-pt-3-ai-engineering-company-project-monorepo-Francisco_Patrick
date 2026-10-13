# API Contracts: Backend Serialization Improvement

**Feature Branch**: `013-backend-serialization-improvement`
**Date**: 2026-09-29
**Status**: Completed

This document defines the HTTP API endpoint contracts updated to achieve strict serialization compliance.

---

## 1. Authentication Endpoints

### 1.1 `GET /auth/me`
* **Description**: Returns safe account attributes for currently authenticated user session.
* **Headers**: `Authorization: Bearer <JWT_TOKEN>`
* **Status**: `200 OK`
* **Response Schema**: `UserResponse`
* **Response Payload Example**:
  ```json
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "email": "user@example.com",
    "is_active": true,
    "role": "user",
    "created_at": "2026-09-29T10:00:00Z"
  }
  ```

---

### 1.2 `POST /auth/forgot-password`
* **Description**: Requests a password reset link for the given email address.
* **Request Body**:
  ```json
  {
    "email": "user@example.com"
  }
  ```
* **Status**: `200 OK`
* **Response Schema**: `MessageResponse`
* **Response Payload Example**:
  ```json
  {
    "message": "If that email is registered, you will receive a reset link shortly."
  }
  ```

---

### 1.3 `POST /auth/reset-password`
* **Description**: Resets a user password using a verified reset token.
* **Request Body**:
  ```json
  {
    "token": "raw-secure-token-value-here",
    "new_password": "NewSecurePassword123!"
  }
  ```
* **Status**: `200 OK`
* **Response Schema**: `MessageResponse`
* **Response Payload Example**:
  ```json
  {
    "message": "Password successfully updated."
  }
  ```

---

### 1.4 `POST /auth/change-password`
* **Description**: Changes password for an active authenticated user session.
* **Headers**: `Authorization: Bearer <JWT_TOKEN>`
* **Request Body**:
  ```json
  {
    "current_password": "CurrentPassword123!",
    "new_password": "BrandNewPassword123!"
  }
  ```
* **Status**: `200 OK`
* **Response Schema**: `MessageResponse`
* **Response Payload Example**:
  ```json
  {
    "message": "Password successfully changed."
  }
  ```

---

## 2. User Management Endpoints

### 2.1 `POST /users`
* **Description**: Registers a new user account and linked profile.
* **Request Body**:
  ```json
  {
    "email": "newuser@example.com",
    "password": "SecurePassword123!",
    "profile": {
      "name": "Jane Doe",
      "phone": "+15551234567",
      "address": "456 Logistics Way"
    }
  }
  ```
* **Status**: `201 Created`
* **Response Schema**: `UserResponse`
* **Response Payload Example**:
  ```json
  {
    "id": "e4f5g6h7-89ab-cdef-0123-456789abcdef",
    "email": "newuser@example.com",
    "is_active": true,
    "role": "user",
    "created_at": "2026-09-29T11:00:00Z"
  }
  ```

---

### 2.2 `GET /users`
* **Description**: Lists all registered users in the system (Admin only).
* **Headers**: `Authorization: Bearer <ADMIN_JWT_TOKEN>`
* **Status**: `200 OK`
* **Response Schema**: `List[UserResponse]`
* **Response Payload Example**:
  ```json
  [
    {
      "id": "admin-id-1234",
      "email": "admin@example.com",
      "is_active": true,
      "role": "admin",
      "created_at": "2026-09-01T00:00:00Z"
    },
    {
      "id": "user-id-5678",
      "email": "user@example.com",
      "is_active": true,
      "role": "user",
      "created_at": "2026-09-15T00:00:00Z"
    }
  ]
  ```

---

### 2.3 `GET /users/{user_id}`
* **Description**: Retrieves user account details by ID (Admin only).
* **Headers**: `Authorization: Bearer <ADMIN_JWT_TOKEN>`
* **Status**: `200 OK`
* **Response Schema**: `UserResponse`
* **Response Payload Example**:
  ```json
  {
    "id": "user-id-5678",
    "email": "user@example.com",
    "is_active": true,
    "role": "user",
    "created_at": "2026-09-15T00:00:00Z"
  }
  ```

---

### 2.4 `PUT /users/{user_id}`
* **Description**: Updates user account attributes (Admin only).
* **Headers**: `Authorization: Bearer <ADMIN_JWT_TOKEN>`
* **Request Body**:
  ```json
  {
    "role": "manager",
    "is_active": true
  }
  ```
* **Status**: `200 OK`
* **Response Schema**: `UserResponse`
* **Response Payload Example**:
  ```json
  {
    "id": "user-id-5678",
    "email": "user@example.com",
    "is_active": true,
    "role": "manager",
    "created_at": "2026-09-15T00:00:00Z"
  }
  ```

---

## 3. Incident Management & Analytics Endpoints

### 3.1 `GET /api/incidents/summary`
* **Description**: Returns 4-dimensional aggregated metric counts of incidents.
* **Status**: `200 OK`
* **Response Schema**: `IncidentSummaryResponse`
* **Response Payload Example**:
  ```json
  {
    "total": 42,
    "by_status": {
      "open": 10,
      "in_progress": 12,
      "resolved": 18,
      "discarded": 2
    },
    "by_category": {
      "warehouse": 15,
      "reverse_logistics": 10,
      "last_mile": 12,
      "customer_experience": 5
    },
    "by_origin": {
      "customer": 14,
      "branch": 16,
      "internal": 12
    },
    "by_branch": {
      "central": 20,
      "north": 12,
      "south": 10
    }
  }
  ```

---

### 3.2 `POST /api/incidents/analyze`
* **Description**: Ingests uploaded CSV stream and returns health metrics and validation diagnostics.
* **Content-Type**: `multipart/form-data` (file upload)
* **Status**: `200 OK`
* **Response Schema**: `IncidentAnalysisResponse`
* **Response Payload Example**:
  ```json
  {
    "metrics": {
      "total_processed": 500,
      "valid_records": 480,
      "invalid_records": 20,
      "category_breakdown": {
        "warehouse": 200,
        "reverse_logistics": 150,
        "last_mile": 100,
        "customer_experience": 30
      },
      "status_breakdown": {
        "open": 120,
        "in_progress": 180,
        "closed": 180
      },
      "average_satisfaction_index": 4.35
    },
    "diagnostics": {
      "invalid_sample": [
        {
          "row": 14,
          "id": "INC-099",
          "reason": "Missing required field: category"
        }
      ]
    }
  }
  ```
