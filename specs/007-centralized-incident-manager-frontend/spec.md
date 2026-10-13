# Feature Specification: Centralized Incident Manager - Frontend

**Feature Branch**: `007-centralized-incident-manager-frontend`

**Created**: 2026-09-13

**Status**: Draft

**Input**: User description: "Feature: Centralized Incident Manager - Frontend. Create an incident registration page, incident list panel with filters, inline status updating, resilient error handling, empty state handling, and summary metrics panel under uis/backoffice, sharing validation logic in packages/shared."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Incident Registration Form & Client Validation (Priority: P1) 🎯 MVP

As an operations manager or branch staff member, I want to register a new operational incident through a guided web form with immediate validation, so that operational issues are recorded reliably even when offline or experiencing network errors.

**Why this priority**: Incident creation is the primary data entry interface replacing manual file manipulation. Delivering a resilient form ensures data integrity and immediate operational entry.

**Independent Test**: Can submit valid incidents and receive confirmation; invalid inputs display field-specific error messages without submitting; API network/server errors display friendly error messages without raw technical traces or page crashes.

**Acceptance Scenarios**:

1. **Given** an operator navigating to the incident registration page, **When** they view the form, **Then** all model fields (`title`, `description`, `category`, `status`, `origin`, `branch`) are displayed, and `branch` is required with all available options including `central` (labeled per context).
2. **Given** the registration form, **When** the user selects `origin` as `branch`, **Then** the `branch` field is visually highlighted to emphasize location selection.
3. **Given** an operator submitting an incident, **When** the submit button is clicked, **Then** client-side validation runs; if valid, the submit button is disabled and a loading indicator is displayed while the API call completes.
4. **Given** a form submission returning an API error, **When** the response is received, **Then** the form remains intact, displays a clear plain-language error message, and if field-specific, highlights the offending field.
5. **Given** a successful incident creation response, **When** completed, **Then** the form fields clear and a confirmation message is displayed.

---

### User Story 2 - Resilient Incident List Panel & Inline Status Updates (Priority: P2)

As a supervisor or auditor, I want to view all registered incidents with multi-attribute filtering and perform inline status transitions directly from the list, so that I can manage incident resolution workflows efficiently.

**Why this priority**: Incident resolution requires real-time list monitoring, status updates, and resilient filter controls to track ongoing operational issues.

**Independent Test**: Can filter incidents by status, origin, and branch; can update status directly from list; failed status updates notify the user and revert visual state to previous value without corrupting UI state.

**Acceptance Scenarios**:

1. **Given** an auditor viewing the incident list, **When** data is loading, **Then** a clear loading indicator is displayed.
2. **Given** an empty list or filter combination with zero matching incidents, **When** rendered, **Then** an informative empty state message is shown rather than an uncontextualized empty table.
3. **Given** a list request that fails due to server/network error, **When** rendering fails, **Then** a friendly error banner with a "Retry" button is displayed without breaking the page layout.
4. **Given** an incident item in the list, **When** the user changes its status via the inline dropdown, **Then** an optimistic update or loader occurs; if the API call fails, the dropdown visually reverts to its prior status and displays a toast/banner alert.

---

### User Story 3 - Operational Summary Metrics Panel (Priority: P3)

As an executive or regional director, I want to view high-level metric summaries (by status, category, origin, branch), so that I can assess overall operational health at a glance.

**Why this priority**: Aggregated insights complement detail-level management and provide operational overview without impacting core incident registration workflows.

**Independent Test**: Summary metrics display correct counts across status, category, origin, and branch; summary loading or error states degrade gracefully without crashing or blocking the rest of the page.

**Acceptance Scenarios**:

1. **Given** the summary panel, **When** data is fetched from `/api/incidents/summary`, **Then** metrics by status, category, origin, and branch are rendered.
2. **Given** a summary request that is slow or fails, **When** loading or error state occurs, **Then** the summary panel displays a localized skeleton loader or fallback message without affecting the incident list or registration form.

---

### Edge Cases

- **Network disconnect during form submission**: Form retains filled values, re-enables submit button, and displays a retry message.
- **Empty database state**: Summary panel shows zero totals across all categories without NaN errors; list panel displays an informative empty state.
- **Concurrent status update failure**: Inline status dropdown reverts to previous server state and alerts user of conflict or failure.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an Incident Registration page accessible from the application navigation menu in `uis/backoffice`.
- **FR-002**: The registration form MUST include `title`, `description`, `category`, `status`, `origin`, and `branch`.
- **FR-003**: The `branch` dropdown MUST always be visible, required, and include options for all branches including `central`.
- **FR-004**: System MUST visually highlight the `branch` selection field whenever `origin` is set to `branch`.
- **FR-005**: System MUST perform client-side validation for required fields before submitting to the backend API.
- **FR-006**: System MUST disable the submit button and show a visual loading spinner while an incident creation request is in progress.
- **FR-007**: System MUST map server/API errors to plain-language, user-friendly messages next to problematic fields or in a prominent alert banner, never displaying raw stack traces or technical exception dumps.
- **FR-008**: System MUST clear the form inputs and display a confirmation notice upon successful incident creation.
- **FR-009**: System MUST display an Incident Listing panel with filter controls for `status`, `origin`, and `branch`.
- **FR-010**: System MUST handle loading, error (with retry button), and empty states gracefully in the incident listing panel.
- **FR-011**: System MUST allow inline status updates on incident list items. If the server update fails, the UI MUST revert the dropdown to its prior value and notify the user.
- **FR-012**: System MUST render an Operational Summary panel displaying aggregated metrics (`by_status`, `by_category`, `by_origin`, `by_branch`).
- **FR-013**: The Summary panel MUST handle slow loading or server errors isolated to its own container without breaking adjacent UI components.
- **FR-014**: Common validation schemas MUST be extracted into `packages/shared/` to allow shared usage across backend, scripts, and frontend without code duplication.

### Key Entities

- **Incident Form State**: Transient state tracking title, description, category, status, origin, branch, validation errors, and submission status.
- **Incident Filter State**: Active selection state for status, origin, and branch filters applied to the incident list.
- **Incident Metric Summary**: Aggregated counts returned from `/api/incidents/summary` partitioned across 4 dimensions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of invalid form submissions are caught client-side with clear field validation warnings before making an API network call.
- **SC-002**: Zero raw technical server error strings or stack traces are displayed to end-users across all error scenarios.
- **SC-003**: 100% of failed inline status updates cleanly revert to their previous visual state without page reload or state corruption.
- **SC-004**: Summary panel or incident list failures never break or unmount adjacent page layout elements.

## Assumptions

- Frontend app is built in `uis/backoffice` using Next.js / React with standard component architecture and CSS / Tailwind styling.
- Backend API endpoints (`POST /api/incidents`, `GET /api/incidents`, `GET /api/incidents/{id}`, `PATCH /api/incidents/{id}/status`, `GET /api/incidents/summary`) are available under the configured base API URL.
- Shared validation logic is placed in `packages/shared/`.
