# Phase 1: Data Model

## Entities

### User
Represents the authentication identity.
- `email` (string, required): User's email address.
- `password` (string, required): User's password (only used during login/registration payload).
- `token` (string): JWT access token returned upon successful authentication (from the `access_token` field).

### Profile
Represents the user's personal information, linked to their account.
- `name` (string, required): Full name.
- `phone` (string, optional): Contact phone number.
- `address` (string, optional): Physical address.

## State Transitions
- **Unauthenticated -> Authenticated**: Triggered by successful `POST /users` (JSON payload) followed by `POST /auth/login` (`application/x-www-form-urlencoded` payload with `username` and `password`). The returned `access_token` is saved to `localStorage`.
- **Authenticated -> Unauthenticated**: Triggered by explicit logout action or receiving a `401 Unauthorized` response. Token is removed from `localStorage`.
