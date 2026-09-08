# Feature Specification: auth-frontend

**Feature Branch**: `[###-feature-name]`

**Created**: 2026-09-08

**Status**: Draft

**Input**: User description: "AUTH-02 — Authentication flows and protected views in the frontend"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - User Registration and Login (Priority: P1)

Users can create an account and log in using their email and password, gaining access to authenticated views.

**Why this priority**: Without authentication, users cannot access any protected functionality in the system.

**Independent Test**: Can be fully tested by submitting the registration and login forms and verifying that the JWT token is successfully stored in `localStorage` and the user is redirected to the authenticated view.

**Acceptance Scenarios**:

1. **Given** a user is on the `/register` page, **When** they submit valid registration details, **Then** an account is created, they are automatically logged in, the token is stored, and they are redirected to the main authenticated view.
2. **Given** a user is on the `/register` page, **When** they submit invalid data, **Then** field-level validation errors are shown.
3. **Given** a user is on the `/login` page, **When** they submit valid credentials, **Then** they receive a token, it is stored in `localStorage`, and they are redirected to the main authenticated view.
4. **Given** a user is on the `/login` page, **When** they submit invalid credentials, **Then** a clear error message is shown.

---

### User Story 2 - Protected Routes (Priority: P1)

Unauthenticated users attempting to access protected routes are redirected to the login page, while the public website remains fully accessible.

**Why this priority**: Ensures security and prevents unauthorized access to sensitive views.

**Independent Test**: Can be fully tested by attempting to navigate to a protected route without a token in `localStorage` and observing the redirect, then navigating to a public website route to ensure no redirect occurs.

**Acceptance Scenarios**:

1. **Given** an unauthenticated user, **When** they attempt to access a protected route, **Then** they are redirected to `/login`.
2. **Given** an unauthenticated user, **When** they attempt to access a route on the public website (`uis/website/`), **Then** they can view the page without any authentication checks or redirects.
3. **Given** an authenticated user with a valid token, **When** they access a protected route, **Then** the page loads successfully.
4. **Given** an authenticated user, **When** their token expires and an API call returns a 401 status, **Then** the token is cleared and they are redirected to `/login`.

---

### User Story 3 - Account Management and Profile Edit (Priority: P2)

Authenticated users can view and edit their profile information.

**Why this priority**: Users need to be able to manage their personal data and keep their contact information up to date.

**Independent Test**: Can be fully tested by logging in, navigating to `/account/profile`, and updating profile fields.

**Acceptance Scenarios**:

1. **Given** an authenticated user is on `/account/profile`, **When** the page loads, **Then** their email and profile data (name, phone, address) are displayed.
2. **Given** an authenticated user is on `/account/profile`, **When** they submit updated name or contact fields, **Then** the changes are saved successfully via the API.

---

### User Story 4 - Logout (Priority: P1)

Users can log out to securely end their session.

**Why this priority**: Allows users to secure their account on shared devices.

**Independent Test**: Can be fully tested by logging out and verifying the token is removed.

**Acceptance Scenarios**:

1. **Given** an authenticated user, **When** they initiate the logout action, **Then** the token is removed from `localStorage` and they are redirected to `/login`.

### Edge Cases

- What happens when the `localStorage` is disabled or inaccessible in the user's browser?
- How does system handle concurrent logins from multiple tabs?
- What happens if the API `POST /users` succeeds but the subsequent `POST /auth/login` fails during registration?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a login form at `/login` that accepts email and password and displays clear error messages on failure.
- **FR-002**: System MUST provide a registration form at `/register` that creates a user, logs them in, and displays field-level validation errors on failure.
- **FR-003**: System MUST store the received JWT token in the browser's `localStorage` upon successful login or registration.
- **FR-004**: System MUST attach the stored JWT token as an `Authorization: Bearer <token>` header to all protected API calls.
- **FR-005**: System MUST implement a client-side protection mechanism that intercepts access to protected Next.js views and redirects to `/login` if no valid token is found.
- **FR-006**: System MUST NOT apply any authentication checks or redirects to the public website (`uis/website/`).
- **FR-007**: System MUST provide a profile view at `/account/profile` displaying the user's email, name, phone, and address.
- **FR-008**: System MUST allow users to update their profile data from the `/account/profile` view.
- **FR-009**: System MUST clear the stored token and redirect to `/login` if any protected API call returns a `401 Unauthorized` response.
- **FR-010**: System MUST clear the stored token and redirect to `/login` when the user initiates a logout action.

### Key Entities

- **User**: Represents the authentication identity. Contains email and password credentials.
- **Profile**: Represents the user's personal information. Contains name, phone, and address. Linked to a User.
- **JWT Token**: The authentication artifact used to authorize API requests.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of protected routes correctly redirect unauthenticated users to the login page.
- **SC-002**: 100% of public website routes (`uis/website/`) remain accessible without any authentication checks.
- **SC-003**: 100% of protected API calls include the `Authorization: Bearer` header when a token is present.
- **SC-004**: Users are automatically redirected to login when a `401` response is received from the API.
- **SC-005**: Users can view and successfully update their profile data.

## Assumptions

- The backend APIs are defined in `services/api/` and are already implemented and available.
- Specifically, the following endpoints are used:
  - `POST /users`: Accepts JSON payload (`email`, `password`, `name`, `phone`, `address`).
  - `POST /auth/login`: Uses OAuth2 password flow. Accepts `application/x-www-form-urlencoded` payload with `username` (which maps to the user's email) and `password`. Returns `access_token` and `token_type`.
  - `GET /auth/me`: Returns the authenticated user's info.
  - `PUT /profiles/me`: Accepts JSON payload to update profile fields.
- Token refresh mechanisms are out of scope for this iteration (a simple 401 redirect is sufficient).
- A unified layout or wrapper component is an acceptable client-side mechanism for route protection in the Next.js applications.
