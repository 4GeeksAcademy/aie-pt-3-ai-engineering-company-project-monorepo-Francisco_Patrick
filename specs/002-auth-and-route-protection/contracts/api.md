# API Contracts: Auth & Route Protection

## Authentication

### `POST /auth/login`
Validates credentials and returns a JWT access token.
- **Request Body (`application/x-www-form-urlencoded`)**:
  ```text
  username=user%40example.com&password=my_secure_password
  ```
  *(Note: FastAPI's `OAuth2PasswordBearer` explicitly requires this form-data format; JSON payloads will be rejected)*
- **Response (200 OK)**:
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1...",
    "token_type": "bearer"
  }
  ```
- **Response (401 Unauthorized)**: Invalid credentials.

### `GET /auth/me`
Returns the authenticated user's details and linked profile.
- **Headers**: `Authorization: Bearer <token>`
- **Response (200 OK)**:
  ```json
  {
    "email": "user@example.com",
    "role": "user",
    "profile": {
      "name": "Jane Doe",
      "phone": "+1234567890",
      "address": "123 Main St"
    }
  }
  ```

## Users

### `POST /users`
Registers a new user and an optional linked profile.
- **Request Body (JSON)**:
  ```json
  {
    "email": "newuser@example.com",
    "password": "strong_password",
    "name": "John Doe",
    "phone": "+0987654321",
    "address": "456 Side St"
  }
  ```
- **Response (201 Created)**: Returns the created user object (without password).

### `GET /users` (Protected)
Lists all users. (Typically requires admin role).
- **Headers**: `Authorization: Bearer <token>`
- **Response (200 OK)**: List of user objects.

### `GET /users/{id}` (Protected)
Gets a single user by ID.
- **Headers**: `Authorization: Bearer <token>`
- **Response (200 OK)**: User object.

### `PUT /users/{id}` (Protected)
Updates credential fields (email, role). Role updates require admin privileges. Users can only update their own credentials unless they are admins.
- **Headers**: `Authorization: Bearer <token>`
- **Request Body (JSON)**:
  ```json
  {
    "email": "updated@example.com",
    "role": "manager"
  }
  ```
- **Response (200 OK)**: Updated user object.
- **Response (403 Forbidden)**: Attempting to modify another user's credentials without admin role.

### `DELETE /users/{id}` (Protected)
Deletes a user and their linked profile.
- **Headers**: `Authorization: Bearer <token>`
- **Response (204 No Content)**: User deleted successfully.

## Profiles

### `GET /profiles/me` (Protected)
Returns the authenticated user's profile.
- **Headers**: `Authorization: Bearer <token>`
- **Response (200 OK)**: Profile object.

### `PUT /profiles/me` (Protected)
Updates the authenticated user's profile data.
- **Headers**: `Authorization: Bearer <token>`
- **Request Body (JSON)**:
  ```json
  {
    "name": "Updated Name",
    "phone": "+1122334455",
    "address": "789 New St"
  }
  ```
- **Response (200 OK)**: Updated profile object.
