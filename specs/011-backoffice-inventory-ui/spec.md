# Feature Specification: Backoffice Inventory Management Interface

**Feature Branch**: `011-backoffice-inventory-ui`

**Created**: 2026-09-17

**Status**: Draft

**Input**: User description: "Backoffice: Inventory Management Interface - Build internal inventory management views (products listing, inbound delivery order form, outbound consumption order form, orders history ledger) for operations staff with centralized API client layer, reactive stock verification, visual stock status indicators, inline error handling, and complete route protection."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Live Product Inventory & Stock Level Indicators (Priority: P1)

As a warehouse operations manager or staff member at TrackFlow, I need to view real-time stock levels for all products across warehouses (Los Angeles `wh-la` and Zaragoza `wh-zgz`) with clear visual health indicators so that I can immediately spot items running low on stock and take swift action.

**Why this priority**: Operations staff rely on real-time stock visibility to maintain fulfillment capacity and avoid stockouts. Without this, warehouse staff cannot monitor inventory health or decide which products require replenishment.

**Independent Test**: Can be tested independently by logging into the backoffice as an authenticated user, navigating to `/backoffice/inventory/products`, verifying that product rows load live data from `GET /inventory/products` displaying SKU details, warehouse origin, stock counts, low-stock threshold badges, and direct order action links.

**Acceptance Scenarios**:

1. **Given** an authenticated operations user navigating to `/backoffice/inventory/products`, **When** the page loads, **Then** the system fetches product data via `GET /inventory/products` and renders each product showing SKU identifier, product name, warehouse ID (`wh-la` or `wh-zgz`), `current_stock`, and `low_stock_threshold`.
2. **Given** a product where `current_stock` is less than or equal to `low_stock_threshold`, **When** the product row is rendered, **Then** the stock level is visually distinguished as "Low Stock" (e.g., using amber/red badge styling or warning icons), whereas products above the threshold display a "Healthy Stock" (green) status indicator.
3. **Given** any product row in the listing, **When** the user clicks the "Create Inbound Order" or "Create Outbound Order" action link/button on that row, **Then** the user is navigated to the corresponding order form with the target product pre-selected.

---

### User Story 2 - Reactive Outbound Order Logging & Stock Guard (Priority: P2)

As a warehouse fulfillment worker, I need to log outbound stock exits (deliveries to transport carriers or stock consumption) with immediate, reactive visibility of available stock and inline validation warnings so that I do not attempt to dispatch stock that TrackFlow does not physically possess.

**Why this priority**: Preventing negative stock entry attempts at the UI layer speeds up warehouse workflow, reduces frustration at 7am shifts, and provides clear inline feedback when stock is insufficient.

**Independent Test**: Can be tested independently by selecting a product in `/backoffice/inventory/orders/outbound`, verifying that available `current_stock` reactively displays immediately, entering a quantity greater than stock to see a client-side warning, and observing inline API 400 error rendering if submitted against insufficient stock.

**Acceptance Scenarios**:

1. **Given** an authenticated user on the Outbound Order form (`/backoffice/inventory/orders/outbound`), **When** the user selects a product from the product dropdown list, **Then** the form reactively fetches and displays that product's `current_stock` count prior to quantity input.
2. **Given** a selected product with a known `current_stock` (e.g., 5 units), **When** the user enters a quantity greater than available stock (e.g., 10 units), **Then** the form immediately renders a prominent client-side warning element near the quantity field indicating that the order exceeds current stock.
3. **Given** an outbound order submission that fails on the server with a `400 Bad Request` (insufficient stock), **When** the API response is received, **Then** the UI surfaces the exact error message inline near the quantity input field rather than silently logging or using browser alerts.

---

### User Story 3 - Inbound Delivery Order Logging (Priority: P3)

As a warehouse receiving clerk, I need to register incoming supplier deliveries by selecting products by human-readable name and entering incoming stock quantities so that real-time stock levels are updated accurately upon stock intake.

**Why this priority**: Receiving inventory from suppliers (`wh-la` and `wh-zgz`) is essential for building and maintaining inventory levels. Clearing forms and providing visual success confirmations ensures clerks know their entry was recorded.

