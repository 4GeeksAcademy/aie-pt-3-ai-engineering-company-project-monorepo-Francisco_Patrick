# Feature Specification: Auth & Route Protection

**Feature Branch**: `[002-auth-and-route-protection]`

**Created**: 2026-09-07

**Status**: Draft

**Input**: User description: "/speckit-specify 
# AUTH-01 — Implement authentication and route protection
The API currently has no authentication layer. This task covers:

- A `users` module with full CRUD (create, read, update, delete) for credentials only — email and password.
- A `profiles` module with a one-to-one link to each user — display name and contact data live on `Profile`, not on `User`.
- A login endpoint that validates credentials and returns a signed JWT token.
- A reusable `get_current_user` dependency that decodes the token and identifies the caller.
Application of that dependency to all routes that should not be publicly accessible.
Store `User` and `Profile` in TinyDB only — The JWT must carry the TinyDB user `id`; inventory and other modules reference it as `user_uuid`.

Use `OAuth2PasswordBearer` from FastAPI and `python-jose` for token signing. Passwords must be hashed — never stored or compared in plain text. The token should carry the user's ID at minimum and expire after a configurable window.

All auth-related routes must live under `/auth`. User management routes under `/users`. Profile routes under `/profiles`.
Once you protect your routes, some frontend calls may stop working temporarily — that's expected. The frontend will be updated to send the token in subsequent work. For now, focus on securing the API to prevent data leaks and unauthorized access.
Required packages: "python-jose[cryptography]" "libpass[bcrypt]"
## User model and CRUD
- Create a User model in TinyDB with at least: id, email, hashed_password, is_active, role, created_at. Do not store display name or contact fields on User.
- The role field must accept only admin, manager, or user. Use an Enum or field validator to reject any other value. New registrations via POST /users default to user.
- Implement a service layer with functions for: create user, get user by ID, get user by email, update user, delete user.
- Expose those services as REST endpoints under /users:
    - POST /users — register a new user (hash the password before storing). Accept optional initial profile fields (name, phone, address) and create the linked Profile in the same operation.
    - GET /users — list all users (protected).
    - GET /users/{id} — get a single user (protected).
    - PUT /users/{id} — update credential fields such as email, and role when the caller is an admin (protected; only the user themselves or an admin).
    - DELETE /users/{id} — delete a user (protected). Also remove the linked profile.
## Profile model and endpoints
- Create a Profile model in TinyDB, linked one-to-one to User via user_id, with at least: id, user_id, name, phone, address.
- Expose profile routes under /profiles:
    - GET /profiles/me (protected) — return the authenticated user's profile.
    - PUT /profiles/me (protected) — update name, phone, and address. Only the profile owner may update it.
