# API Contract: Centralized Incident Manager Backend

## Endpoints Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/incidents` | Create a new incident. |
| `GET` | `/api/incidents` | List incidents with optional filters (`status`, `origin`, `branch`, `category`). |
| `GET` | `/api/incidents/{id}` | Get detail of a single incident. Returns `404` if not found. |
| `PATCH` | `/api/incidents/{id}/status` | Update incident status following lifecycle rules. |
| `GET` | `/api/incidents/summary` | Get aggregated 4-dimension metrics (`status`, `category`, `origin`, `branch`). |

---

## 1. POST /api/incidents

### Request Body

```json
{
  "title": "Damaged pallet in Warehouse A",
  "description": "Forklift collision damaged bottom pallet",
  "category": "warehouse",
  "status": "open",
  "origin": "internal",
  "branch": "los_angeles"
}
```

### Response (201 Created)

```json
{
  "id": "inc_a1b2c3d4e5f6",
  "title": "Damaged pallet in Warehouse A",
  "description": "Forklift collision damaged bottom pallet",
  "category": "warehouse",
  "status": "open",
  "origin": "internal",
  "branch": "los_angeles",
  "created_at": "2026-09-13T14:00:00Z",
  "updated_at": "2026-09-13T14:00:00Z",
  "legacy_id": null
}
```

---

## 2. GET /api/incidents

### Query Parameters (Optional)
- `status`: String (`open`, `in_progress`, `resolved`, `discarded`)
- `origin`: String (`customer`, `branch`, `internal`)
- `branch`: String (e.g. `zaragoza`, `los_angeles`, `central`)
- `category`: String (`warehouse`, `reverse_logistics`, `last_mile`, `customer_experience`)

### Response (200 OK)

```json
[
  {
    "id": "inc_a1b2c3d4e5f6",
    "title": "Damaged pallet in Warehouse A",
    "description": "Forklift collision damaged bottom pallet",
    "category": "warehouse",
    "status": "open",
    "origin": "internal",
    "branch": "los_angeles",
    "created_at": "2026-09-13T14:00:00Z",
    "updated_at": "2026-09-13T14:00:00Z",
    "legacy_id": null
  }
]
```

---

## 3. GET /api/incidents/{id}

### Response (200 OK)

```json
{
  "id": "inc_a1b2c3d4e5f6",
  "title": "Damaged pallet in Warehouse A",
  "description": "Forklift collision damaged bottom pallet",
  "category": "warehouse",
  "status": "open",
  "origin": "internal",
  "branch": "los_angeles",
  "created_at": "2026-09-13T14:00:00Z",
  "updated_at": "2026-09-13T14:00:00Z",
  "legacy_id": null
}
```

### Response (404 Not Found)

```json
{
  "error": "Not Found",
  "message": "Incident with ID 'inc_missing' was not found."
}
```

---

## 4. PATCH /api/incidents/{id}/status

### Request Body

```json
{
  "status": "in_progress"
}
```

### Response (200 OK)

```json
{
  "id": "inc_a1b2c3d4e5f6",
  "title": "Damaged pallet in Warehouse A",
  "description": "Forklift collision damaged bottom pallet",
  "category": "warehouse",
  "status": "in_progress",
  "origin": "internal",
  "branch": "los_angeles",
  "created_at": "2026-09-13T14:00:00Z",
  "updated_at": "2026-09-13T14:05:00Z",
  "legacy_id": null
}
```

### Response (400 Bad Request — Invalid State Transition)

```json
{
  "error": "Invalid Status Transition",
  "message": "Cannot transition incident status from 'open' directly to 'resolved'."
}
```

---

## 5. GET /api/incidents/summary

### Response (200 OK)

```json
{
  "total_incidents": 10,
  "by_status": {
    "open": 3,
    "in_progress": 2,
    "resolved": 4,
    "discarded": 1
  },
  "by_category": {
    "warehouse": 3,
    "reverse_logistics": 2,
    "last_mile": 3,
    "customer_experience": 2
  },
  "by_origin": {
    "customer": 7,
    "branch": 2,
    "internal": 1
  },
  "by_branch": {
    "central": 7,
    "los_angeles": 2,
    "zaragoza": 1
  }
}
```