**Independent Test**: Can be tested independently by filling out `/backoffice/inventory/orders/inbound` with a valid product name and quantity, submitting the form, and confirming that the form clears with a success message and stock updates accordingly on the products view.

**Acceptance Scenarios**:

1. **Given** an authenticated user on the Inbound Order form (`/backoffice/inventory/orders/inbound`), **When** interacting with the product selector, **Then** products are listed by human-readable name and SKU code rather than requiring manual typing of raw system IDs.
2. **Given** a valid inbound order submission, **When** the request succeeds (`POST /inventory/orders/inbound`), **Then** the form fields reset to empty, and a clear visual confirmation banner displays the successful order receipt.
3. **Given** an inbound order submission that returns a server error (`400` or `500`), **When** the API responds, **Then** the form surfaces the API's detailed error message in a visible UI component on the page.

---

### User Story 4 - Audit-Ready Orders History Ledger (Priority: P4)

As an operations manager, I need to review a comprehensive, read-only history of all inbound and outbound stock operations, detailing quantities, creation timestamps, and responsible staff identifiers (`user_uuid`), so that TrackFlow maintains full traceability across warehouse operations.

**Why this priority**: Complete operational auditing allows management to verify stock entries and exits, investigate discrepancies, and track staff accountability.

**Independent Test**: Can be tested independently by navigating to `/backoffice/inventory/orders` as an authenticated user, verifying that all historical orders load from `GET /inventory/orders` in a read-only table with distinct visual badges for inbound vs. outbound movement.

**Acceptance Scenarios**:

1. **Given** an authenticated user navigating to `/backoffice/inventory/orders`, **When** the page loads, **Then** the system fetches and displays all orders from `GET /inventory/orders` in chronological order.
2. **Given** an order entry in the history table, **When** displayed, **Then** the row shows: product name, movement quantity, order type (`inbound` vs `outbound`), creation timestamp, and the `user_uuid` of the staff member who logged it.
3. **Given** inbound and outbound order rows in the table, **When** rendered, **Then** inbound and outbound entries are visually differentiated (e.g., green badge/icon for inbound stock additions, blue/amber badge for outbound stock exits).
4. **Given** the orders history page, **When** accessed by any user, **Then** no inline edit or delete actions are present (strict read-only audit ledger).

---

### Edge Cases

- **Expired or Missing Authentication Token**: If a user attempts to access any of the 4 inventory pages (`/products`, `/orders/inbound`, `/orders/outbound`, `/orders`) without a valid session token, the route protection mechanism must immediately redirect them to the `/login` route.
- **API Unavailability / Network Failure**: If the backend API returns a `5xx` error or network connectivity fails while fetching products or submitting orders, the frontend must display an explicit error alert with actionable error text, avoiding blank pages or silent failures.
- **Zero Stock Selection**: When selecting a product with `current_stock = 0` in the outbound order form, the UX guard must warn the user immediately upon entering any quantity greater than 0.
- **Rapid Product Switching**: If a user quickly switches between products in the outbound form product selector, previous pending async stock check requests must not overwrite the latest selected product's stock count.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: **Centralized API Integration Module**: System MUST encapsulate all `/inventory` API interactions inside a dedicated module (`lib/inventory.ts`). Components MUST NOT invoke `fetch` directly.
- **FR-002**: **Bearer Token Authorization**: System MUST append the `Authorization: Bearer <token>` header to all protected `/inventory` API HTTP requests, reading the token from the existing auth context/storage.
- **FR-003**: **Explicit API Error Handling**: The API client module MUST parse `4xx` and `5xx` HTTP responses, extract error message details (`detail` or `message`), and throw structured exceptions for components to render visibly.
- **FR-004**: **Live Products Listing**: System MUST render all inventory items from `GET /inventory/products` at `/backoffice/inventory/products`, showing SKU, product name, warehouse identifier (`wh-la`, `wh-zgz`), `current_stock`, and `low_stock_threshold`.
- **FR-005**: **Visual Stock Status Indicators**: System MUST visually distinguish product stock status using color-coded indicators (e.g., Healthy Stock when `current_stock > low_stock_threshold`, Low Stock when `current_stock <= low_stock_threshold`).
- **FR-006**: **Product Action Direct Links**: Products listing rows MUST include direct links/buttons to initiate inbound or outbound orders pre-populating the selected product.
- **FR-007**: **Inbound Order Submission**: System MUST provide a form at `/backoffice/inventory/orders/inbound` submitting to `POST /inventory/orders/inbound` with product dropdown displaying human-readable names and SKUs.
- **FR-008**: **Inbound Feedback & State Reset**: Upon successful inbound order submission, system MUST clear all input fields and display a clear confirmation notice. Upon server failure, system MUST display error text in a visible UI component.
- **FR-009**: **Reactive Outbound Stock Display**: The Outbound Order form at `/backoffice/inventory/orders/outbound` MUST reactively fetch and display `current_stock` immediately when a product is selected.
- **FR-010**: **Outbound Client-Side Stock Guard**: Outbound form MUST display a client-side warning banner if entered quantity exceeds displayed `current_stock`.
- **FR-011**: **Inline Outbound Error Display**: Server-returned `400 Bad Request` errors on outbound order submission MUST be rendered inline near the quantity input field.
- **FR-012**: **Read-Only Order History Ledger**: System MUST display all stock orders from `GET /inventory/orders` at `/backoffice/inventory/orders` showing product name, quantity, order type (`inbound`/`outbound`), creation timestamp, and `user_uuid`, with visual distinction between order types and zero modification capabilities.
- **FR-013**: **Route Protection**: All four backoffice inventory routes MUST redirect unauthenticated requests to `/login`.
- **FR-014**: **Domain Terminology Alignment**: All UI labels, headers, and entity names MUST strictly mirror TrackFlow domain language as defined in `CONTEXT.md` (e.g., warehouses `wh-la` / `wh-zgz`, SKUs, `user_uuid`).

