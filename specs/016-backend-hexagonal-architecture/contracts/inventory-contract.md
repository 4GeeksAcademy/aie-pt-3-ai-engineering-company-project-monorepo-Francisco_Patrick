# Inventory & Stock API Contract

**Service**: `services/api`  
**Domain**: Inventory  
**Base Path**: `/inventory` (legacy alias) & `/api/v1/inventory` (canonical)  
**Storage Engine**: SQLModel / SQLite (`inventory.db`) or PostgreSQL  

---

## Endpoints Specification

### 1. Create Product (SKU)
* **Method**: `POST`
* **Path**: `/inventory/products` & `/api/v1/inventory/products`
* **Security**: Bearer JWT (`Depends(get_current_user)`)
* **Status**: `201 Created`
* **Request Payload (`ProductCreate`)**:
  ```json
  {
    "sku": "SKU-AUTO-001",
    "name": "Hydraulic Brake Pump",
    "warehouse_id": "wh-central",
    "low_stock_threshold": 15
  }
  ```
* **Response Payload (`ProductResponse`)**:
  ```json
  {
    "id": 1,
    "sku": "SKU-AUTO-001",
    "name": "Hydraulic Brake Pump",
    "warehouse_id": "wh-central",
    "current_stock": 0,
    "low_stock_threshold": 15,
    "is_low_stock": true
  }
  ```
* **Errors**: `400 Bad Request` (duplicate SKU code), `401 Unauthorized`

---

### 2. List Products
* **Method**: `GET`
* **Path**: `/inventory/products` & `/api/v1/inventory/products`
* **Security**: Public
* **Status**: `200 OK`
* **Cache**: 30s TTL (`inventory_products:all`)
* **Response Payload**: `List[ProductResponse]`

---

### 3. Get Product Detail
* **Method**: `GET`
* **Path**: `/inventory/products/{id}` & `/api/v1/inventory/products/{id}`
* **Security**: Public
* **Status**: `200 OK`
* **Cache**: 30s TTL (`inventory_products:{id}`)
* **Response Payload**: `ProductResponse`
* **Errors**: `404 Not Found`

---

### 4. Record Inbound Stock Entry
* **Method**: `POST`
* **Path**: `/inventory/orders/inbound` & `/api/v1/inventory/orders/inbound`
* **Security**: Bearer JWT (`Depends(get_current_user)`)
* **Status**: `201 Created`
* **Request Payload (`InboundOrderCreate`)**:
  ```json
  {
    "sku_id": 1,
    "warehouse_id": "wh-central",
    "quantity": 50
  }
  ```
* **Response Payload (`OrderResponse`)**:
  ```json
  {
    "order_id": 101,
    "sku_id": 1,
    "sku": "SKU-AUTO-001",
    "type": "inbound",
    "quantity": 50,
    "warehouse_id": "wh-central",
    "date": "2026-10-13T10:15:00Z"
  }
  ```
* **Errors**: `400 Bad Request` (`quantity <= 0`), `404 Not Found` (SKU does not exist), `401 Unauthorized`

---

### 5. Record Outbound Stock Exit
* **Method**: `POST`
* **Path**: `/inventory/orders/outbound` & `/api/v1/inventory/orders/outbound`
* **Security**: Bearer JWT (`Depends(get_current_user)`)
* **Status**: `201 Created`
* **Request Payload (`OutboundOrderCreate`)**:
  ```json
  {
    "sku_id": 1,
    "warehouse_id": "wh-central",
    "quantity": 20
  }
  ```
* **Response Payload (`OrderResponse`)**:
  ```json
  {
    "order_id": 102,
    "sku_id": 1,
    "sku": "SKU-AUTO-001",
    "type": "outbound",
    "quantity": 20,
    "warehouse_id": "wh-central",
    "date": "2026-10-13T10:20:00Z"
  }
  ```
* **Errors**: 
  * `400 Bad Request`: Insufficient stock available (`quantity > current_stock`)
  * `404 Not Found`: SKU does not exist
  * `401 Unauthorized`

---

### 6. List Historical Orders
* **Method**: `GET`
* **Path**: `/inventory/orders` & `/api/v1/inventory/orders`
* **Security**: Bearer JWT (`Depends(get_current_user)`)
* **Status**: `200 OK`
* **Response Payload**: `List[OrderResponse]`
* **Errors**: `401 Unauthorized`
