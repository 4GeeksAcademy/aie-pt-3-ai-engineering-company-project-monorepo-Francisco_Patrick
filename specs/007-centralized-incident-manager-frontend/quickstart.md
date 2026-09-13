# Quickstart & Verification Guide: Centralized Incident Manager - Frontend

## 1. Start Services

### Step A: Backend API
```bash
cd services/api
uv run uvicorn main:app --port 8000 --reload
```

### Step B: Frontend Backoffice UI
```bash
cd uis/backoffice
npm run dev
```
Navigate to `http://localhost:3000/incidents` or click "Incidents" in the main navigation menu.

---

## 2. Validation Scenarios

### Scenario 1: Registration Form Client-Side Validation
1. Open `http://localhost:3000/incidents/register`.
2. Leave required fields blank and click "Submit Incident".
3. **Expected Result**: Network request is NOT sent. Client validation messages highlight missing required fields (`title`, `description`).

### Scenario 2: Origin Highlighting
1. On the registration form, change `origin` from `customer` to `branch`.
2. **Expected Result**: `branch` dropdown container is visually highlighted (amber glow / border highlight).

### Scenario 3: Valid Creation & Form Reset
1. Fill out:
   - Title: "Broken barcode reader"
   - Description: "Device battery swollen in sorting room"
   - Category: "warehouse"
   - Status: "open"
   - Origin: "internal"
   - Branch: "zaragoza"
2. Click "Submit Incident".
3. **Expected Result**: Submit button disabled with spinner. On completion, success message is displayed, form clears, and the list updates.

### Scenario 4: List Filtering & Inline Status Update Failure Rollback
1. Go to `http://localhost:3000/incidents`.
2. Apply filter `status=open`.
3. Try updating an incident status inline from `open` to `resolved` (invalid direct status transition).
4. **Expected Result**: Backend returns 400 Bad Request error. UI displays error alert banner and dropdown visually reverts back to `open`.

### Scenario 5: Summary Panel Resiliency
1. Stop backend API service (`Ctrl+C` in `services/api`).
2. Refresh `http://localhost:3000/incidents`.
3. **Expected Result**: Summary panel and listing panel display friendly error banners with "Retry" buttons. The page layout does not crash or display raw stack traces.
