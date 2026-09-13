# Feature Specification: Comprehensive Error Handling

**Feature Branch**: `008-error-handling`

**Created**: 2026-09-13

**Status**: Draft

**Input**: User description: "Comprehensive error handling quality across Next.js frontend in uis/, FastAPI backend in services/api/, and Python scripts in scripts/ based on findings in audit.md."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Resilient Frontend Data Fetching & 3-State UI (Priority: P1)

As a TrackFlow Backoffice user or Administrator, I want all data-fetching views (such as Suppliers, Incidents, and Profile) to gracefully display loading indicators, clear human-readable error messages with retry buttons, and safe fallback values so that network drops or server errors never leave me stuck with blank screens or crashed interfaces.

**Why this priority**: Directly impacts user experience and application stability. Prevents unhandled JavaScript exceptions, infinite loading spinners, and unrecoverable error states across all frontend modules.

**Independent Test**: Can be tested by disconnecting network connectivity or mocking API failure (500/404) when visiting the Suppliers, Incidents, or Profile views, verifying that a loading skeleton appears, followed by a human-readable error banner with a functional "Retry" button.

**Acceptance Scenarios**:

1. **Given** a user is loading a page that fetches data (e.g., Suppliers or Profile), **When** the request is in flight, **Then** a localized loading spinner or skeleton UI is displayed and interactive elements are safely disabled.
2. **Given** an async data request fails due to network or server error, **When** the error state is reached, **Then** the loading state is cleared via `finally`, a human-readable error explanation (without raw status codes or stack traces) is rendered, and a clear call to action (e.g. "Retry" button or "Back to Home" link) is provided.
3. **Given** an unauthenticated user navigates to `/forgot-password` or `/reset-password`, **When** `AuthGuard` evaluates the route, **Then** the page is recognized as a public route and renders the password recovery form immediately instead of redirecting to `/login`.
4. **Given** an API response returns missing or `null` nested fields, **When** rendering UI components, **Then** optional chaining (`?.`) and fallback default values prevent UI crashes.

---

### User Story 2 - Secure & Structured Backend API Error Handling (Priority: P2)

As an API client or integration service, I want all FastAPI endpoints to return clean, structured JSON error objects with standard HTTP status codes (400, 404, 422, 500) and zero sensitive information leaks so that errors are predictable and internal secrets are protected.

**Why this priority**: Crucial for security, data privacy, and robust integration. Eliminates raw Python exception leaks (`str(e)`), plaintext password token logging, and unhandled database crashes.

**Independent Test**: Can be tested by sending malformed payloads, invalid IDs, or forcing database/third-party API errors against `/api/incidents/analyze`, `/suppliers`, and `/auth/forgot-password`, verifying that all responses return structured JSON with appropriate HTTP status codes without internal paths, stack traces, or secrets.

**Acceptance Scenarios**:

1. **Given** an invalid file format or internal error occurs during incident CSV analysis, **When** `/api/incidents/analyze` receives the request, **Then** it returns a structured JSON error response (`{"error": "Server Error", "message": "..."}`) with status code 500 without exposing raw Python exception details.
2. **Given** database operations occur inside supplier endpoints (`/suppliers`), **When** database access succeeds or fails, **Then** errors are caught at granular scope and returned with proper HTTP status codes rather than unhandled 500 crashes.
3. **Given** a user requests a password reset or email dispatch fails, **When** mock or production email handlers execute, **Then** plaintext reset URL tokens and user email addresses are never output to standard console logs or audit logs.

---

### User Story 3 - Robust & Safe Python CLI Script Execution (Priority: P3)

As a DevOps engineer or developer running command-line scripts (`scripts/analyze.py`, `scripts/seed_incidents.py`, `services/api/seed.py`), I want script operations (file I/O, CSV parsing, DB writes) to be defensively checked and wrapped in error handlers with non-zero exit codes on failure so that automated pipelines fail fast with actionable stderr diagnostic output.

**Why this priority**: Prevents silent script failures, incomplete database seeds, and script exits with code 0 upon process interruption or data corruption.

**Independent Test**: Can be tested by invoking `scripts/analyze.py` with a non-existent file, corrupted CSV, or sending `KeyboardInterrupt` (Ctrl+C), verifying that stderr receives clear error messages and the process exits with a non-zero exit status (`sys.exit(1)` or `sys.exit(130)`).

