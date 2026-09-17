# Interface Contract: `/inventory` API Endpoints

## Base URL & Headers

- **Base URL**: `http://localhost:8000` (or `process.env.NEXT_PUBLIC_API_URL`)
- **Headers**:
  - `Content-Type: application/json`
  - `Authorization: Bearer <auth_token>` (for protected endpoints)

---

## Endpoints

### 1. `GET /inventory/products`

Fetches all product SKUs with their calculated `current_stock`.

- **Access**: Public / Protected
- **Response**: `200 OK`
```json
[
  {
    "id": 1,
    "sku": "SKU-LA-001",
    "name": "Heavy Duty Shipping Box L",
    "warehouse_id": "wh-la",
    "low_stock_threshold": 10,
    "current_stock": 45,
    "created_at": "2026-09-17T10:00:00Z"
  }
]
```

---

### 2. `GET /inventory/products/{id}`

Fetches a specific product by ID with its calculated `current_stock`.

- **Access**: Public / Protected
- **Response**: `200 OK`
```json
{
  "id": 1,
  "sku": "SKU-LA-001",
  "name": "Heavy Duty Shipping Box L",
  "warehouse_id": "wh-la",
  "low_stock_threshold": 10,
  "current_stock": 45,
  "created_at": "2026-09-17T10:00:00Z"
}
```
- **Error Response**: `404 Not Found`
```json
{
  "detail": "Product with ID 999 not found"
}
```

---

### 3. `POST /inventory/orders/inbound`

Registers an inbound delivery (`StockEntry`), incrementing derived inventory stock.

- **Access**: Protected (`Authorization: Bearer <token>`)
- **Request Body**:
```json
{
  "sku_id": 1,
  "warehouse_id": "wh-la",
  "quantity": 50
}
```
- **Response**: `201 Created`
```json
{
  "id": 101,
  "order_type": "inbound",
  "sku_id": 1,
  "sku_code": "SKU-LA-001",
  "warehouse_id": "wh-la",
  "quantity": 50,
  "user_uuid": "usr-8f4b2a9c",
  "created_at": "2026-09-17T11:15:00Z"
}
```
- **Error Responses**:
  - `400 Bad Request`: `{ "detail": "Quantity must be greater than 0" }`
  - `404 Not Found`: `{ "detail": "Product with ID 999 not found" }`

---

### 4. `POST /inventory/orders/outbound`

Registers an outbound stock exit (`StockExit`), reducing derived inventory stock. Validates available stock balance.

- **Access**: Protected (`Authorization: Bearer <token>`)
- **Request Body**:
```json
{
  "sku_id": 1,
  "warehouse_id": "wh-la",
  "quantity": 5
}
```
- **Response**: `201 Created`
```json
{
  "id": 102,
  "order_type": "outbound",
  "sku_id": 1,
  "sku_code": "SKU-LA-001",
  "warehouse_id": "wh-la",
  "quantity": 5,
  "user_uuid": "usr-8f4b2a9c",
  "created_at": "2026-09-17T11:20:00Z"
}
```
- **Error Responses**:
  - `400 Bad Request` (Insufficient Stock):
    ```json
    {
      "detail": "Insufficient stock for SKU 'SKU-LA-001' in warehouse 'wh-la'. Requested: 100, Available: 45"
    }
    ```

---

### 5. `GET /inventory/orders`

Lists all inbound and outbound stock orders chronologically.

- **Access**: Protected (`Authorization: Bearer <token>`)
- **Response**: `200 OK`
```json
[
  {
    "id": 102,
    "order_type": "outbound",
    "sku_id": 1,
    "sku_code": "SKU-LA-001",
    "warehouse_id": "wh-la",
    "quantity": 5,
    "user_uuid": "usr-8f4b2a9c",
    "created_at": "2026-09-17T11:20:00Z"
  },
  {
    "id": 101,
    "order_type": "inbound",
    "sku_id": 1,
    "sku_code": "SKU-LA-001",
    "warehouse_id": "wh-la",
    "quantity": 50,
    "user_uuid": "usr-8f4b2a9c",
    "created_at": "2026-09-17T11:15:00Z"
  }
]
```
