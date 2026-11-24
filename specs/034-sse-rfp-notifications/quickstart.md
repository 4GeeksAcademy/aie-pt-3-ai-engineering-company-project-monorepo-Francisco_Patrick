# Quickstart & Validation Guide: Real-Time RFP Ticket Notifications (SSE Part 1)

**Feature Branch**: `034-sse-rfp-notifications`  
**Date**: 2026-11-24  
**Spec**: [spec.md](./spec.md) | **Contracts**: [sse-rfp-notifications-api.yaml](./contracts/sse-rfp-notifications-api.yaml)

---

## 1. Prerequisites & Environment Setup

Ensure the Python virtual environment and Node workspace dependencies are installed from the repository root:

```powershell
# 1. Verify Python dependencies in services/api
pytest --version

# 2. Verify TypeScript workspace dependencies
npm run typecheck
```

> **Zero LLM Requirement (FR-013, SC-005)**: No `OPENAI_API_KEY` or external LLM/Vector service is required to run or test the SSE notification stream, ticket creation broadcast, keep-alive heartbeat, or reconnection/recovery flows.

---

## 2. Running Automated Verification Suites

### 2.1 Backend SSE Wire Format, Auth, Fan-Out & Replay Tests (`pytest`)

Run the dedicated backend test suite validating `Content-Type: text/event-stream`, named `event: rfp_ticket_created`, flat JSON payload schema ([rfp-ticket-created-event.schema.json](./contracts/rfp-ticket-created-event.schema.json)), HTTP 401 rejection, `: keep-alive` heartbeats, multi-client fan-out, and `Last-Event-ID` ring-buffer replay:

```powershell
pytest services/api/tests/test_rfp_sse_notifications.py -v
```

**Expected Outcome**:
- 100% of test cases pass.
- Unauthenticated requests to `GET /api/v1/rfp/notifications/stream` return `401 Unauthorized` with zero SSE frames emitted.
- Authenticated stream requests return `200 OK` with `Content-Type: text/event-stream; charset=utf-8` and `Cache-Control: no-cache`.
- Posting a new RFP ticket to `POST /api/v1/rfp/tickets` (or completing RFP orchestration in `RFPIntakePipeline`) emits:
  ```text
  id: 1
  event: rfp_ticket_created
  data: {"ticket_id":"tkt_0225","rfp_id":"rfp_0071","client_name":"Northline Apparel","client_country":"US","services_requested":["warehouse","lastmile"],"status":"analyzing","created_at":"2026-07-24T14:32:00Z"}
  ```
- Reconnecting with `Last-Event-ID: 1` replays only events with `id > 1`.

### 2.2 Frontend SSE Client, Reconnection Backoff & Deduplication Tests (`jest` & `typecheck`)

Run the frontend unit tests and monorepo static type check:

```powershell
npm --prefix uis/backoffice test -- rfpNotifications
npm run typecheck
```

**Expected Outcome**:
- Exponential backoff schedule (`1s, 2s, 4s, 8s, 16s, 30s`) verified on stream drops; immediate halt on HTTP `401`/`403`.
- Hybrid recovery (`Last-Event-ID` header + `GET /api/v1/rfp/tickets` reconciliation) merges missed tickets and deduplicates by `ticket_id` so 0 duplicate rows appear.

---

## 3. Manual End-to-End Validation Scenario

1. **Start the FastAPI Backend**:
   ```powershell
   cd services/api
   uvicorn main:app --reload --port 8000
   ```
2. **Start the Backoffice UI**:
   ```powershell
   npm --prefix uis/backoffice run dev
   ```
3. **Open the RFP Dashboard**:
   - Log in to the backoffice UI (`http://localhost:3000/login`) and navigate to `/rfp`.
   - Observe the live connection indicator showing **"Tiempo Real Activo (SSE)"**.
4. **Trigger a Real-Time RFP Ticket Notification**:
   - Obtain a valid Bearer JWT from `/api/v1/auth/login` and execute:
     ```bash
     curl -X POST http://localhost:8000/api/v1/rfp/tickets \
       -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
       -H "Content-Type: application/json" \
       -d '{
         "ticket_id": "tkt_0225",
         "rfp_id": "rfp_0071",
         "client_name": "Northline Apparel",
         "client_country": "US",
         "services_requested": ["warehouse", "lastmile"]
       }'
     ```
5. **Verify Real-Time Arrival**:
   - Within `< 2 seconds`, the Northline Apparel ticket (`tkt_0225` / `rfp_0071`) appears at the top of the `/rfp` dashboard with `status = analyzing` (`Analizando`), country `US`, services `warehouse, lastmile`, and a **"Nuevo en tiempo real"** highlight badge—without reloading the page.