## Authentication endpoints
- Implement POST /auth/login — accepts email and password, validates credentials, returns a JWT access token.
- Implement GET /auth/me (protected) — returns the authenticated user's email, role, plus the linked Profile (name and contact data).
## Token and dependency
- Create a get_current_user dependency that: extracts the Authorization: Bearer <token> header, decodes and validates the JWT, retrieves the user from the database, and raises HTTPException(401) if anything fails.
- Set token expiry via an environment variable (e.g. ACCESS_TOKEN_EXPIRE_MINUTES). Store the signing secret in .env — never hardcode it.
## Route protection
- Apply get_current_user as a dependency to every route that should not be publicly accessible. At minimum: all /users endpoints except POST /users, /auth/me, and at least 5 other existing routes from your monorepo API (outside /users and /auth) that expose or modify sensitive data.
- Return 401 Unauthorized for unauthenticated requests and 403 Forbidden when a user tries to access a resource they don't own.
## Testing
- Verify the full flow manually using the FastAPI interactive docs (/docs): register via POST /users → login → copy token → use token on a protected route.
- Confirm that calling a protected route without a token returns 401.
- Confirm that calling a protected route with an expired or malformed token returns 401.
IMPORTANT: Store User and Profile in TinyDB only — now and after Supabase is added. Do not create user or profile tables in Supabase/SQLModel. Inventory and other PostgreSQL tables store only the TinyDB user id as user_uuid.
IMPORTANT: Do not use session-based or cookie-based authentication. This project implements stateless JWT auth only.
IMPORTANT: Never store plain-text passwords. Use libpass with the bcrypt scheme for all password operations. Install libpass[bcrypt] — not unmaintained passlib. The Python import stays from passlib.hash import bcrypt (libpass is a drop-in fork).
## Acceptante Criteria
 User CRUD is fully implemented and reachable via the API.
 Each User has a linked Profile; name, phone, and address are stored on Profile, not on User.
 The role field accepts only admin, manager, or user; new users created via POST /users default to user.
 Passwords are hashed at creation and compared correctly at login — plain text never touches the database.
 Login endpoint returns a valid, signed JWT token.
 get_current_user dependency correctly decodes the token and identifies the user.
 Protected routes return 401 when called without a valid token.
 A user accessing or updating another user's profile or credentials receives 403 Forbidden (not only 401 for missing/invalid token).
 Token expiry and signing secret are read from environment variables, not hardcoded.
 Auth routes are under /auth, user routes under /users, and profile routes under /profiles — clean, consistent structure.
 At least 5 existing routes outside /users and /auth require a valid token (in addition to the protected user/auth routes themselves).
 User and Profile remain in TinyDB after Supabase is introduced — no user tables in PostgreSQL.
 Protected monorepo routes still behave correctly when called with a valid token (no regressions)."

## Clarifications

### Session 2026-09-07
- Q: How should the system handle authentication for users where `is_active` is false? → A: Reject login and return 401/403 for API requests
- Q: How should the application behave if the JWT secret key is missing from the environment? → A: Abort startup/crash immediately to prevent insecure operation
- Q: Since FastAPI's `OAuth2PasswordBearer` is required, should the `/auth/login` endpoint accept credentials as Form Data (the OAuth2 standard) or JSON? → A: Accept `application/x-www-form-urlencoded` (OAuth2 standard)
- Q: Should there be minimum complexity requirements for passwords during registration? → A: Minimum 8 characters, no special character requirement

## User Scenarios & Testing *(mandatory)*

### User Story 1 - User Registration and Profile Creation (Priority: P1)

Users can register for a new account by providing their email and password, along with optional profile information (name, phone, address). The system creates a user and linked profile.

**Why this priority**: Essential first step for users to access the system and establish identity.

**Independent Test**: Can be tested via POST `/users`. Calling the endpoint with valid credentials creates a user and profile in the database, and returns the user object (without the password).

**Acceptance Scenarios**:

1. **Given** a valid new email, password, and optional profile data, **When** submitting to POST `/users`, **Then** the user and profile are created, the password is hashed, the default role is 'user', and success is returned.
2. **Given** an existing email, **When** submitting to POST `/users`, **Then** the registration is rejected with an appropriate error.

---

### User Story 2 - User Login (Priority: P1)

Users can log in with their email and password to receive a JWT token for accessing protected resources.

**Why this priority**: Required for users to authenticate and prove their identity in subsequent requests.

**Independent Test**: Can be tested via POST `/auth/login`. Providing valid credentials returns a signed JWT token containing the user's ID.

**Acceptance Scenarios**:

1. **Given** valid credentials, **When** submitting to POST `/auth/login`, **Then** a signed JWT token is returned.
2. **Given** invalid credentials, **When** submitting to POST `/auth/login`, **Then** a 401 Unauthorized error is returned.

---

### User Story 3 - Accessing Protected Resources (Priority: P1)

Authenticated users can access their own protected data (e.g., their profile) and use protected endpoints by including their JWT token in the Authorization header.

**Why this priority**: Enforces security and ensures only authorized users can access sensitive data.

**Independent Test**: Can be tested by calling a protected endpoint (like GET `/auth/me` or GET `/profiles/me`) with and without a valid token.

**Acceptance Scenarios**:

