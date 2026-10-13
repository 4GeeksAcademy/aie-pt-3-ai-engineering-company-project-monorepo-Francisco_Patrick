# Feature Specification: Centralized Incident Manager - Backend

**Feature Branch**: `006-centralized-incident-manager-backend`

**Created**: 2026-09-13

**Status**: Draft

**Input**: User description: "Centralized Incident Manager - Backend Management API & Lifecycle State Machine"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Incident Lifecycle & Status State Machine (Priority: P1)

As an Operations Coordinator, I want to update an incident's status following strict lifecycle rules (`open` -> `in_progress`/`discarded`, `in_progress` -> `resolved`/`discarded`, terminal states `resolved`/`discarded`), so that incidents progress logically through operational stages without invalid state jumps or unauthorized modifications once resolved or discarded.

**Why this priority**: Correct lifecycle state management prevents invalid operational workflows and ensures reports accurately reflect work state.

**Independent Test**: Transitioning an incident from `open` to `in_progress` succeeds, while attempting an invalid transition (e.g. `open` directly to `resolved` or `resolved` to `open`) is rejected with a clear error message.

**Acceptance Scenarios**:

1. **Given** an incident in state `open`, **When** requesting a status update to `in_progress` or `discarded`, **Then** the status is updated and saved.
2. **Given** an incident in state `in_progress`, **When** requesting a status update to `resolved` or `discarded`, **Then** the status is updated and saved.
3. **Given** an incident in state `resolved` or `discarded`, **When** requesting any status transition, **Then** the system rejects the update because terminal states cannot be modified.
4. **Given** an incident in state `open`, **When** attempting a transition directly to `resolved`, **Then** the system rejects the update as an invalid lifecycle transition.

---

### User Story 2 - Incident Creation & Field Validation (Priority: P2)

As a Customer Support / Operations Agent, I want to submit new incident reports with full field validation, so that bad, blank, or malformed data is rejected immediately with human-readable error messages identifying the exact invalid field.

**Why this priority**: High data quality prevents corrupt records from entering operational pipelines and provides clear guidance to agents when submitting forms.

**Independent Test**: Submitting a valid incident report creates the record; submitting a report with missing required fields or invalid enums returns HTTP 400 with a clean JSON payload highlighting the problematic field.

**Acceptance Scenarios**:

1. **Given** a valid incident payload (title, description, category, status, origin, branch), **When** submitting creation request, **Then** the incident is created and returned with unique ID and timestamps.
2. **Given** an incident submission with missing required fields or invalid enum values, **When** submitting creation request, **Then** the system returns HTTP 400 with field-specific error details.

---

### User Story 3 - Filtering, Detail Lookup & Operational Summary (Priority: P3)

As an Executive / Operations Manager, I want to query incidents with multi-attribute filters (`status`, `origin`, `branch`, `category`), retrieve individual incident details, and view summary metrics across all operational dimensions, so that I have complete visibility into system performance even when database records are sparse or empty.

**Why this priority**: Filtering and comprehensive summary metrics allow operations teams to track regional workloads and performance KPIs effectively.

**Independent Test**: Querying list endpoints with filters returns matching records; requesting `/summary` on an empty database returns zeroed metrics without crashing.

**Acceptance Scenarios**:

1. **Given** stored incidents, **When** requesting list of incidents with filters (e.g., `origin=customer`, `branch=zaragoza`), **Then** only matching incidents are returned.
2. **Given** an incident ID, **When** requesting incident detail for an existing ID, **Then** full details are returned; if ID does not exist, HTTP 404 is returned.
3. **Given** an empty or populated database, **When** requesting summary metrics, **Then** totals by `status`, `category`, `origin`, and `branch` are returned accurately without failure.

---

### Edge Cases

- What happens when a request attempts to update the status of a non-existent incident ID? System returns HTTP 404 with a descriptive message.
- What happens when an unhandled server error occurs? System returns HTTP 500 with a generic message, hiding raw stack traces.
- What happens when list or summary endpoints are queried on a brand-new, empty database? System returns HTTP 200 with an empty list `[]` or zeroed metric structure (`total_incidents: 0`, empty/zero breakdown maps).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an Incident Creation capability (`POST /api/incidents`) that validates all required fields (`title`, `description`, `category`, `status`, `origin`, `branch`) and returns HTTP 400 with field-specific plain language error messages for invalid or missing inputs.
- **FR-002**: System MUST provide an Incident List capability (`GET /api/incidents`) supporting optional query filter parameters: `status`, `origin`, `branch`, and `category`.
- **FR-003**: System MUST provide an Incident Detail capability (`GET /api/incidents/{id}`) returning 404 Not Found if the requested incident ID does not exist.
- **FR-004**: System MUST provide a Status Transition capability (`PATCH /api/incidents/{id}/status`) enforcing lifecycle state transitions:
  - `open` -> `in_progress` or `discarded`
  - `in_progress` -> `resolved` or `discarded`
  - `resolved` and `discarded` are terminal states and MUST NOT accept any status transitions.
- **FR-005**: Status transitions outside allowed lifecycle rules MUST be rejected with HTTP 400 and an explanatory error message.
- **FR-006**: System MUST provide an Aggregated Metrics capability (`GET /api/incidents/summary`) returning total counts grouped by `status`, `category`, `origin`, and `branch`.
- **FR-007**: Summary and list endpoints MUST handle empty databases gracefully without error, returning zeroed metrics or empty collections.
- **FR-008**: System MUST catch all unhandled exceptions and return HTTP 500 with a generic user message, ensuring zero raw stack traces leak to clients.

### Key Entities

- **Incident**:
  - `id`: Unique identifier
  - `title`: Non-empty title
  - `description`: Non-empty description
  - `category`: Enum (`warehouse`, `reverse_logistics`, `last_mile`, `customer_experience`)
  - `status`: Enum (`open`, `in_progress`, `resolved`, `discarded`)
  - `origin`: Enum (`customer`, `branch`, `internal`)
  - `branch`: Branch identifier (e.g., `los_angeles`, `zaragoza`, `central`)
  - `created_at`: Datetime
  - `updated_at`: Datetime

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of invalid status transition requests are rejected with HTTP 400 error responses.
- **SC-002**: 100% of validation errors return HTTP 400 JSON payloads identifying the problematic field name.
- **SC-003**: Zero unhandled error stack traces are exposed across all API error responses.
- **SC-004**: Incident summary endpoint returns 100% accurate metrics across 4 dimensions (`status`, `category`, `origin`, `branch`), including zeroed metrics on empty databases.
- **SC-005**: Incident filtering returns 100% accurate matching subsets for any combination of `status`, `origin`, `branch`, and `category` parameters.

## Assumptions

- Incident persistence is managed via the monorepo backend service (`services/api`).
- Standard ISO-8601 timestamps are updated automatically on status modification (`updated_at`).
- Existing seed data from Part I provides initial customer incidents for validation.
