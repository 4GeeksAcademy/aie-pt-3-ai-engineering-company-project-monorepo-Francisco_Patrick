# Data Model: Backend Hexagonal Architecture

**Feature**: Backend Architecture - Switch to Hexagonal  
**Branch**: `016-backend-hexagonal-architecture`  
**Date**: 2026-10-13  
**Status**: Complete  

---

## Overview

This document specifies the target domain entities, value objects, validation rules, state transitions, and persistence mappings for the TrackFlow backend (`services/api`). 

In accordance with Hexagonal Architecture:
1. **Domain Entities** represent pure business models with zero dependencies on database engines (TinyDB, SQLModel) or transport frameworks (FastAPI).
2. **Persistence Entities (ORM / DB Rows)** represent storage schemas encapsulated exclusively within driven adapters (`infrastructure/persistence/`).
3. **Application DTOs** represent request and response serialization schemas used at presentation and application boundaries.

---

## 1. Domain Entities & Value Objects

### 1.1. Suppliers Domain (`domain/suppliers/models.py`)

```python
class Supplier(BaseModel):
    id: Optional[int] = None
    name: str
    country: str
    category: str
    cost_per_kg: float
    status: Literal["active", "suspended"] = "active"
    created_at: str
    updated_at: str
```

* **Validation Rules**:
  * `cost_per_kg > 0.0`: Must be positive float.
  * `status`: Restricted to `"active"` or `"suspended"`.
  * `name`, `country`, `category`: Non-empty strings.
* **Relationships**: Standalone reference entity.
* **Storage Mapping**: TinyDB document in table `'suppliers'`.

---

### 1.2. Inventory Domain (`domain/inventory/models.py`)

#### SKU (Stock Keeping Unit)
```python
class SKU(BaseModel):
    id: Optional[int] = None
    sku: str
    name: str
    warehouse_id: str
    low_stock_threshold: int = 10
```

#### StockEntry (Inbound Inventory Order)
```python
class StockEntry(BaseModel):
    id: Optional[int] = None
    sku_id: int
    warehouse_id: str
    quantity: int
    date: str
```

#### StockExit (Outbound Inventory Order)
```python
class StockExit(BaseModel):
    id: Optional[int] = None
    sku_id: int
    warehouse_id: str
    quantity: int
    date: str
```

#### InventoryProduct (Calculated Domain Projection)
```python
class InventoryProduct(BaseModel):
    id: int
    sku: str
    name: str
    warehouse_id: str
    current_stock: int
    low_stock_threshold: int
    is_low_stock: bool
```

* **Validation & Business Invariants**:
  * `sku`: Unique alphanumeric SKU code across the catalog.
  * `quantity`: Must be integer > 0 for both inbound and outbound transactions.
  * `low_stock_threshold`: Integer >= 0.
  * **Stock Invariant**: An outbound order cannot be processed if `quantity > current_stock(sku_id, warehouse_id)`. Attempting to do so raises `InsufficientStockError`.
  * `current_stock`: Dynamically computed as $\sum(\text{Inbound Quantity}) - \sum(\text{Outbound Quantity})$.
* **Storage Mapping**: Relational tables in SQLite/PostgreSQL managed via SQLModel adapter:
  * Table `sku` -> `SKU`
  * Table `stockentry` -> `StockEntry`
  * Table `stockexit` -> `StockExit`

---

### 1.3. Telemetry Domain (`domain/telemetry/models.py`)

```python
class TelemetryEvent(BaseModel):
    event_id: str  # UUIDv4
    session_id: str
    event_type: str
    timestamp: datetime
    schema_version: str
    payload: Dict[str, Any]
```

* **Validation Rules**:
  * `event_id`: Valid UUIDv4 string.
  * `event_type`: Alphanumeric with dots/dashes (e.g., `user.login`, `cart.checkout`, `page.view`).
  * `schema_version`: Semantic version string (e.g., `1.0.0`).
  * `session_id`: Non-empty pseudonymized identifier.
* **Storage Mapping**: Ephemeral logging sink (`TelemetrySinkPort`).

---

### 1.4. Auth & User Management Domain (`domain/auth/models.py`)

#### User Entity
```python
class User(BaseModel):
    id: str
    email: str
    hashed_password: str
    role: Literal["user", "admin"] = "user"
    is_active: bool = True
    created_at: str
    updated_at: str
```

