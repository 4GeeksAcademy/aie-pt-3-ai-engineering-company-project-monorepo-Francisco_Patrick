# Quickstart & Validation Guide: Dual Database Architecture + Inventory ORM

This guide outlines runnable scenarios to verify dual database configuration, ORM setup, stock calculations, and boundary guards.

## Prerequisites
- Python 3.11+ environment in `services/api`
- Dependencies installed via `uv` or `pip` (including `fastapi`, `sqlmodel`, `pydantic`, `psycopg2-binary`, `tinydb`)
- Valid `.env` file in `services/api/.env` containing `DATABASE_URL` and `JWT_SECRET_KEY`

---

## Runnable Verification Steps

### 1. Dual Database Startup & Schema Generation
Run the FastAPI backend server:
```bash
cd services/api
uv run uvicorn main:app --reload --port 8000
```
Verify that application logs indicate success:
- TinyDB client initialized (`db.json`)
- SQLModel engine connected and `SQLModel.metadata.create_all(engine)` executed.

### 2. Run Automated Test Suite
Execute backend tests using `pytest`:
```bash
cd services/api
uv run pytest tests/test_inventory.py -v
```
All unit & integration tests covering dual DB, stock calculation, auth checking, and negative stock rejection must pass cleanly.

### 3. Manual E2E Validation Flow (Swagger UI / curl)

1. **Obtain Auth Token**:
   ```bash
   curl -X POST "http://localhost:8000/auth/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin@trackflow.com&password=securepassword"
   ```
   Save the returned `access_token`.

2. **Create Product**:
   ```bash
   curl -X POST "http://localhost:8000/inventory/products" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"sku": "SKU-2001", "name": "Heavy Duty Pallet", "warehouse_id": "wh-la", "low_stock_threshold": 15}'
   ```
   Verify returned product has `current_stock`: 0.

3. **Inbound Stock Addition**:
   ```bash
   curl -X POST "http://localhost:8000/inventory/orders/inbound" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"sku_id": 1, "warehouse_id": "wh-la", "quantity": 100}'
   ```
   Verify stock for product 1 in `wh-la` is now 100 on `GET /inventory/products/1`.

4. **Negative Stock Guard (Must Reject)**:
   ```bash
   curl -X POST "http://localhost:8000/inventory/orders/outbound" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"sku_id": 1, "warehouse_id": "wh-la", "quantity": 150}'
   ```
   Verify response is `HTTP 400 Bad Request` with message `"Insufficient stock available in target warehouse"`.
