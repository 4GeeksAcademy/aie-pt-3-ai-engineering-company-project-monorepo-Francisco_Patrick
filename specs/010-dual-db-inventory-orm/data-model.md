# Data Model: Dual Database Architecture + Inventory ORM

## Overview
This document defines the entity schemas for Supabase (SQLModel ORM models in `models.py`) and API data contracts (Pydantic schemas in `schemas.py`).

---

## 1. ORM Models (`services/api/models.py`)

### `SKU` (Product Entity)
- **Table Name**: `sku`
- **Fields**:
  - `id`: `Optional[int]` (Primary Key, Auto-increment)
  - `sku`: `str` (Indexed, Unique e.g., "SKU-1001")
  - `name`: `str` (Item title e.g. "Commercial Shipping Box A")
  - `warehouse_id`: `str` (Warehouse partition key e.g., "wh-la" or "wh-zgz")
  - `low_stock_threshold`: `int` (Default: 10)
  - `created_at`: `datetime` (Default: UTC now)

### `StockEntry` (Inbound Order Entity)
- **Table Name**: `stock_entry`
- **Fields**:
  - `id`: `Optional[int]` (Primary Key, Auto-increment)
  - `sku_id`: `int` (Foreign Key -> `sku.id`)
  - `warehouse_id`: `str` (Warehouse partition identifier)
  - `quantity`: `int` (Must be > 0)
  - `user_uuid`: `str` (TinyDB User UUID reference string)
  - `created_at`: `datetime` (Default: UTC now)

### `StockExit` (Outbound Order Entity)
- **Table Name**: `stock_exit`
- **Fields**:
  - `id`: `Optional[int]` (Primary Key, Auto-increment)
  - `sku_id`: `int` (Foreign Key -> `sku.id`)
  - `warehouse_id`: `str` (Warehouse partition identifier)
  - `quantity`: `int` (Must be > 0)
  - `user_uuid`: `str` (TinyDB User UUID reference string)
  - `created_at`: `datetime` (Default: UTC now)

---

## 2. Pydantic Schemas (`services/api/schemas.py`)

### SKU / Product Schemas
- **`ProductCreate`**:
  - `sku`: `str`
  - `name`: `str`
  - `warehouse_id`: `str`
  - `low_stock_threshold`: `int = 10`
- **`ProductResponse`**:
  - `id`: `int`
  - `sku`: `str`
  - `name`: `str`
  - `warehouse_id`: `str`
  - `low_stock_threshold`: `int`
  - `current_stock`: `int` *(Calculated dynamically: SUM(inbound) - SUM(outbound) for this SKU & warehouse)*
  - `created_at`: `datetime`

### Order Schemas
- **`InboundOrderCreate`**:
  - `sku_id`: `int`
  - `warehouse_id`: `str`
  - `quantity`: `int` (gt=0)
- **`OutboundOrderCreate`**:
  - `sku_id`: `int`
  - `warehouse_id`: `str`
  - `quantity`: `int` (gt=0)
- **`OrderResponse`**:
  - `id`: `int`
  - `order_type`: `str` ("inbound" | "outbound")
  - `sku_id`: `int`
  - `sku_code`: `str`
  - `warehouse_id`: `str`
  - `quantity`: `int`
  - `user_uuid`: `str`
  - `created_at`: `datetime`
