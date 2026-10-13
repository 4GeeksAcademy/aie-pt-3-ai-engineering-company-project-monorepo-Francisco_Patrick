# Quickstart & Verification Guide: Backoffice Inventory Management Interface

## Overview
This document outlines runnable validation scenarios and automated test commands to verify the inventory management UI features end-to-end.

---

## Prerequisites & Local Setup

1. **Backend Service**: Ensure FastAPI backend is running on `http://localhost:8000`.
   ```bash
   cd services/api
   uv run uvicorn app:app --reload --port 8000
   ```

2. **Frontend Service**: Ensure Next.js backoffice app is running on `http://localhost:3000`.
   ```bash
   cd uis/backoffice
   npm run dev
   ```

---

## Runnable Verification Scenarios

### Scenario 1: Unauthenticated Route Protection Guard

1. Clear `localStorage` in browser devtools (`localStorage.clear()`).
2. Navigate directly to `http://localhost:3000/inventory/products`.
3. **Expected Outcome**: Browser is immediately redirected to `http://localhost:3000/login`.
4. Repeat for `/inventory/orders/inbound`, `/inventory/orders/outbound`, and `/inventory/orders`.

---

### Scenario 2: Products Listing & Visual Stock Indicators

1. Log into backoffice with valid credentials to store `auth_token`.
2. Navigate to `/inventory/products`.
3. **Expected Outcome**:
   - Products list loads from `GET /inventory/products`.
   - Each row displays SKU identifier (e.g. `SKU-LA-001`), Product Name, Warehouse ID (`wh-la` or `wh-zgz`), `current_stock`, and `low_stock_threshold`.
   - Visual stock badge displays green ("Healthy Stock") when `current_stock > low_stock_threshold` and amber/red ("Low Stock") when `current_stock <= low_stock_threshold`.
   - Each product row has clickable links/buttons: "+ Log Inbound" and "- Log Outbound".

---

### Scenario 3: Inbound Delivery Order Registration

1. Navigate to `/inventory/orders/inbound` (or click "+ Log Inbound" on a product row).
2. Select a product by human-readable name from the product dropdown.
3. Enter quantity `25`.
4. Click "Submit Inbound Delivery".
5. **Expected Outcome**:
   - Request `POST /inventory/orders/inbound` responds `201 Created`.
   - A green confirmation notification banner appears.
   - Form inputs reset to empty state.
   - Navigating back to `/inventory/products` shows that `current_stock` increased by 25.

---

### Scenario 4: Outbound Order Form Reactive Stock & Client Warning Guard

1. Navigate to `/inventory/orders/outbound`.
2. Select a product with `current_stock = 10`.
3. **Expected Outcome (Reactive Fetch)**: Available stock badge immediately shows `Current Stock: 10`.
4. Enter quantity `15` (exceeds 10).
5. **Expected Outcome (Client Warning Guard)**: An inline amber warning banner appears: `"Warning: Quantity (15) exceeds available stock (10)"`.
6. Submit the form.
7. **Expected Outcome (API 400 Surface)**: Backend returns `400 Bad Request`, and the exact error message (`Insufficient stock for SKU...`) is displayed in an inline red error box near the quantity field.

---

### Scenario 5: Orders History Audit Ledger

1. Navigate to `/inventory/orders`.
2. **Expected Outcome**:
   - Table displays historical entries from `GET /inventory/orders`.
   - Rows show product name, movement quantity, order type (`inbound` with green badge vs `outbound` with blue/amber badge), creation timestamp, and `user_uuid`.
   - Page is read-only (no edit or delete actions).

---

## Automated Jest Testing Suite

Run frontend unit and integration tests:
```bash
cd uis/backoffice
npm test -- --testPathPattern=inventory
```