#### User Profile Entity
```python
class Profile(BaseModel):
    user_id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    updated_at: str
```

#### Password Reset Token Value Object
```python
class PasswordResetToken(BaseModel):
    token: str
    user_id: str
    expires_at: datetime
    is_used: bool = False
```

#### Audit Log Record
```python
class AuditLog(BaseModel):
    id: str
    user_id: str
    action: str
    timestamp: datetime
    details: Dict[str, Any] = Field(default_factory=dict)
```

* **Validation & Security Invariants**:
  * `email`: Valid RFC 5322 email string, strictly unique across users.
  * `hashed_password`: Bcrypt cryptographic hash; raw passwords must never be stored in this entity.
  * `PasswordResetToken`: Single-use token with 15-minute expiration window.
* **Storage Mapping**: TinyDB tables `'users'`, `'profiles'`, `'password_reset_tokens'`, `'audit_logs'`.

---

### 1.5. Incident Management Domain (`domain/incidents/models.py`)

```python
IncidentStatus = Literal["open", "in_progress", "resolved", "closed"]
IncidentCategory = Literal["warehouse", "reverse_logistics", "last_mile", "customer_experience"]
IncidentOrigin = Literal["customer", "internal", "partner"]

class Incident(BaseModel):
    id: str
    title: str
    description: str
    category: IncidentCategory
    status: IncidentStatus = "open"
    origin: IncidentOrigin = "customer"
    branch: str
    satisfaction_index: Optional[float] = None
    created_at: str
    updated_at: str
```

* **Lifecycle State Transitions**:
  ```mermaid
  stateDiagram-v2
      [*] --> open : Create Incident
      open --> in_progress : Assign / Start
      open --> closed : Dismiss / Direct Close
      in_progress --> resolved : Remediate
      in_progress --> open : Return to Queue
      resolved --> closed : Confirm Resolution
      resolved --> in_progress : Reopen
      closed --> [*]
  ```
* **Validation Rules**:
  * `satisfaction_index`: If provided, float between `1.0` and `5.0`.
  * `title`: Non-empty string, max 200 characters.
  * `status`, `category`, `origin`: Strictly constrained to predefined literals.
* **Storage Mapping**: TinyDB table `'incidents'`.

---

## 2. Entity-to-Storage Mapping Strategy

| Domain Entity | Storage Engine | Concrete Adapter Class | Mapping Responsibility |
| :--- | :--- | :--- | :--- |
| `Supplier` | TinyDB (`suppliers`) | `TinyDBSupplierRepository` | Serializes entity to dict with doc ID; deserializes doc to `Supplier`. |
| `SKU` | SQLModel / SQLite | `SQLModelInventoryRepository` | Converts between `domain.SKU` and `infrastructure.sqlmodel.models.SKU`. |
| `StockEntry` | SQLModel / SQLite | `SQLModelInventoryRepository` | Converts between `domain.StockEntry` and `infrastructure.sqlmodel.models.StockEntry`. |
| `StockExit` | SQLModel / SQLite | `SQLModelInventoryRepository` | Converts between `domain.StockExit` and `infrastructure.sqlmodel.models.StockExit`. |
| `User` | TinyDB (`users`) | `TinyDBUserRepository` | Converts between TinyDB document and `domain.User`. |
| `Profile` | TinyDB (`profiles`) | `TinyDBProfileRepository` | Converts between TinyDB document and `domain.Profile`. |
| `Incident` | TinyDB (`incidents`) | `TinyDBIncidentRepository` | Converts between TinyDB document and `domain.Incident`. |
| `TelemetryEvent` | Logger / Stream | `LoggingTelemetrySink` | Formats event for structured JSON log stream. |

---

## 3. Data Integrity & Validation Enforcement

1. **Domain Boundary Invariant Check**: Domain models enforce structural typing and invariants via Pydantic validators upon instantiation.
2. **Zero Leaked Persistence Primitives**: ORM models (`SQLModel` instances) never cross repository adapter boundaries into application services.
3. **Zero Sensitive Data Exposure**: Sensitive attributes (`hashed_password`, raw tokens) are filtered when projecting domain entities to presentation DTOs (`UserResponse`).
