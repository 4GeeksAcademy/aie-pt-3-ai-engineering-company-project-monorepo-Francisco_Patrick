# Suppliers API Contract

**Service**: `services/api`  
**Domain**: Suppliers  
**Base Path**: `/suppliers` (legacy alias) & `/api/v1/suppliers` (canonical)  
**Security**: Bearer JWT (`Depends(get_current_user)`)  

---

## Endpoints Specification

### 1. Create Supplier
* **Method**: `POST`
* **Path**: `/suppliers` & `/api/v1/suppliers`
* **Status**: `201 Created`
* **Request Payload**:
  ```json
  {
    "name": "Global Cargo Logistics",
    "country": "Germany",
    "category": "freight",
    "cost_per_kg": 4.50
  }
  ```
* **Response Payload (`SupplierResponse`)**:
  ```json
  {
    "id": 1,
    "name": "Global Cargo Logistics",
    "country": "Germany",
    "category": "freight",
    "cost_per_kg": 4.50,
    "status": "active",
    "created_at": "2026-10-13T10:00:00Z",
    "updated_at": "2026-10-13T10:00:00Z"
  }
  ```
* **Errors**: `400 Bad Request` (invalid body/rates), `401 Unauthorized`

---

### 2. List Suppliers
* **Method**: `GET`
* **Path**: `/suppliers` & `/api/v1/suppliers`
* **Query Parameters**:
  * `country` (optional string): filter by origin country
  * `category` (optional string): filter by supplier category
* **Status**: `200 OK`
* **Cache**: 60s TTL (`suppliers:country=...&category=...`)
* **Response Payload**: `List[SupplierResponse]`

---

### 3. Get Supplier Detail
* **Method**: `GET`
* **Path**: `/suppliers/{id}` & `/api/v1/suppliers/{id}`
* **Path Parameters**: `id: int`
* **Status**: `200 OK`
* **Response Payload**: `SupplierResponse`
* **Errors**: `404 Not Found`, `401 Unauthorized`

---

### 4. Update Supplier Rate
* **Method**: `PATCH`
* **Path**: `/suppliers/{id}/rate` & `/api/v1/suppliers/{id}/rate`
* **Request Payload**:
  ```json
  {
    "cost_per_kg": 4.25
  }
  ```
* **Status**: `200 OK`
* **Response Payload**: `SupplierResponse`
* **Errors**: `400 Bad Request` (`cost_per_kg <= 0`), `404 Not Found`, `401 Unauthorized`

---

### 5. Update Supplier Status
* **Method**: `PATCH`
* **Path**: `/suppliers/{id}/status` & `/api/v1/suppliers/{id}/status`
* **Request Payload**:
  ```json
  {
    "status": "suspended"
  }
  ```
* **Status**: `200 OK`
* **Response Payload**: `SupplierResponse`
* **Errors**: `400 Bad Request` (invalid status enum), `404 Not Found`, `401 Unauthorized`

---

### 6. Delete Supplier
* **Method**: `DELETE`
* **Path**: `/suppliers/{id}` & `/api/v1/suppliers/{id}`
* **Status**: `204 No Content`
* **Errors**: `404 Not Found`, `401 Unauthorized`
