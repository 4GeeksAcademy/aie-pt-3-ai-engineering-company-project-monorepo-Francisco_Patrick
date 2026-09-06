# Feature Specification: supplier-api

**Feature Branch**: `[001-supplier-api-uis-backoffice]`

**Created**: 2026-08-31

**Status**: Draft

**Input**: User description: "$ARGUMENTS"

## Clarifications

### Session 2026-09-06

- Q: Should the new `supplier-api` and Backoffice UI require explicit user authentication (e.g., JWT, OAuth), or is access controlled at the network level? → A: Network level (no app-level auth needed for this MVP)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Registering a New Carrier/Supplier (Priority: P1)

As an Operations Manager (like Carlos Vega or Ana Whitfield), I need to register new carriers/suppliers into the system so that TrackFlow can assign shipments to them and track costs accurately.

**Why this priority**: Essential foundation to allow TrackFlow to manage its network of 8+ carriers (UPS, FedEx, DHL, MRW, SEUR, etc.) in the US and Spain.

**Independent Test**: Can be fully tested by sending a POST request to `/suppliers` with a valid supplier payload (including name, country, rate "cost_per_kg", and product categories) and verifying that a `201/200` response with a valid TinyDB ID is returned.

**Acceptance Scenarios**:

1. **Given** a valid payload for a new carrier with a positive rate (`cost_per_kg`), **When** sending a POST to `/suppliers`, **Then** the system creates the record, generates an `updated_at` timestamp, returns the complete object with its ID, and saves it in TinyDB.
2. **Given** a payload with an invalid status (e.g., "inactive" instead of "suspended") or a negative/zero rate, **When** sending a POST to `/suppliers`, **Then** the system rejects it with a `422` error before reaching the database.

---

### User Story 2 - Querying and Filtering Carriers (Priority: P1)

As a Logistics Coordinator, I need to list all carriers or filter them by country or category so that I can decide which carrier is optimal for an outgoing shipment.

**Why this priority**: Necessary for the manual or automated "motor de selección de transportista" to find valid carriers for a specific shipment destination.

**Independent Test**: Can be tested by seeding the database and sending GET requests to `/suppliers` with and without query parameters.

**Acceptance Scenarios**:

1. **Given** a populated database, **When** calling `GET /suppliers` without parameters, **Then** all carriers are returned.
2. **Given** a populated database, **When** calling `GET /suppliers?country=Spain`, **Then** only carriers operating in Spain (e.g., MRW, SEUR) are returned.
3. **Given** a populated database, **When** calling `GET /suppliers?category=express`, **Then** only carriers handling that product category are returned.

---

### User Story 3 - Updating Carrier Rates and Status (Priority: P2)

As a Logistics Coordinator, I need to update the rate (cost_per_kg) or status (active/suspended) of a carrier so that the system reflects current contractual agreements and operational availability.

**Why this priority**: Carrier rates change and carriers may temporarily be suspended due to performance issues.

**Independent Test**: Can be tested by updating a specific carrier's rate or status via the PATCH endpoints and verifying the updated record.

**Acceptance Scenarios**:

1. **Given** an existing carrier, **When** a `PATCH /suppliers/{id}/rate` request is sent with a new positive rate, **Then** the rate is updated, and the `updated_at` timestamp is automatically refreshed.
2. **Given** an existing carrier, **When** a `PATCH /suppliers/{id}/status` request is sent with "suspended", **Then** the status is updated.
3. **Given** an existing carrier, **When** a `PATCH` request contains invalid data (negative rate or unrecognized status), **Then** a `422` error is returned.

---

### User Story 4 - Backoffice Supplier Directory (Priority: P1)

As an Operations Manager, I need a visual directory of suppliers in the backoffice application to manage their data, rates, and statuses without using an API client.

**Why this priority**: Required for non-technical staff to interact with the supplier data efficiently.

**Independent Test**: Can be tested by navigating the backoffice UI, interacting with the directory, adding new suppliers, updating rates/statuses, and applying filters.

**Acceptance Scenarios**:

