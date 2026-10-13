# Backend API Contracts

This file documents the specific API endpoints, headers, and payloads required for the frontend authentication flow to communicate successfully with the `services/api/` microservices.

## Global Headers
For all protected endpoints (e.g., `GET /auth/me`, `PUT /profiles/me`), the following header is required:
- `Authorization`: `Bearer <access_token>`

## 1. Login (`POST /auth/login`)
Authenticates the user and returns a JWT token.

- **Content-Type**: `application/x-www-form-urlencoded`
- **Request Body**:
  - `username` (string, required): The user's email address.
  - `password` (string, required): The user's password.
- **Response** (200 OK):
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1...",
    "token_type": "bearer"
  }
  ```
- **Response** (401 Unauthorized or 403 Forbidden):
  - Invalid credentials or inactive user.

## 2. Register (`POST /users`)
Creates a new user account.

- **Content-Type**: `application/json`
- **Request Body**:
  ```json
  {
    "email": "user@example.com",
    "password": "securepassword",
    "name": "Jane Doe",
    "phone": "+1234567890",
    "address": "123 Main St"
  }
  ```
- **Response** (201 Created):
  - Returns the created User object (without password).

## 3. Get Current Profile (`GET /auth/me`)
Retrieves the profile of the currently authenticated user.

- **Response** (200 OK):
  ```json
  {
    "id": "user-uuid",
    "email": "user@example.com",
    "is_active": true
  }
  ```

## 4. Update Profile (`PUT /profiles/me`)
Updates the authenticated user's profile information.

- **Content-Type**: `application/json`
- **Request Body**:
  ```json
  {
    "name": "Jane Doe",
    "phone": "+1987654321",
    "address": "456 Market St"
  }
  ```
- **Response** (200 OK):
  - Returns the updated Profile object.
