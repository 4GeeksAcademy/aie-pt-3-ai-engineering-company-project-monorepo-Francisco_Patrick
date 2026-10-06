# Quickstart & Verification Guide: Telemetry Event Capture

**Feature**: Telemetry Event Capture  
**Feature Branch**: `015-telemetry-event-capture`  
**Date**: 2026-10-06  

---

## 1. Prerequisites & Environment Setup

### 1.1 Backend Environment Configuration
In `services/api/.env` (or environment):
```bash
TELEMETRY_ENDPOINT=/telemetry/events
```

### 1.2 Frontend Environment Configuration
In `uis/backoffice/.env.local`:
```bash
NEXT_PUBLIC_TELEMETRY_ENDPOINT=http://localhost:8000/telemetry/events
```

---

## 2. Running the Services

### 2.1 Start Backend API
```powershell
# From services/api
cd services/api
uv run uvicorn main:app --reload --port 8000
```

### 2.2 Start Frontend Backoffice
```powershell
# From uis/backoffice
cd uis/backoffice
npm run dev
```

---

## 3. End-to-End Verification Scenarios

### Scenario 1: Direct Ingestion Stub API Verification
Send a test batch directly to the FastAPI telemetry endpoint using `curl`:

```powershell
curl -X POST http://localhost:8000/telemetry/events `
  -H "Content-Type: application/json" `
  -d '{
    "events": [
      {
        "eventId": "550e8400-e29b-41d4-a716-446655440000",
        "timestamp": "2026-10-06T10:30:00.000Z",
        "sessionId": "sess_demo_123",
        "userId": "usr_test_operator",
        "event_type": "inbound_order_created",
        "schemaVersion": "1.0.0",
        "requestId": "req_abc_123",
        "properties": {
          "inboundOrderId": "INB-9988",
          "clientId": "client_acme",
          "warehouseCode": "LA-01",
          "totalSkus": 5,
          "totalUnits": 200,
          "sourceChannel": "PORTAL"
        }
      }
    ]
  }'
```

**Expected Outcome**:
- Status: `200 OK`
- Body: `{"received": 1}`
- Backend Console Log: `Received 1 telemetry events: ['inbound_order_created']`

---

### Scenario 2: Frontend Queue & Batch Transmission Verification
1. Open the Backoffice UI in a browser (`http://localhost:3000`).
2. Open Browser DevTools -> **Network** tab, filter by `events` or `telemetry`.
3. Navigate across sections (e.g. Incidents, Suppliers, Inventory).
4. Observe that individual user clicks do NOT fire immediate HTTP requests.
5. Wait 10 seconds or trigger 20 actions:
   - A single `POST /telemetry/events` is dispatched containing `{ "events": [...] }`.
   - Each event contains valid `eventId`, `timestamp`, `sessionId`, `userId`, `schemaVersion`, `requestId`.
   - Network response returns `200 OK` with `{ "received": N }`.

---

### Scenario 3: Page Exit / Tab Visibility Flush (`sendBeacon`)
1. In the Backoffice UI, perform 2 actions to populate the queue without waiting 10 seconds.
2. Switch tabs or close the browser tab.
3. Observe in DevTools (Preserve Log enabled) that a `sendBeacon` POST is fired carrying the pending batch, resulting in 200 OK without dropping events.

---

### Scenario 4: Automated Automated Test Suites
Run backend and frontend automated test suites:

```powershell
# Backend pytest
cd services/api
uv run pytest tests/api/test_telemetry.py

# Frontend jest
cd ../../uis/backoffice
npm test __tests__/services/telemetry.test.ts
```