1. **Given** a user navigates to the supplier directory in the backoffice, **Then** they see a table/list with supplier name, country, categories, rate (cost_per_kg), and status, with active/suspended statuses visually differentiated (e.g., badges).
2. **Given** the directory view, **When** a user applies filters by country or category, **Then** the list updates without page reload.
3. **Given** the directory view, **When** a user submits the new supplier form, **Then** a `POST /suppliers` request is made and the list updates, or a visible error message is shown if the API rejects it.
4. **Given** the directory view, **When** a user changes a supplier's rate (`cost_per_kg`) or status (activate/suspend), **Then** the UI makes the respective `PATCH` request and reflects the change immediately.

---

### Edge Cases

- What happens when a user attempts to update or delete a non-existent carrier ID? Returns `404 Not Found`.
- How does the system handle concurrent updates to the same carrier? (TinyDB handles basic file locks, but might face issues with high concurrency).
- What happens if the `uv run seed` script is executed multiple times? It verifies existing data to prevent duplicate entries.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a `POST /suppliers` endpoint to create a supplier with fields: name, country, product categories, rate (cost_per_kg), status, and auto-generated `updated_at`.
- **FR-002**: System MUST validate that the rate is strictly positive (> 0) and reject zero or negative values with `422`.
- **FR-003**: System MUST validate that the status only accepts predefined values: "active" or "suspended".
- **FR-004**: System MUST provide a `GET /suppliers` endpoint supporting optional query parameters `country` and `category` for filtering.
- **FR-005**: System MUST provide a `GET /suppliers/{id}` endpoint that returns a specific supplier or `404` if not found.
- **FR-006**: System MUST provide `PATCH /suppliers/{id}/rate` and `PATCH /suppliers/{id}/status` endpoints, updating `updated_at` on modification.
- **FR-007**: System MUST provide a `DELETE /suppliers/{id}` endpoint, returning `404` if the ID doesn't exist.
- **FR-008**: System MUST include a `seed.py` script executable via `uv run seed` that preloads initial carriers from CONTEXT.md (e.g., UPS, FedEx, MRW) without creating duplicates, printing the insertion count to the console.
- **FR-009**: The backoffice MUST include a Supplier Directory page accessible via the main menu.
- **FR-010**: The Supplier Directory MUST display suppliers in a table or list showing name, country, categories, rate (cost_per_kg), and status.
- **FR-011**: The Supplier Directory MUST provide client-side or AJAX filtering by country and category without full page reloads.
- **FR-012**: The Supplier Directory MUST include a form to create a new supplier calling `POST /suppliers`, handling validation errors gracefully.
- **FR-013**: The Supplier Directory MUST allow updates for a supplier's `cost_per_kg` and `status` from the UI, calling the respective `PATCH` endpoints and updating the view instantly.
- **FR-014**: The Supplier Directory MUST visually distinguish between "active" and "suspended" statuses using colored badges or distinct styling.
- **FR-015**: The system assumes network-level security (e.g., VPN/VPC) and MUST NOT implement application-level authentication for this MVP.

### Key Entities

- **Supplier (Carrier)**: Represents a logistics partner. Attributes include ID (assigned by TinyDB), Name (e.g., FedEx, SEUR), Country (e.g., United States, Spain), Product Categories (array of supported categories), Rate / cost_per_kg (positive float), Status (Enum: active/suspended), and updated_at (timestamp).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `uv run seed` executes without errors and outputs the exact number of inserted records, generating no duplicates on subsequent runs.
- **SC-002**: 100% of invalid data payloads (negative rates, invalid statuses) are rejected with a `422` error code before reaching the database.
- **SC-003**: Filtering `GET /suppliers` by country or category returns the correctly filtered subsets within 200ms.
- **SC-004**: The backoffice Supplier Directory correctly renders and filters suppliers without page reloads.
- **SC-005**: All Create and Update operations in the UI successfully reflect in the backend database and update the UI state.
- **SC-006**: Suspended and Active suppliers are clearly distinguishable visually.

## Assumptions

- TinyDB is used as the underlying storage mechanism as requested (lightweight storage).
- The terms "Supplier" and "Proveedor" in the request correspond to the "Transportistas" (carriers) mentioned in the TrackFlow CONTEXT.md, since TrackFlow is a logistics company managing carriers (UPS, FedEx, MRW, SEUR, etc.), and the required rate field matches "coste por kg".
- The valid statuses are explicitly "active" and "suspended" based on the user's prompt.
- The base language for the API URLs is English (`/suppliers`), and data models MUST use English terms exclusively.
