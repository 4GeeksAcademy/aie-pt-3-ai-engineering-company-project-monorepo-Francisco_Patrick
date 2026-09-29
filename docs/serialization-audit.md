# Backend Service API Serialization Audit (`services/api/`)

## Executive Summary

This audit reviews all endpoints across the FastAPI backend service (`services/api/`). It evaluates the serialization integrity, schema definitions, response models, and security hygiene of each route.

A key security vulnerability identified during this audit is **credential exposure in User and Authentication endpoints**:
- Domain model `User` includes the database field `hashed_password`. Multiple endpoints (`/auth/me`, `POST /users`, `GET /users`, `GET /users/{id}`, `PUT /users/{id}`) use `response_model=User`, serializing the password hash directly into JSON responses delivered to clients.
- Password recovery and reset routes (`/auth/forgot-password`, `/auth/reset-password`, `/auth/change-password`) and incident analysis routes (`/api/incidents/analyze`) lack explicit response models, returning raw untyped dictionaries.

### Summary Statistics
- **Total Endpoints Audited**: 31
- **✅ Already Serialized**: 21 (67.7%)
- **⚠️ Partially Serialized / Over-exposing Fields**: 6 (19.4%)
- **❌ Not Serialized**: 4 (12.9%)

---

## Classification Taxonomy

| State | Indicator | Description |
|---|---|---|
| **Already Serialized** | ✅ | Has an explicit `response_model` and the schema accurately reflects client needs without over-exposing sensitive fields or internal models. |
| **Partially Serialized** | ⚠️ | Defines a `response_model` (or loose type annotation like `Dict[str, Any]`), but over-exposes sensitive fields (e.g., `hashed_password`), exposes internal domain/ORM entities, or lacks field-level typing. |
| **Not Serialized** | ❌ | Returns raw dictionaries or ORM objects without any `response_model` configured on the route handler. |

---

## 1. High-Priority Focus: Authentication & User Management Security Review

Routes handling authentication, user registration, and password recovery represent the highest risk surface for credential leakage and user enumeration.

> [!CAUTION]
> **Vulnerability Finding: `hashed_password` Leaked in Public API Responses**
>
> In [services/api/domain/models.py](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/services/api/domain/models.py), the `User` model is defined as:
> ```python
> class User(UserBase):
>     id: str
>     hashed_password: str
>     created_at: str
> ```
> Because `User` is used as the `response_model` across `GET /auth/me` and the entire `/users` CRUD suite, the password hash string is serialized and exposed over HTTP.

### Recommended DTO Schema Architecture
A dedicated projection model must be introduced:
```python
class UserResponse(BaseModel):
    id: str
    email: str
    is_active: bool
    role: Literal["admin", "manager", "user"]
    created_at: str

class MessageResponse(BaseModel):
    message: str
```

---

## 2. Comprehensive Endpoint Audit & Classification

### 2.1 Authentication Subsystem (`/auth`)

| Method | Route | Purpose | Current Response Behaviour | Status | Recommended Improvement & Output Shape |
|---|---|---|---|---|---|
| `POST` | `/auth/login` | Authenticate credentials and generate JWT token | `response_model=Token`, returns `{"access_token": "...", "token_type": "bearer"}` | ✅ Already serialized | None required. Accurately scopes response to bearer token without credential echoing. <br>**Shape**: `{"access_token": str, "token_type": str}` |
| `GET` | `/auth/me` | Retrieve current authenticated user profile | `response_model=User`, returns domain `User` entity | ⚠️ Partially serialized | **Security Fix Required**: Replace `response_model=User` with `UserResponse` to prevent leaking `hashed_password`. <br>**Target Shape**: <br>`{"id": str, "email": str, "is_active": bool, "role": str, "created_at": str}` |
| `POST` | `/auth/forgot-password` | Request password reset email (with anti-enumeration) | Untyped dict, no `response_model` decorator | ❌ Not serialized | **Add Schema**: Decorate with `response_model=MessageResponse`. Handler correctly returns generic message preventing email enumeration, but lacks OpenAPI schema. <br>**Target Shape**: <br>`{"message": str}` |
| `POST` | `/auth/reset-password` | Reset password using reset token | Untyped dict, no `response_model` decorator | ❌ Not serialized | **Add Schema**: Decorate with `response_model=MessageResponse`. <br>**Target Shape**: <br>`{"message": str}` |
| `POST` | `/auth/change-password` | Change password for authenticated session | Untyped dict, no `response_model` decorator | ❌ Not serialized | **Add Schema**: Decorate with `response_model=MessageResponse`. <br>**Target Shape**: <br>`{"message": str}` |

---

### 2.2 User Management Subsystem (`/users`)

