# Phase 1 Data Model & Test Fixtures: Authentication API Testing

**Feature**: `009-auth-api-tests`  
**Date**: 2026-09-13

## Test Fixture Models & Schemas

### 1. Test User Entity (`UserFixture`)
Represents synthetic test users configured for happy-path, edge-case, and failure-mode testing.

```json
{
  "id": "usr_test_001",
  "email": "user@example.com",
  "hashed_password": "<bcrypt_hash_of_Password123!>",
  "full_name": "Active Test User",
  "role": "user",
  "is_active": true,
  "created_at": "2026-09-13T00:00:00Z"
}
```

- **Inactive User Fixture (`usr_inactive_002`)**: `is_active = false` (used for `403 Forbidden` edge cases).
- **Admin User Fixture (`usr_admin_003`)**: `role = "admin"` (used for admin authorization checks).

---

### 2. Password Reset Token Entity (`PasswordResetTokenFixture`)
Represents password reset token records tracked in the reset token repository.

```json
{
  "id": "rst_tok_001",
  "user_id": "usr_test_001",
  "raw_token": "secure_random_token_string_32_chars",
  "expires_at": "2026-09-13T22:00:00Z",
  "is_used": false,
  "created_at": "2026-09-13T21:30:00Z"
}
```

- **Used Token State (`rst_tok_used`)**: `is_used = true` (triggers `400 Bad Request` edge case on reuse attempt).
- **Expired Token State (`rst_tok_exp`)**: `expires_at` in the past (triggers `400 Bad Request` failure mode).

---

### 3. JWT Payload Model (`JwtTokenPayload`)
Represents encoded and decoded JWT bearer token payloads.

```json
{
  "sub": "usr_test_001",
  "exp": 1789336800
}
```
