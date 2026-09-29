# Quickstart Validation Guide: Backend Serialization Improvement

**Feature Branch**: `013-backend-serialization-improvement`
**Date**: 2026-09-29
**Status**: Completed

This quickstart guide outlines the step-by-step procedure to validate and verify that all serialization schemas and route improvements function without regressions.

---

## 1. Prerequisites & Environment Setup

1. Open a terminal in `services/api/`:
   ```powershell
   cd services/api
   ```
2. Ensure python virtual environment is available:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

---

## 2. Automated Test Suite Execution

Run the complete pytest regression suite:
```powershell
.\.venv\Scripts\pytest -v
```

**Expected Outcome**:
- All 73+ tests pass with 0 failures.
- No schema validation errors or missing attribute exceptions.

---

## 3. Interactive Documentation & Manual API Validation

Start the local development server:
```powershell
.\.venv\Scripts\python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Open interactive Swagger docs at: `http://127.0.0.1:8000/docs`

### Scenario A: Verify Current User Self-Inspection (`GET /auth/me`)
1. In `/docs`, execute `POST /auth/login` with test credentials. Copy the `access_token`.
2. Authorize Swagger UI with the Bearer token.
3. Execute `GET /auth/me`.
4. **Verification**:
   - Status code is `200 OK`.
   - Response contains: `{"id": "...", "email": "...", "is_active": true, "role": "...", "created_at": "..."}`.
   - **Crucial**: The `hashed_password` field is NOT present in the response body.

### Scenario B: Verify Password Reset Request (`POST /auth/forgot-password`)
1. In `/docs`, execute `POST /auth/forgot-password` with body:
   ```json
   {
     "email": "test@example.com"
   }
   ```
2. **Verification**:
   - Status code is `200 OK`.
   - Response payload is: `{"message": "If that email is registered, you will receive a reset link shortly."}`.
   - Response schema matches `MessageResponse`.

### Scenario C: Verify Incident Summary Breakdown (`GET /api/incidents/summary`)
1. In `/docs`, execute `GET /api/incidents/summary`.
2. **Verification**:
   - Status code is `200 OK`.
   - Response body contains concrete structured count dictionaries for `total`, `by_status`, `by_category`, `by_origin`, and `by_branch`.
   - Response schema matches `IncidentSummaryResponse`.

### Scenario D: Verify Incident CSV Ingestion & Analysis (`POST /api/incidents/analyze`)
1. In `/docs`, upload a test CSV file to `POST /api/incidents/analyze`.
2. **Verification**:
   - Status code is `200 OK`.
   - Response payload contains `metrics` and `diagnostics.invalid_sample`.
   - Response schema matches `IncidentAnalysisResponse`.