| Method | Route | Purpose | Current Response Behaviour | Status | Recommended Improvement & Output Shape |
|---|---|---|---|---|---|
| `POST` | `/users` | Register a new user and initialize profile | `response_model=User`, returns domain `User` entity | ⚠️ Partially serialized | **Security Fix Required**: Exposes `hashed_password` on registration response. Replace with `response_model=UserResponse` (or `UserRegistrationResponse` including safe profile info). <br>**Target Shape**: <br>`{"id": str, "email": str, "is_active": bool, "role": str, "created_at": str}` |
| `GET` | `/users` | List all registered user accounts (Admin only) | `response_model=List[User]`, returns list of `User` domain entities | ⚠️ Partially serialized | **Security Fix Required**: Exposes `hashed_password` for all users in the system to admin callers. Replace with `response_model=List[UserResponse]`. <br>**Target Shape**: <br>`[{"id": str, "email": str, "is_active": bool, "role": str, "created_at": str}]` |
| `GET` | `/users/{user_id}` | Get specific user by ID (Admin only) | `response_model=User`, returns domain `User` entity | ⚠️ Partially serialized | **Security Fix Required**: Leaks `hashed_password`. Update to `response_model=UserResponse`. <br>**Target Shape**: <br>`{"id": str, "email": str, "is_active": bool, "role": str, "created_at": str}` |
| `PUT` | `/users/{user_id}` | Update user attributes (Admin only) | `response_model=User`, returns updated domain `User` entity | ⚠️ Partially serialized | **Security Fix Required**: Leaks `hashed_password`. Update to `response_model=UserResponse`. <br>**Target Shape**: <br>`{"id": str, "email": str, "is_active": bool, "role": str, "created_at": str}` |
| `DELETE` | `/users/{user_id}` | Delete user account and profile (Admin only) | Status 204, returns `None` (empty body) | ✅ Already serialized | None required. Correct standard REST status code and empty body response. |

---

### 2.3 User Profiles Subsystem (`/profiles`)

| Method | Route | Purpose | Current Response Behaviour | Status | Recommended Improvement & Output Shape |
|---|---|---|---|---|---|
| `GET` | `/profiles/me` | Fetch authenticated user's profile | `response_model=Profile`, returns `Profile` entity (`id`, `user_id`, `name`, `phone`, `address`) | ✅ Already serialized | None required. Fully typed and contains no sensitive credentials. <br>**Shape**: `{"id": str, "user_id": str, "name": Optional[str], "phone": Optional[str], "address": Optional[str]}` |
| `PUT` | `/profiles/me` | Update authenticated user's profile | `response_model=Profile`, returns updated `Profile` | ✅ Already serialized | None required. Schema is well-defined and appropriately scoped. <br>**Shape**: `{"id": str, "user_id": str, "name": Optional[str], "phone": Optional[str], "address": Optional[str]}` |

---

### 2.4 Incident Operations Subsystem (`/api/incidents`)

| Method | Route | Purpose | Current Response Behaviour | Status | Recommended Improvement & Output Shape |
|---|---|---|---|---|---|
| `GET` | `/api/incidents/summary` | Aggregated incident count metrics (by status, category, origin, branch) | `response_model=Dict[str, Any]`, returns generic dictionary | ⚠️ Partially serialized | **Improvement Required**: `Dict[str, Any]` is untyped and provides no contract for frontends. Create `IncidentSummaryResponse` schema with concrete count dictionaries. <br>**Target Shape**: <br>`{"total": int, "by_status": dict[str, int], "by_category": dict[str, int], "by_origin": dict[str, int], "by_branch": dict[str, int]}` |
| `GET` | `/api/incidents` | List incidents with query filters (`status`, `origin`, `branch`, `category`) | `response_model=List[IncidentResponseSchema]` | ✅ Already serialized | None required. DTO schema correctly handles incident metadata, enum values, and timestamps. <br>**Shape**: `[{"id": str, "title": str, "description": str, "category": str, "status": str, "origin": str, "branch": str, "created_at": str, "updated_at": str, "legacy_id": Optional[str]}]` |
| `POST` | `/api/incidents` | Create a new operational incident | `response_model=IncidentResponseSchema`, status 201 | ✅ Already serialized | None required. Properly validates input and maps to response DTO. |
| `GET` | `/api/incidents/{incident_id}` | Retrieve incident details by ID | `response_model=IncidentResponseSchema` | ✅ Already serialized | None required. Explicit and properly shaped. |
| `PATCH` | `/api/incidents/{incident_id}/status` | Transition incident lifecycle status | `response_model=IncidentResponseSchema` | ✅ Already serialized | None required. Returns updated incident adhering to lifecycle rules. |
| `POST` | `/api/incidents/analyze` | Ingest CSV stream and compute aggregate health metrics | Untyped dict, no `response_model` decorator | ❌ Not serialized | **Improvement Required**: Create explicit schema `IncidentAnalysisResponse(metrics: IncidentMetrics, diagnostics: IncidentDiagnostics)`. <br>**Target Shape**: <br>`{"metrics": {"total_processed": int, "valid_records": int, "invalid_records": int, "category_breakdown": dict, "status_breakdown": dict, "average_satisfaction_index": float}, "diagnostics": {"invalid_sample": list}}` |
| `GET` | `/api/incidents/results/export` | Download CSV export of last analysis result | Streaming response (`StreamingResponse`, media_type `text/csv`) | ✅ Already serialized (Binary/Stream) | None required. Standard HTTP streaming response with CSV attachment header. |

