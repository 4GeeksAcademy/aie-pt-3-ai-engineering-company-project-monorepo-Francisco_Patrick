# API Contract: Asynchronously Offloaded Heavy Endpoints

This contract documents the 4 endpoints converted from synchronous blocking operations to non-blocking Celery task dispatchers returning HTTP 202 Accepted.

---

## 1. Summary of Offloaded Endpoints

| Method | Canonical Path | Legacy Path | Async Task Name | Description |
|---|---|---|---|---|
| `POST` | `/api/v1/reporting/trigger` | `/reporting/trigger` | `reporting.trigger_pipeline` | Triggers background analytical reporting pipeline run. |
| `GET` | `/api/v1/inventory/products` | `/inventory/products` | `inventory.list_products` | Offloads heavy stock aggregation across all product SKUs. |
| `GET` | `/api/v1/telemetry/report` | `/telemetry/report` | `telemetry.generate_report` | Offloads Pandas event telemetry extraction & aggregation. |
| `POST` | `/api/v1/incidents/analyze` | `/api/incidents/analyze` | `incidents.analyze_csv` | Offloads multi-megabyte CSV incident stream processing. |

---

## 2. Standard HTTP 202 Response Specification

All 4 converted endpoints adhere to the standard `AsyncTaskAcceptedResponse` schema.

### Schema
```json
{
  "type": "object",
  "required": ["task_id", "status", "message", "poll_url", "created_at"],
  "properties": {
    "task_id": {
      "type": "string",
      "format": "uuid",
      "example": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    },
    "status": {
      "type": "string",
      "enum": ["pending"],
      "default": "pending"
    },
    "message": {
      "type": "string",
      "example": "Task enqueued successfully."
    },
    "poll_url": {
      "type": "string",
      "example": "/api/v1/tasks/3fa85f64-5717-4562-b3fc-2c963f66afa6"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    }
  }
}
```

---

## 3. Converted Endpoint Specifications

### 3.1 `POST /reporting/trigger`

- **Status Code**: `202 Accepted`
- **Request Body (Optional)**:
  ```json
  {
    "period_start": "2026-10-01T00:00:00Z",
    "period_end": "2026-10-31T23:59:59Z"
  }
  ```
- **Response Headers**:
  - `Content-Type`: `application/json`
  - `Location`: `/api/v1/tasks/{task_id}`
- **Response Body**:
  ```json
  {
    "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "status": "pending",
    "message": "Reporting pipeline execution enqueued.",
    "poll_url": "/api/v1/tasks/a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "created_at": "2026-11-05T13:00:00Z"
  }
  ```
- **Task Result when Completed (`GET /tasks/{task_id}`)**:
  ```json
  {
    "pipeline_run_id": "run-2026-11-05-01",
    "status": "COMPLETED",
    "kpis_computed": 4,
    "records_processed": 1420
  }
  ```

---

### 3.2 `GET /inventory/products`

- **Status Code**: `202 Accepted`
- **Query Parameters**:
  - `include_archived` (optional boolean, default `false`)
- **Response Headers**:
  - `Content-Type`: `application/json`
  - `Location`: `/api/v1/tasks/{task_id}`
- **Response Body**:
  ```json
  {
    "task_id": "b2c3d4e5-f678-90ab-cdef-2345678901bc",
    "status": "pending",
    "message": "Inventory stock aggregation task enqueued.",
    "poll_url": "/api/v1/tasks/b2c3d4e5-f678-90ab-cdef-2345678901bc",
    "created_at": "2026-11-05T13:00:00Z"
  }
  ```
- **Task Result when Completed (`GET /tasks/{task_id}`)**:
  ```json
  [
    {
      "id": 1,
      "sku": "SKU-PROD-001",
      "name": "Standard Component",
      "current_stock": 250,
      "reorder_threshold": 50
    }
  ]
  ```

---

### 3.3 `GET /telemetry/report`

- **Status Code**: `202 Accepted`
- **Query Parameters**:
  - `start_date` (optional datetime, e.g. `2026-10-01T00:00:00Z`)
  - `end_date` (optional datetime, e.g. `2026-10-31T23:59:59Z`)
- **Response Headers**:
  - `Content-Type`: `application/json`
  - `Location`: `/api/v1/tasks/{task_id}`
- **Response Body**:
  ```json
  {
    "task_id": "c3d4e5f6-7890-abcd-ef12-3456789012cd",
    "status": "pending",
    "message": "Telemetry report generation task enqueued.",
    "poll_url": "/api/v1/tasks/c3d4e5f6-7890-abcd-ef12-3456789012cd",
    "created_at": "2026-11-05T13:00:00Z"
  }
  ```
- **Task Result when Completed (`GET /tasks/{task_id}`)**:
  ```json
  {
    "time_window": {
      "start": "2026-10-01T00:00:00Z",
      "end": "2026-10-31T23:59:59Z"
    },
    "metrics": {
      "total_events": 14200,
      "error_rate": 0.004,
      "p95_duration_ms": 48.2
    }
  }
  ```

---

### 3.4 `POST /incidents/analyze`

- **Status Code**: `202 Accepted`
- **Request Content-Type**: `multipart/form-data`
- **Form Body**:
  - `file`: UploadFile (required, UTF-8 CSV)
- **Synchronous Pre-Validation**:
  - Rejects missing or non-`.csv` filename with HTTP 400.
  - Rejects empty file payload with HTTP 400.
  - Rejects invalid UTF-8 byte stream with HTTP 400.
- **Payload Handling**:
  - Uploaded content is saved to local staging path `data/staging/incidents/{task_id}.csv`.
  - Task is enqueued with reference path and original filename.
- **Response Headers**:
  - `Content-Type`: `application/json`
  - `Location`: `/api/v1/tasks/{task_id}`
- **Response Body**:
  ```json
  {
    "task_id": "d4e5f678-90ab-cdef-1234-5678901234de",
    "status": "pending",
    "message": "Incident CSV analysis task enqueued.",
    "poll_url": "/api/v1/tasks/d4e5f678-90ab-cdef-1234-5678901234de",
    "created_at": "2026-11-05T13:00:00Z"
  }
  ```
- **Task Result when Completed (`GET /tasks/{task_id}`)**:
  ```json
  {
    "total_incidents": 50,
    "severity_counts": {
      "CRITICAL": 3,
      "HIGH": 12,
      "MEDIUM": 20,
      "LOW": 15
    },
    "mean_resolution_time_hours": 4.2
  }
  ```