1. **Given** a valid, unexpired JWT token in the header, **When** calling a protected endpoint, **Then** the request succeeds and returns the requested data.
2. **Given** a missing, invalid, or expired JWT token, **When** calling a protected endpoint, **Then** a 401 Unauthorized error is returned.
3. **Given** a valid token for User A, **When** attempting to update credentials or profile of User B, **Then** a 403 Forbidden error is returned.

---

### User Story 4 - Admin Managing Users (Priority: P2)

Admin users can list, view, and manage all users in the system, including updating roles or deleting accounts.

**Why this priority**: Necessary for system administration and user management.

**Independent Test**: Can be tested by calling GET `/users`, PUT `/users/{id}`, and DELETE `/users/{id}` with an admin user's token.

**Acceptance Scenarios**:

1. **Given** an admin user token, **When** calling GET `/users`, **Then** a list of all users is returned.
2. **Given** a regular user token, **When** attempting to update another user's role via PUT `/users/{id}`, **Then** a 403 Forbidden error is returned.

### Edge Cases

- What happens when a token expires during a request? (Should return 401)
- How does the system handle concurrent login requests or multiple active tokens? (JWTs are stateless, so multiple tokens can be valid simultaneously until expiration)
- If the `ACCESS_TOKEN_EXPIRE_MINUTES` or secret key is missing from the environment, the application must abort startup/crash immediately to prevent insecure operation.
- If a user's `is_active` flag is false, any attempt to log in or use an existing token must be rejected with a 401/403 error.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `users` module for CRUD operations on user credentials (email, hashed password, is_active, role, created_at) stored in TinyDB.
- **FR-002**: System MUST provide a `profiles` module linked one-to-one with users, storing display name, phone, and address in TinyDB.
- **FR-003**: System MUST NOT store plain-text passwords. Passwords MUST be hashed using bcrypt before storage.
- **FR-004**: System MUST expose a POST `/users` endpoint for registration, defaulting the role to 'user' and accepting optional profile data. Passwords MUST be at least 8 characters long (no special character requirements).
- **FR-005**: System MUST provide a POST `/auth/login` endpoint that accepts credentials as `application/x-www-form-urlencoded` (OAuth2 standard), validates them, and returns a signed JWT token.
- **FR-006**: System MUST use a stateless JWT authentication mechanism; no session or cookie-based auth.
- **FR-007**: System MUST provide a `get_current_user` dependency to decode tokens, identify the caller, verify the user `is_active` is true, and protect routes (returning 401 for invalid/missing tokens or inactive users).
- **FR-008**: System MUST enforce authorization: users can only modify their own credentials/profile unless they have an 'admin' role (returning 403 for unauthorized access).
- **FR-009**: System MUST protect at least 5 existing sensitive routes outside of `/users` and `/auth` using the `get_current_user` dependency.
- **FR-010**: System MUST read the JWT signing secret and expiration time from environment variables, and MUST crash at startup if they are missing.
- **FR-011**: System MUST remove the linked Profile when a User is deleted.

### Key Entities

- **User**: Represents authentication credentials. Attributes: `id` (UUID), `email`, `hashed_password`, `is_active`, `role` (admin, manager, user), `created_at`.
- **Profile**: Represents user contact information. Attributes: `id` (UUID), `user_id` (links to User), `name`, `phone`, `address`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can successfully register, log in, and receive a JWT token.
- **SC-002**: The `get_current_user` dependency correctly identifies the user from a valid token and rejects invalid tokens with a 401.
- **SC-003**: A user attempting to modify another user's data receives a 403 Forbidden response.
- **SC-004**: At least 5 previously unprotected routes now require authentication and return 401 when accessed without a token.
- **SC-005**: All plain-text passwords are hashed; no plain-text passwords exist in the TinyDB database.
- **SC-006**: The system continues to use TinyDB for User and Profile data, and existing monorepo routes function correctly when provided a valid token.

## Assumptions

- Users will manage their tokens on the client side (e.g., storing in memory or local storage).
- The frontend will be updated separately to handle token storage and inclusion in API requests.
- TinyDB is sufficient for the scale and concurrency requirements of user and profile management for this feature.
