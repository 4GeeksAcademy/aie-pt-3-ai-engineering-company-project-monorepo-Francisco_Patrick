# Data Model & Serialization Schemas: Backend Serialization Improvement

**Feature Branch**: `013-backend-serialization-improvement`
**Date**: 2026-09-29
**Status**: Completed

## 1. Schema Specifications

### 1.1 User Management & Authentication Schemas (`services/api/domain/models.py`)

#### `UserResponse`
Projection schema for returning safe user metadata across authentication self-inspection and administrative user management routes.

```python
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    is_active: bool = True
    role: Literal["admin", "manager", "user"] = "user"
    created_at: str
```

**Field Breakdown**:
- `id` (str): Unique UUID string identifying the user.
- `email` (str): User's registered email address.
- `is_active` (bool): Account active/suspended flag.
- `role` (Literal["admin", "manager", "user"]): Authorization access tier.
- `created_at` (str): ISO-8601 formatted creation timestamp.
- *Omitted Fields*: `hashed_password` is strictly excluded from this model.

---

#### `MessageResponse`
Standardized operation acknowledgment schema.

```python
class MessageResponse(BaseModel):
    message: str
```

**Field Breakdown**:
- `message` (str): Human-readable confirmation or status message (e.g., `"Password successfully updated."`).

---

### 1.2 Incident Management Schemas (`services/api/domain/schemas/incident_schema.py`)

#### `IncidentSummaryResponse`
Structured summary response for multi-dimensional incident metrics aggregations.

```python
class IncidentSummaryResponse(BaseModel):
    total: int
    by_status: Dict[str, int]
    by_category: Dict[str, int]
    by_origin: Dict[str, int]
    by_branch: Dict[str, int]
```

**Field Breakdown**:
- `total` (int): Total number of recorded incidents.
- `by_status` (Dict[str, int]): Count breakdown by lifecycle status (`open`, `in_progress`, `resolved`, `discarded`).
- `by_category` (Dict[str, int]): Count breakdown by category (`warehouse`, `reverse_logistics`, `last_mile`, `customer_experience`).
- `by_origin` (Dict[str, int]): Count breakdown by origin (`customer`, `branch`, `internal`).
- `by_branch` (Dict[str, int]): Count breakdown by branch identifier (`central`, `north`, etc.).

---

#### `IncidentAnalysisResponse`
Response schema for streaming CSV ingestion, metric aggregation, and validation diagnostics.

```python
class IncidentMetrics(BaseModel):
    total_processed: int
    valid_records: int
    invalid_records: int
    category_breakdown: Dict[str, int]
    status_breakdown: Dict[str, int]
    average_satisfaction_index: float

class InvalidRecordDetail(BaseModel):
    row: int
    id: str
    reason: str

class IncidentDiagnostics(BaseModel):
    invalid_sample: List[InvalidRecordDetail]

class IncidentAnalysisResponse(BaseModel):
    metrics: IncidentMetrics
    diagnostics: IncidentDiagnostics
```

**Field Breakdown**:
- `metrics.total_processed` (int): Total rows evaluated in CSV stream.
- `metrics.valid_records` (int): Count of valid rows meeting validation criteria.
- `metrics.invalid_records` (int): Count of invalid or malformed rows.
- `metrics.category_breakdown` (Dict[str, int]): Category distribution among valid rows.
- `metrics.status_breakdown` (Dict[str, int]): Status distribution among valid rows.
- `metrics.average_satisfaction_index` (float): Mean satisfaction rating for closed incidents.
- `diagnostics.invalid_sample` (List[InvalidRecordDetail]): Truncated list (up to 100 entries) of row-level error diagnostics.

---

## 2. Entity Mapping & Serialization State Transitions

| Target Route | Input Schema | Internal Processing Entity | Output Response Schema |
|---|---|---|---|
| `POST /users` | `UserCreate` | `domain.models.User` (DB insert) | `UserResponse` |
| `GET /users` | None | `List[domain.models.User]` (DB query) | `List[UserResponse]` |
| `GET /users/{id}` | Path param `user_id` | `domain.models.User` | `UserResponse` |
| `PUT /users/{id}` | `dict` / `UserUpdate` | `domain.models.User` (DB update) | `UserResponse` |
| `GET /auth/me` | Bearer Token | `domain.models.User` (Session) | `UserResponse` |
| `POST /auth/forgot-password` | `ForgotPasswordRequestModel` | Email dispatch + Token generation | `MessageResponse` |
| `POST /auth/reset-password` | `ResetPasswordRequestModel` | Token validation + Hash update | `MessageResponse` |
| `POST /auth/change-password` | `ChangePasswordRequestModel` | Password verification + Hash update | `MessageResponse` |
| `GET /api/incidents/summary` | None | `repo.count_summary()` | `IncidentSummaryResponse` |
| `POST /api/incidents/analyze` | `UploadFile` (CSV) | `analyze_csv_stream()` | `IncidentAnalysisResponse` |
