# API Contracts: AUTH-03 Password Reset

## Endpoints

### 1. `POST /auth/forgot-password`
Solicita el restablecimiento de contraseña para un correo electrónico.

- **Auth Required**: No (público)
- **Request Body**:
  ```json
  {
    "email": "user@example.com"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "message": "If that email is registered, you will receive a reset link shortly."
  }
  ```
- **Response `429 Too Many Requests`**:
  ```json
  {
    "error": "Too many password reset attempts. Please try again later."
  }
  ```

---

### 2. `POST /auth/reset-password`
Restablece la contraseña utilizando el token enviado por correo electrónico.

- **Auth Required**: No (público via token)
- **Request Body**:
  ```json
  {
    "token": "d7a8e9f0c1b2...",
    "new_password": "NewSecurePassword123!"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "message": "Password successfully updated."
  }
  ```
- **Response `400 Bad Request`**:
  ```json
  {
    "error": "Invalid, expired, or already used reset token."
  }
  ```

---

### 3. `POST /auth/change-password`
Cambia la contraseña de un usuario autenticado.

- **Auth Required**: Sí (`Authorization: Bearer <session_token>`)
- **Request Body**:
  ```json
  {
    "current_password": "CurrentPassword123!",
    "new_password": "NewSecurePassword123!"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "message": "Password successfully changed."
  }
  ```
- **Response `400 Bad Request`**:
  ```json
  {
    "error": "Incorrect current password."
  }
  ```
- **Response `401 Unauthorized`**:
  ```json
  {
    "error": "Unauthorized session token."
  }
  ```
