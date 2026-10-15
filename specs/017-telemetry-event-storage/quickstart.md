# Quickstart Validation Guide: Telemetry Event Storage

**Feature**: `017-telemetry-event-storage`  
**Date**: 2026-10-15  
**Status**: Ready for Validation  

---

## 1. Prerequisites & Environment Setup

Ensure the Python virtual environment is initialized with all dependencies:

```powershell
cd services/api
uv sync
```

Ensure the database schema is initialized (automatically creates `telemetry_events` table via `init_db()`):

```powershell
uv run python -c "from infrastructure.persistence.sqlmodel.client import init_db; init_db()"
```

Start the FastAPI development server:

```powershell
uv run uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

---

## 2. Automated Test Verification

Execute all unit, integration, and API contract tests covering telemetry ingestion:

```powershell
uv run pytest tests/api/test_telemetry.py tests/unit/test_domain_models.py tests/unit/test_application_services.py -v
```

Expected Outcome:
- All test suites pass with 100% success rate.
- Coverage includes partial validation, empty batches, receipt counters, and bulk storage.

---

## 3. End-to-End Runnable Validation Scenarios

Refer to the OpenAPI specification in [telemetry-api.yaml](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/017-telemetry-event-storage/contracts/telemetry-api.yaml) and domain specifications in [data-model.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/017-telemetry-event-storage/data-model.md).

### Scenario 1: Mixed Batch Ingestion (Partial Persistence)

Send a batch containing 2 valid events and 1 malformed event (missing `eventId` and invalid `event_type`):

```powershell
curl.exe -X POST http://127.0.0.1:8000/telemetry/events `
  -H "Content-Type: application/json" `
  -d '{
    "events": [
      {
        "eventId": "a1b2c3d4-e5f6-4a1b-8c2d-1e2f3a4b5c6d",
        "timestamp": "2026-10-15T10:00:00Z",
        "sessionId": "sess_quickstart_01",
        "userId": "usr_operator_1",
        "event_type": "inbound_order_created",
        "schemaVersion": "1.0.0",
        "requestId": "req_qs_01",
        "properties": {
          "warehouseId": "WH-NORTH",
          "quantity": 100
        }
      },
      {
        "eventId": "not-a-uuid",
        "timestamp": "invalid-timestamp",
        "sessionId": "",
        "event_type": "MALFORMED_EVENT",
        "schemaVersion": "invalid",
        "requestId": ""
      },
      {
        "eventId": "f1e2d3c4-b5a6-4f1e-8d2c-9a8b7c6d5e4f",
        "timestamp": "2026-10-15T10:05:00Z",
        "sessionId": "sess_quickstart_01",
        "userId": "usr_operator_1",
        "event_type": "stock_threshold_triggered",
        "schemaVersion": "1.0.0",
        "requestId": "req_qs_02",
        "properties": {
          "skuId": "SKU-PROMO-1",
          "severity": "HIGH"
        }
      }
    ]
  }'
```

**Expected Response**:
- Status: `200 OK`
- Body:
  ```json
  {
    "received": 3,
    "stored": 2,
    "rejected": 1
  }
  ```

---

### Scenario 2: Empty Batch Ingestion

Send an empty event batch:

```powershell
curl.exe -X POST http://127.0.0.1:8000/telemetry/events `
  -H "Content-Type: application/json" `
  -d '{"events": []}'
```

**Expected Response**:
- Status: `200 OK`
- Body:
  ```json
  {
    "received": 0,
    "stored": 0,
    "rejected": 0
  }
  ```

---

### Scenario 3: Malformed Outer Envelope Rejection

Send a request missing the `events` field:

```powershell
curl.exe -X POST http://127.0.0.1:8000/telemetry/events `
  -H "Content-Type: application/json" `
  -d '{"invalidKey": []}'
```

**Expected Response**:
- Status: `422 Unprocessable Entity`

---

### Scenario 4: Direct Database Verification

Inspect persisted records directly from SQLite or PostgreSQL:

```powershell
uv run python -c "from sqlmodel import Session, select; from infrastructure.persistence.sqlmodel.client import get_engine; from infrastructure.persistence.sqlmodel.models import TelemetryEventRecord; eng = get_engine(); session = Session(eng); results = session.exec(select(TelemetryEventRecord)).all(); print(f'Total stored events: {len(results)}'); [print(r.event_id, r.event_type, r.timestamp) for r in results[-5:]]"
```

**Expected Outcome**:
- Output confirms the exact valid event records were inserted with immutable attributes.
- Malformed items do not appear in the database.
