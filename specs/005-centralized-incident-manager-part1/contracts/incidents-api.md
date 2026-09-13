# API Contract: Centralized Incident Manager

## Endpoints Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/incidents/summary` | Get aggregated incident totals grouped by status and category. |
| `GET` | `/api/incidents` | List incident records with optional filters. |
| `POST` | `/api/incidents` | Create a new incident record (form entry point). |

---

## 1. GET /api/incidents/summary

### Response (200 OK)

```json
{
  "total_incidents": 95,
  "by_status": {
    "open": 30,
    "in_progress": 0,
    "resolved": 60,
    "discarded": 5
  },
  "by_category": {
    "warehouse": 25,
    "reverse_logistics": 20,
    "last_mile": 30,
    "customer_experience": 20
  }
}
```

---

## 2. Standard Error Response Format

All API errors return clean, user-understandable JSON instead of raw stack traces.

### Response (400 Bad Request / 422 Unprocessable Entity)

```json
{
  "error": "Validation Error",
  "message": "The field 'category' must be one of: warehouse, reverse_logistics, last_mile, customer_experience.",
  "details": [
    {
      "field": "category",
      "issue": "Invalid enum value 'invalid_cat'"
    }
  ]
}
```

### Response (500 Internal Server Error)

```json
{
  "error": "Server Error",
  "message": "An unexpected error occurred while processing the incident request. Please try again or contact support."
}
```
