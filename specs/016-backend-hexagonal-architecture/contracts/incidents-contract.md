# Incidents & Stream Analysis API Contract

**Service**: `services/api`  
**Domain**: Incidents & Analysis  
**Base Path**: `/api/incidents` (legacy) & `/api/v1/incidents` (canonical)  
**Storage Engine**: TinyDB (`incidents`) & In-memory / Cache Stream Store  

---

## Endpoints Specification

### 1. Incident Metrics Summary
* **Method**: `GET`
* **Path**: `/api/incidents/summary` & `/api/v1/incidents/summary`
* **Security**: Open / Internal
* **Status**: `200 OK`
* **Cache**: 30s TTL (`incident_summary:global`)
* **Response Payload (`IncidentSummaryResponse`)**:
  ```json
  {
    "total_incidents": 24,
    "by_status": {
      "open": 8,
      "in_progress": 10,
      "resolved": 4,
      "closed": 2
    },
    "by_category": {
      "warehouse": 12,
      "last_mile": 6,
      "reverse_logistics": 4,
      "customer_experience": 2
    },
    "by_origin": {
      "customer": 14,
      "internal": 8,
      "partner": 2
    },
    "by_branch": {
      "branch_north": 14,
      "branch_south": 10
    }
  }
  ```

---

### 2. List Incidents (Multi-Filter)
* **Method**: `GET`
* **Path**: `/api/incidents` & `/api/v1/incidents`
* **Query Parameters**:
  * `status`: Optional filter (`"open"`, `"in_progress"`, `"resolved"`, `"closed"`)
  * `origin`: Optional filter (`"customer"`, `"internal"`, `"partner"`)
  * `branch`: Optional string filter
  * `category`: Optional filter (`"warehouse"`, `"reverse_logistics"`, `"last_mile"`, `"customer_experience"`)
* **Status**: `200 OK`
* **Response Payload**: `List[IncidentResponseSchema]`

---

### 3. Create Incident
* **Method**: `POST`
* **Path**: `/api/incidents` & `/api/v1/incidents`
* **Status**: `201 Created`
* **Request Payload (`IncidentCreateSchema`)**:
  ```json
  {
    "title": "Damaged Pallet in Warehouse Bay 4",
    "description": "Forklift impact ruptured secondary packaging.",
    "category": "warehouse",
    "origin": "internal",
    "branch": "branch_north",
    "status": "open"
  }
  ```
* **Response Payload (`IncidentResponseSchema`)**:
  ```json
  {
    "id": "inc_e4c4829c52d1",
    "title": "Damaged Pallet in Warehouse Bay 4",
    "description": "Forklift impact ruptured secondary packaging.",
    "category": "warehouse",
    "origin": "internal",
    "branch": "branch_north",
    "status": "open",
    "satisfaction_index": null,
    "created_at": "2026-10-13T10:00:00Z",
    "updated_at": "2026-10-13T10:00:00Z"
  }
  ```
* **Side Effect**: Invalidates `incident_summary:global` cache.

---

### 4. Get Incident Detail
* **Method**: `GET`
* **Path**: `/api/incidents/{incident_id}` & `/api/v1/incidents/{incident_id}`
* **Status**: `200 OK`
* **Response Payload**: `IncidentResponseSchema`
* **Errors**: `404 Not Found`

---

### 5. Update Incident Lifecycle Status
* **Method**: `PATCH`
* **Path**: `/api/incidents/{incident_id}/status` & `/api/v1/incidents/{incident_id}/status`
* **Request Payload (`IncidentStatusUpdateSchema`)**:
  ```json
  {
    "status": "in_progress"
  }
  ```
* **Status**: `200 OK`
* **Response Payload**: `IncidentResponseSchema`
* **Errors**: `400 Bad Request` (illegal state transition), `404 Not Found`
* **Side Effect**: Invalidates `incident_summary:global` cache.

---

### 6. Analyze Incident CSV Stream
* **Method**: `POST`
* **Path**: `/api/incidents/analyze` & `/api/v1/incidents/analyze`
* **Request Payload**: Multipart `UploadFile` (CSV file with incident records)
* **Status**: `200 OK`
* **Response Payload (`IncidentAnalysisResponse`)**:
  ```json
  {
    "total_rows": 1000,
    "valid_rows": 985,
    "invalid_rows": 15,
    "category_breakdown": {
      "warehouse": 450,
      "last_mile": 320,
      "reverse_logistics": 150,
      "customer_experience": 65
    },
    "average_satisfaction": 4.12
  }
  ```
* **Side Effect**: Stores analysis results in transient analysis store (CachePort) for subsequent download.

---

### 7. Export Incident Analysis Results
* **Method**: `GET`
* **Path**: `/api/incidents/results/export` & `/api/v1/incidents/results/export`
* **Status**: `200 OK`
* **Response Headers**:
  * `Content-Type`: `text/csv; charset=utf-8`
  * `Content-Disposition`: `attachment; filename=results.csv`
* **Response Body**: Streaming CSV content
* **Errors**: `404 Not Found` (if no previous analysis exists)