---

### 2.5 Supplier Management Subsystem (`/suppliers`)

| Method | Route | Purpose | Current Response Behaviour | Status | Recommended Improvement & Output Shape |
|---|---|---|---|---|---|
| `POST` | `/suppliers` | Create a new supplier record | `response_model=Supplier`, status 201 | ✅ Already serialized | None required. Explicit `Supplier` schema validates output. <br>**Shape**: `{"id": int, "name": str, "country": str, "categories": list[str], "cost_per_kg": float, "status": str, "updated_at": str}` |
| `GET` | `/suppliers` | List suppliers with country/category filters | `response_model=List[Supplier]` | ✅ Already serialized | None required. Returns validated list of suppliers. |
| `GET` | `/suppliers/{id}` | Retrieve supplier details by ID | `response_model=Supplier` | ✅ Already serialized | None required. |
| `PATCH` | `/suppliers/{id}/rate` | Update supplier rate (`cost_per_kg`) | `response_model=Supplier` | ✅ Already serialized | None required. |
| `PATCH` | `/suppliers/{id}/status` | Update supplier active/suspended status | `response_model=Supplier` | ✅ Already serialized | None required. |
| `DELETE` | `/suppliers/{id}` | Remove supplier record | Status 204, returns `None` | ✅ Already serialized | None required. Standard 204 No Content response. |

---

### 2.6 Inventory & Order Management Subsystem (`/inventory`)

| Method | Route | Purpose | Current Response Behaviour | Status | Recommended Improvement & Output Shape |
|---|---|---|---|---|---|
| `POST` | `/inventory/products` | Create product SKU and warehouse association | `response_model=ProductResponse`, status 201 | ✅ Already serialized | None required. Uses `ProductResponse` schema with calculated stock. <br>**Shape**: `{"id": int, "sku": str, "name": str, "warehouse_id": str, "low_stock_threshold": int, "current_stock": int, "created_at": datetime}` |
| `GET` | `/inventory/products` | List product SKUs with derived real-time stock | `response_model=List[ProductResponse]` | ✅ Already serialized | None required. Uses `List[ProductResponse]`. |
| `GET` | `/inventory/products/{id}` | Get product SKU details by ID | `response_model=ProductResponse` | ✅ Already serialized | None required. |
| `POST` | `/inventory/orders/inbound` | Create inbound inventory order (stock replenishment) | `response_model=OrderResponse`, status 201 | ✅ Already serialized | None required. Uses `OrderResponse` schema mapping stock entry. <br>**Shape**: `{"id": int, "order_type": str, "sku_id": int, "sku_code": str, "warehouse_id": str, "quantity": int, "user_uuid": str, "created_at": datetime}` |
| `POST` | `/inventory/orders/outbound` | Create outbound inventory order (stock dispatch) | `response_model=OrderResponse`, status 201 | ✅ Already serialized | None required. Validates available stock and returns `OrderResponse`. |
| `GET` | `/inventory/orders` | List all inventory orders (inbound/outbound) | `response_model=List[OrderResponse]` | ✅ Already serialized | None required. Returns `List[OrderResponse]`. |

---

## 3. Detailed Remediation Plan & Schema Specifications

To bring all 31 endpoints into full serialization compliance (100% ✅), implement the following changes in `services/api/`:

### Step 1: Add Public User & Message Response Schemas
In `domain/models.py` (or a dedicated `domain/schemas/user_schema.py`):
```python
from pydantic import BaseModel
from typing import Literal

class UserResponse(BaseModel):
    id: str
    email: str
    is_active: bool
    role: Literal["admin", "manager", "user"]
    created_at: str

class MessageResponse(BaseModel):
    message: str
```

### Step 2: Update Auth Routes (`presentation/api/auth_routes.py`)
- Change `GET /auth/me` from `response_model=User` to `response_model=UserResponse`.
- Add `response_model=MessageResponse` to `POST /auth/forgot-password`.
- Add `response_model=MessageResponse` to `POST /auth/reset-password`.
- Add `response_model=MessageResponse` to `POST /auth/change-password`.

### Step 3: Update User Management Routes (`presentation/api/user_routes.py`)
- Change `POST /users` from `response_model=User` to `response_model=UserResponse`.
- Change `GET /users` from `response_model=List[User]` to `response_model=List[UserResponse]`.
- Change `GET /users/{user_id}` from `response_model=User` to `response_model=UserResponse`.
- Change `PUT /users/{user_id}` from `response_model=User` to `response_model=UserResponse`.

### Step 4: Add Incident Summary & Analysis Schemas
In `domain/schemas/incident_schema.py`:
```python
from typing import Dict, List, Any
from pydantic import BaseModel

class IncidentSummaryResponse(BaseModel):
    total: int
    by_status: Dict[str, int]
    by_category: Dict[str, int]
    by_origin: Dict[str, int]
    by_branch: Dict[str, int]

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
- Update `GET /api/incidents/summary` to `response_model=IncidentSummaryResponse`.
- Update `POST /api/incidents/analyze` to `response_model=IncidentAnalysisResponse`.
