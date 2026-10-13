# Research & Technical Decisions: Backoffice Inventory Management Interface

## Overview
This document records technical research, architectural decisions, and design patterns for implementing the inventory management UI section in `uis/backoffice`.

---

## Technical Decisions & Rationale

### 1. Centralized API Client Module (`lib/inventory.ts`)

- **Decision**: Create a dedicated TypeScript module `uis/backoffice/lib/inventory.ts` that exports strongly typed async functions for all `/inventory` API endpoints using the existing `fetchWithAuth` utility from `uis/backoffice/lib/api.ts`.
- **Rationale**:
  - Direct `fetch` calls in React components scatter endpoint URLs, token handling, header construction, and error extraction logic, making maintenance error-prone and breaking separation of concerns.
  - `fetchWithAuth` automatically handles reading the `auth_token` from `localStorage`, injecting `Authorization: Bearer <token>`, and invalidating/redirecting on `401 Unauthorized` responses.
  - Strong typing with explicit TypeScript interfaces prevents `any` types and enforces strict return type annotations as required by workspace rules.
- **Alternatives Considered**:
  - *Direct `fetch` inside components*: Rejected due to code duplication and violating the explicit requirement "No component should call `fetch` directly".
  - *Axios / React Query*: Rejected to avoid adding unnecessary external dependencies to Next.js backoffice when `fetchWithAuth` is already established in the codebase.

---

### 2. Route Protection Architecture

- **Decision**: Leverage the existing `AuthGuard` component (`uis/backoffice/components/AuthGuard.tsx`) wrapped in `RootLayout` (`uis/backoffice/app/layout.tsx`), while adding explicit client-side session checks in inventory pages to guarantee zero unauthorized access.
- **Rationale**:
  - `AuthGuard` checks `isAuthenticated()` (which verifies presence of `auth_token` in `localStorage`) and redirects non-authenticated users to `/login`.
  - Adding route checks on page mount provides redundant, fail-safe protection.
- **Alternatives Considered**:
  - *Next.js Middleware*: While middleware is possible, the project's existing auth model relies on client-side `localStorage` tokens. Standardizing on `AuthGuard` keeps auth consistent with `/incidents`, `/account`, and `/suppliers`.

---

### 3. Visual Stock Level Indicator Thresholds

- **Decision**:
  - **Healthy Stock (Green)**: `current_stock > low_stock_threshold`
  - **Low Stock (Amber/Orange)**: `0 < current_stock <= low_stock_threshold`
  - **Out of Stock (Red)**: `current_stock === 0`
- **Rationale**:
  - Providing three distinct visual states (Green / Amber / Red) gives operational staff at 7am an immediate, unambiguous snapshot of inventory health without calculating thresholds manually.
  - Threshold values are dynamically derived per product from `low_stock_threshold` (defaulting to 10 if unspecified by API).

---

### 4. Outbound Form Reactive Stock Fetching & Inline Error Handling

- **Decision**:
  - When the user selects a product in the outbound order form (`/inventory/orders/outbound`), the component immediately triggers `getInventoryProductById(skuId)` or matches the pre-fetched products list to update `current_stock`.
  - An inline UX warning banner is rendered under the quantity input when `quantity > current_stock`.
  - If the backend returns `400 Bad Request` (e.g., `Insufficient stock for SKU...`), the component captures the error message from `ApiServerError` / `detail` and displays it in an inline error alert box adjacent to the quantity field.
- **Rationale**:
  - Reactive feedback prevents users from submitting invalid stock exit requests.
  - Inline error rendering directly near the input field satisfies operational UX requirements ("zero patience for broken forms or cryptic error messages").

---

### 5. Domain Language & Vocabulary Alignment

- **Decision**: Use TrackFlow domain terminology defined in `CONTEXT.md`:
  - `SKU`: Product entity identifier code (e.g., `SKU-LA-001`, `SKU-ZGZ-042`).
  - Warehouses: `wh-la` (Los Angeles Warehouse) and `wh-zgz` (Zaragoza Warehouse).
  - Stock Entries / Exits: Inbound delivery vs Outbound exit/consumption.
  - User Identifier: `user_uuid`.
- **Rationale**: Aligns UI labels with physical warehouse operations in Los Angeles and Zaragoza.
