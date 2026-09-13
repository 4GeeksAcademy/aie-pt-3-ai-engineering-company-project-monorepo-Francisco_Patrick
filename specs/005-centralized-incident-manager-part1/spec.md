# Feature Specification: Centralized Incident Manager - Part I

**Feature Branch**: `005-centralized-incident-manager-part1`

**Created**: 2026-09-13

**Status**: Draft

**Input**: User description: "Centralized Incident Manager - Part I: Data Model & Historical Data Seed"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Historical Data Seeding (Priority: P1)

As an Operations & Incident Manager, I want historical customer incident records loaded into the centralized incident database from the legacy CSV file, so that real customer incident data is available from day one with correct status, category, and branch attributes.

**Why this priority**: Without historical seed data, the incident management system starts empty, preventing reporting continuity and operational analysis.

**Independent Test**: Running the seed procedure populates the centralized storage with valid historical records marked with origin "customer", applying status and category transformations correctly.

**Acceptance Scenarios**:

1. **Given** a legacy CSV containing historical incident records, **When** the seeding script executes, **Then** all valid records are transformed and inserted into the incident database with origin set to `customer`.
2. **Given** a legacy CSV containing invalid or corrupt rows, **When** the seeding script executes, **Then** invalid rows are excluded from insertion and reported to the console with clear failure details.
3. **Given** historical data has already been seeded, **When** the seeding script is executed a second time, **Then** no duplicate incident records are created in the database.

---

### User Story 2 - Incident Data Integrity & Constraints (Priority: P2)

As a System Administrator, I want all incident records governed by strict field validation and allowed enum constraints, so that bad, incomplete, or corrupted data cannot enter the incident management lifecycle.

**Why this priority**: High data quality and consistency are essential for reliable aggregations, operational routing, and summary dashboards.

**Independent Test**: Attempting to store or transform incident records with invalid statuses, origins, or categories fails validation and returns structured error details.

**Acceptance Scenarios**:

1. **Given** an incident creation request with missing required fields (title, description, category, status, origin, branch), **When** validation evaluates the record, **Then** the record is rejected with user-understandable validation messages.
2. **Given** an incident record with invalid field values (e.g. status outside `open`, `in_progress`, `resolved`, `discarded`), **When** validation evaluates the record, **Then** insertion is prevented.

---

### User Story 3 - Operational Incident Summary & Metrics (Priority: P3)

As an Executive / Operations Director, I want summary metrics by incident status and category via a summary endpoint, so that I can monitor incident distributions after historical seeding and ongoing operations.

**Why this priority**: Aggregated metrics provide immediate visibility into incident volumes across operational areas and resolution states.

**Independent Test**: Querying the summary endpoint after seeding returns totals by status and category matching expected transformed counts from historical data.

**Acceptance Scenarios**:

1. **Given** seeded incident data in the database, **When** requesting the incident summary metrics, **Then** totals broken down by status and category are returned matching historical valid dataset metrics.

---

### Edge Cases

- What happens when a CSV record contains an unknown status or category value? It is flagged as invalid, excluded from database insertion, and reported in the console error log.
- What happens when the seed script is interrupted mid-execution? Idempotency mechanisms ensure subsequent runs resume without duplicating previously inserted records.
- What happens when branch information is missing in a customer incident? The branch is automatically mapped to `central`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST maintain an Incident data model containing `id`, `title`, `description`, `category`, `status`, `origin`, `branch`, `created_at`, and `updated_at`.
- **FR-002**: System MUST enforce that `title`, `description`, `category`, `status`, `origin`, and `branch` are required fields for every incident.
- **FR-003**: System MUST restrict `status` to allowed values: `open`, `in_progress`, `resolved`, and `discarded`.
- **FR-004**: System MUST restrict `origin` to allowed values: `customer`, `branch`, and `internal`.
- **FR-005**: System MUST restrict `category` to valid TrackFlow operational categories: `warehouse`, `reverse_logistics`, `last_mile`, and `customer_experience`.
- **FR-006**: System MUST assign default branch `central` for incidents not tied to a specific operational branch.
- **FR-007**: System MUST automatically generate unique identifiers (`id`) and timestamps (`created_at`, `updated_at`) for incidents.
- **FR-008**: System MUST provide a command-line seeding utility to ingest historical CSV incident records into the database.
- **FR-009**: The seeding utility MUST assign `origin: "customer"` to all imported historical CSV records.
- **FR-010**: The seeding utility MUST transform legacy CSV fields to the Incident model schema before insertion (mapping legacy `description` to `title`, `date` to `created_at`, location to `branch`, legacy status `closed` to `resolved`).
- **FR-011**: The seeding utility MUST reuse shared validation logic to reject invalid CSV rows and output diagnostic summaries of invalid rows to the console.
- **FR-012**: The seeding utility MUST be idempotent, preventing duplicate records when executed multiple times.
- **FR-013**: System MUST provide an Incident Summary endpoint returning aggregated totals grouped by `status` and `category`.
- **FR-014**: System MUST return user-comprehensible error messages instead of unhandled server stack traces during validation failures or API errors.

### Key Entities

- **Incident**: Represents a customer, branch, or internal operational report requiring tracking and resolution.
  - `id`: String (Unique identifier)
  - `title`: String (Brief summary title)
  - `description`: String (Detailed description)
  - `category`: Enum (`warehouse`, `reverse_logistics`, `last_mile`, `customer_experience`)
  - `status`: Enum (`open`, `in_progress`, `resolved`, `discarded`)
  - `origin`: Enum (`customer`, `branch`, `internal`)
  - `branch`: String (Branch identifier or `central`)
  - `created_at`: Datetime (Creation timestamp)
  - `updated_at`: Datetime (Last modification timestamp)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of valid historical CSV records are loaded with origin `customer` upon initial seed script completion.
- **SC-002**: Seeding script execution is 100% idempotent; running it multiple times yields zero duplicate records in database.
- **SC-003**: 100% of invalid CSV rows are correctly flagged, excluded from database insertion, and listed in terminal execution summary.
- **SC-004**: Post-seeding incident summary metrics by status and category match transformed expected historical figures exactly.
- **SC-005**: Zero unhandled error stack traces are exposed to users during validation failures or error conditions.

## Assumptions

- Historical CSV source file is located in the project's standard script asset path (`scripts/incidents-COMPANY.csv`).
- Legacy status `closed` maps to lifecycle status `resolved` in the centralized incident model.
- Location values in the CSV map to branch identifiers, defaulting to `central` when non-specific.
- Shared validation routines reside in `shared/` / `packages/shared/` for reuse between CLI scripts and backend API services.
