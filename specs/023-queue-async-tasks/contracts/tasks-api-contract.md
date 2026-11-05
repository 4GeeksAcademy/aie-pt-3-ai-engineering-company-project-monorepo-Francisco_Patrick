# API Contract: Task Lifecycle & Status Tracking

**Endpoint**: `GET /tasks/{task_id}` (canonical `/api/v1/tasks/{task_id}`)  
**Description**: Query the lifecycle state and final result of an asynchronous background task.  
**Tag**: `Tasks`  

---

## 1. Request Specification

### HTTP Request
`GET /tasks/{task_id}`  
`GET /api/v1/tasks/{task_id}`

### Path Parameters
| Parameter | Type | Required | Description | Example |
|---|---|---|---|---|
| `task_id` | `string (UUID)` | Yes | Unique Celery execution identifier returned in HTTP 202 response. | `b1e2c3d4-5678-90ab-cdef-1234567890ab` |

### Query Parameters
*None*

### Request Headers
| Header | Value | Required | Description |
|---|---|---|---|
| `Accept` | `application/json` | Yes | Requested MIME response type. |

---

## 2. Response Specifications

### HTTP 200 OK: Task Found & Inspected

Returned when `task_id` corresponds to a valid enqueued or finished task.

#### Response Headers
- `Content-Type`: `application/json`

#### Schema: `TaskStatusResponse`
```json
{
  "type": "object",
  "required": ["task_id", "status"],
  "properties": {
    "task_id": {
      "type": "string",
      "format": "uuid",
      "description": "Unique identifier of the task."
    },
    "status": {
      "type": "string",
      "enum": ["pending", "started", "success", "failure"],
      "description": "Current lifecycle status."
    },
    "result": {
      "description": "Output payload produced upon successful completion. Null if task is pending, started, or failed.",
      "nullable": true
    },
    "error": {
      "type": "string",
      "description": "Sanitized error message if task failed. Null otherwise.",
      "nullable": true
    },
    "created_at": {
      "type": "string",
      "format": "date-time",
      "description": "UTC timestamp of task enqueue."
    },
    "completed_at": {
      "type": "string",
      "format": "date-time",
      "nullable": true,
      "description": "UTC timestamp of completion or terminal failure."
    }
  }
}
```

#### Example Payloads by State

##### State: `pending`
```json
{
  "task_id": "b1e2c3d4-5678-90ab-cdef-1234567890ab",
  "status": "pending",
  "result": null,
  "error": null,
  "created_at": "2026-11-05T13:00:00Z",
  "completed_at": null
}
```

##### State: `started`
```json
{
  "task_id": "b1e2c3d4-5678-90ab-cdef-1234567890ab",
  "status": "started",
  "result": null,
  "error": null,
  "created_at": "2026-11-05T13:00:00Z",
  "completed_at": null
}
```

##### State: `success` (Example: Inventory Products)
```json
{
  "task_id": "b1e2c3d4-5678-90ab-cdef-1234567890ab",
  "status": "success",
  "result": [
    {
      "id": 1,
      "sku": "SKU-TRACK-001",
      "name": "Heavy Duty Sensor",
      "current_stock": 142
    }
  ],
  "error": null,
  "created_at": "2026-11-05T13:00:00Z",
  "completed_at": "2026-11-05T13:00:02Z"
}
```

##### State: `failure` (Task Exhausted Retries / Quarantined to DLQ)
```json
{
  "task_id": "b1e2c3d4-5678-90ab-cdef-1234567890ab",
  "status": "failure",
  "result": null,
  "error": "Pipeline execution failed: Database lock timeout exceeded after 3 attempts.",
  "created_at": "2026-11-05T13:00:00Z",
  "completed_at": "2026-11-05T13:00:15Z"
}
```

---

### HTTP 404 Not Found: Unknown Task Identifier

Returned when `task_id` is unknown, has expired, or was never enqueued.

#### Schema
```json
{
  "detail": "Task 'invalid-uuid-1234' not found."
}
```

---

### HTTP 503 Service Unavailable: Broker Connection Error

Returned when the Redis result store or broker is unreachable.

#### Schema
```json
{
  "detail": "Queue service is temporarily unavailable. Please retry shortly."
}
```