**Acceptance Scenarios**:

1. **Given** `analyze.py` or `seed_incidents.py` is executed with missing or malformed input files, **When** file I/O or CSV parsing fails, **Then** an informative error message is printed to `stderr` and the script exits with `sys.exit(1)`.
2. **Given** a user cancels script execution via Ctrl+C (`KeyboardInterrupt`), **When** the interrupt signal is trapped, **Then** the script logs a cancellation message to `stderr` and exits with exit code 130 instead of swallowing the exception with code 0.
3. **Given** `seed_incidents.py` processes a CSV dataset with some invalid rows, **When** row processing encounters errors, **Then** individual bad rows are logged and skipped without crashing the overall seeding pipeline.

---

### Edge Cases

- What happens when the network drops mid-request during form submission? The loading state is cleared via `finally`, an inline error banner is displayed, and the form remains pre-filled so user input is not lost.
- What happens when a third-party email service (Resend API) is unreachable? The backend logs a structured error internally, masks sensitive credentials, and returns a safe generic response to the user without breaking anti-enumeration rules.
- What happens when a CSV file processed by `analyze.py` contains invalid UTF-8 byte sequences? The script catches `UnicodeDecodeError`, outputs a descriptive message to `stderr`, and exits with code 1.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Frontend components MUST implement the 3-state UI pattern (loading, fulfilled, rejected) for all asynchronous data-fetching operations.
- **FR-002**: Frontend error views MUST render human-readable error messages and include a actionable Call to Action (e.g. Retry button, Back to Home link).
- **FR-003**: Frontend data fetching operations MUST use `finally` blocks to guarantee that loading states are cleared regardless of request outcome.
- **FR-004**: Frontend components MUST employ optional chaining (`?.`) and fallback default values (`?? default`) to prevent rendering crashes on `null` or `undefined` data.
- **FR-005**: `AuthGuard` MUST include public password recovery routes (`/forgot-password` and `/reset-password`) in `PUBLIC_PATHS` to prevent unauthenticated user access blocks.
- **FR-006**: Backend API route handlers MUST catch exceptions at granular scope and return structured JSON error payloads with standard HTTP status codes (400, 404, 422, 500).
- **FR-007**: Backend API responses and log outputs MUST NOT expose raw Python exception strings (`str(e)`), stack traces, secret keys, or plaintext PII (email addresses in audit logs or console output).
- **FR-008**: External service integrations (e.g., Resend email API) MUST be wrapped in error handling and log structured errors without swallowing failures or leaking raw credentials.
- **FR-009**: Python scripts MUST wrap file I/O, CSV parsing, and database seeding in `try/except` blocks and print descriptive messages to `stderr`.
- **FR-10**: Python scripts MUST issue explicit non-zero exit codes (`sys.exit(1)` on error, `sys.exit(130)` on `KeyboardInterrupt`) upon critical failure or process termination.

### Key Entities *(include if feature involves data)*

- **ErrorResponsePayload**: Standardized backend JSON response object containing `error` (category name), `message` (user-safe description), and optional structured `details` array.
- **AsyncUIState**: Frontend state interface containing `isLoading` (boolean), `data` (T | null), `error` (string | null), and `retry` (callback function).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of frontend async data-fetching components render a loading state during request flight and clear loading state in a `finally` block.
- **SC-002**: 100% of frontend error states display a human-readable message accompanied by at least one interactive Call to Action (Retry, Home, Support).
- **SC-003**: Zero API responses contain raw Python tracebacks, internal file system paths, or `str(e)` exception dump strings in client-facing payloads.
- **SC-004**: Zero log outputs contain plaintext secret reset tokens or unmasked email addresses.
- **SC-005**: 100% of Python scripts exit with a non-zero exit code (1 or 130) when encountering unrecoverable errors or interrupt signals.

## Assumptions

- Frontend styling uses existing Tailwind CSS utilities for loading spinners, skeletons, and error banners.
- Password reset token hashing and validation mechanisms remain compliant with security policies while hiding user enumeration signals.
- Existing database (TinyDB) schema structures remain intact while adding error handling boundaries.
