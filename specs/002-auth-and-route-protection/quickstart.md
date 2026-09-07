# Quickstart Validation Guide: Auth & Route Protection

This guide outlines how to manually validate the Auth and Route Protection feature once implemented.

## Prerequisites
- The backend API must be running (e.g., via `uvicorn main:app --reload` or the monorepo's equivalent dev server command).
- An API client tool like `curl`, Postman, or the built-in FastAPI Swagger UI at `http://localhost:8000/docs`.

## Validation Scenarios

### 1. User Registration
**Action**: Create a new user account.
**Command**:
```bash
curl -X POST "http://localhost:8000/users" \
     -H "Content-Type: application/json" \
     -d '{"email": "test@example.com", "password": "secure123", "name": "Test User"}'
```
**Expected Outcome**: Returns a 201 Created with the user object (excluding the password).

### 2. User Login
**Action**: Log in with the newly created user credentials to receive a JWT token.
**Command**:
```bash
# FastAPI's OAuth2PasswordBearer expects form data:
curl -X POST "http://localhost:8000/auth/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=test@example.com&password=secure123"
```
**Expected Outcome**: Returns a 200 OK with a JSON object containing the `access_token` and `token_type`.

### 3. Access Protected Route (Valid Token)
**Action**: Use the JWT token to access a protected route (e.g., getting the user's own profile).
**Command**:
```bash
# Replace <YOUR_TOKEN> with the token received from the login step.
curl -X GET "http://localhost:8000/profiles/me" \
     -H "Authorization: Bearer <YOUR_TOKEN>"
```
**Expected Outcome**: Returns a 200 OK with the user's profile data (e.g., name: "Test User").

### 4. Access Protected Route (Invalid Token)
**Action**: Attempt to access a protected route without a token or with a malformed token.
**Command**:
```bash
curl -X GET "http://localhost:8000/profiles/me"
# Or with a fake token:
curl -X GET "http://localhost:8000/profiles/me" \
     -H "Authorization: Bearer invalid_token_123"
```
**Expected Outcome**: Returns a 401 Unauthorized error.

### 5. Authorization Check (Forbidden)
**Action**: Attempt to update another user's profile using a regular user token.
**Command**:
```bash
# Assuming user ID 2 exists and the token belongs to user ID 1
curl -X PUT "http://localhost:8000/users/2" \
     -H "Authorization: Bearer <YOUR_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"role": "admin"}'
```
**Expected Outcome**: Returns a 403 Forbidden error, as the user is trying to modify a resource they do not own and they are not an admin.