### Key Entities

- **SKU / Product**: Represents a TrackFlow inventory product item stored in a specific warehouse (`wh-la` in Los Angeles or `wh-zgz` in Zaragoza). Attributes: `id`, `sku`, `name`, `warehouse_id`, `low_stock_threshold`, `current_stock`, `created_at`.
- **Inbound Stock Order (StockEntry)**: Represents an incoming delivery transaction increasing inventory count. Attributes: `id`, `sku_id`, `quantity`, `order_type` (`inbound`), `user_uuid`, `created_at`.
- **Outbound Stock Order (StockExit)**: Represents an outgoing delivery or consumption transaction decreasing inventory count. Attributes: `id`, `sku_id`, `quantity`, `order_type` (`outbound`), `user_uuid`, `created_at`.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: **Zero Direct Component Fetch Calls**: 100% of API requests to `/inventory` routes are dispatched through `lib/inventory.ts`, achieving zero direct `fetch` calls across all backoffice inventory page components.
- **SC-002**: **Rapid Operational Order Entry**: Operations staff can register an inbound delivery or outbound consumption order in under 15 seconds.
- **SC-003**: **Immediate Reactive Feedback**: Product selection in the outbound order form updates the displayed `current_stock` and triggers UX warnings in under 300 milliseconds.
- **SC-004**: **Comprehensive Error Visibility**: 100% of API error responses (`4xx` and `5xx`) produce visible, human-readable error notifications in the UI with zero unhandled promise rejections or silent failures.
- **SC-005**: **Total Route Protection**: 100% of unauthenticated attempts to access any inventory backoffice view are redirected to the login interface.

---

## Assumptions

- **Existing Authentication Infrastructure**: The backoffice frontend already possesses an authentication mechanism (context, localStorage, or cookie) that provides the current logged-in user's Bearer token and `user_uuid`.
- **Backend API Contract Availability**: The backend project exposes working endpoints for `GET /inventory/products`, `GET /inventory/orders`, `POST /inventory/orders/inbound`, and `POST /inventory/orders/outbound` accepting JSON payloads.
- **Domain Scope**: Inventory management in this interface focuses on stock tracking across `wh-la` (Los Angeles) and `wh-zgz` (Zaragoza) warehouses.
- **Browser Environment**: Target users operate standard desktop web browsers in warehouse computer setups with stable local network connections.
