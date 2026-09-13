# Quickstart & Verification Guide: Centralized Incident Manager - Backend

## 1. Run Automated Integration Test Suite

Execute pytest across the backend services test directory:

```bash
uv run pytest
```

**Expected Outcome**: 100% test suite passing cleanly across all domain and API integration tests.

---

## 2. Manual End-to-End Endpoint Verification

Start the API dev server:

```bash
cd services/api
uvicorn main:app --reload --port 8000
```

### Test 1: Verify Empty Database Metrics
```bash
curl http://localhost:8000/api/incidents/summary
```
**Expected Response**: HTTP 200 OK with `total_incidents: 0` and zeroed breakdown maps.

---

### Test 2: Create a New Incident
```bash
curl -X POST http://localhost:8000/api/incidents \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Unscheduled Carrier Delay",
    "description": "Carrier did not arrive for scheduled 14:00 pickup",
    "category": "last_mile",
    "status": "open",
    "origin": "internal",
    "branch": "zaragoza"
  }'
```
**Expected Response**: HTTP 201 Created with generated `id` (e.g., `inc_...`).

---

### Test 3: Test Valid Status Transition (`open` -> `in_progress`)
```bash
curl -X PATCH http://localhost:8000/api/incidents/inc_YOUR_ID/status \
  -H "Content-Type: application/json" \
  -d '{"status": "in_progress"}'
```
**Expected Response**: HTTP 200 OK with `status: "in_progress"`.

---

### Test 4: Test Invalid Status Transition (`in_progress` -> `open`)
```bash
curl -X PATCH http://localhost:8000/api/incidents/inc_YOUR_ID/status \
  -H "Content-Type: application/json" \
  -d '{"status": "open"}'
```
**Expected Response**: HTTP 400 Bad Request with plain language error message.

---

### Test 5: Verify Filtered List Query
```bash
curl "http://localhost:8000/api/incidents?branch=zaragoza&status=in_progress"
```
**Expected Response**: HTTP 200 OK returning array containing the updated incident.
