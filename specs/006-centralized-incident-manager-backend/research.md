# Technical Research: Centralized Incident Manager - Backend

## 1. Status Lifecycle State Machine & Transition Guard

- **Decision**: Implement explicit transition validation logic within `domain/incident_model.py` or `application/services/incident_service.py`.
- **Allowed Transition Matrix**:
  - `open` -> `in_progress`, `discarded`
  - `in_progress` -> `resolved`, `discarded`
  - `resolved` -> None (Terminal state)
  - `discarded` -> None (Terminal state)
- **Rationale**: Strict state transition validation prevents accidental state regression or illegal operational jumps. Attempting invalid transitions raises a domain `InvalidStatusTransitionException`, which maps to HTTP 400.

## 2. Multi-Attribute Filter Query Engine

- **Decision**: Extend `TinyDBIncidentRepository.find_all(filters: Optional[dict])` to filter by any combination of `status`, `origin`, `branch`, and `category`.
- **Rationale**: Allows query execution on `GET /api/incidents?status=open&branch=zaragoza` efficiently across stored records.

## 3. Aggregated Summary Metrics Engine

- **Decision**: Extend `TinyDBIncidentRepository.count_summary()` to return 4 breakdown dimensions:
  - `by_status`: `{ "open": 0, "in_progress": 0, "resolved": 0, "discarded": 0 }`
  - `by_category`: `{ "warehouse": 0, "reverse_logistics": 0, "last_mile": 0, "customer_experience": 0 }`
  - `by_origin`: `{ "customer": 0, "branch": 0, "internal": 0 }`
  - `by_branch`: `{ ... }` (dynamically populated or defaulted)
- **Rationale**: Fulfills the requirement for comprehensive 4-dimension metric tracking. On an empty database, all counters return `0` instead of failing.

## 4. Error Handling & Validation Response Architecture

- **Decision**: Configure FastAPI exception handlers to map:
  - `RequestValidationError` / `ValueError` -> HTTP 400 JSON: `{"error": "Validation Error", "message": "...", "details": [{"field": "...", "issue": "..."}]}`
  - `InvalidStatusTransitionException` -> HTTP 400 JSON: `{"error": "Invalid Status Transition", "message": "Cannot transition from 'open' to 'resolved'."}`
  - `IncidentNotFoundException` / `HTTPException(404)` -> HTTP 404 JSON: `{"error": "Not Found", "message": "Incident 'inc_xyz' does not exist."}`
  - Generic `Exception` -> HTTP 500 JSON: `{"error": "Server Error", "message": "An unexpected error occurred. Please try again or contact support."}` (never leaking tracebacks).
