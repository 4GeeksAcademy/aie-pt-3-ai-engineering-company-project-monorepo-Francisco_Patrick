# Data Model & Typed Schemas: Backoffice Inventory Management Interface

## Overview
This document specifies the TypeScript interfaces, domain entities, and data structures utilized by the backoffice inventory management UI layer (`uis/backoffice/lib/inventory.ts`).

---

## TypeScript Domain Interfaces

### 1. Product (SKU) Model

Represents a TrackFlow inventory product item associated with a specific warehouse (`wh-la` or `wh-zgz`).

```typescript
export interface InventoryProduct {
  readonly id: number;
  readonly sku: string;
  readonly name: string;
  readonly warehouse_id: string;
  readonly low_stock_threshold: number;
  readonly current_stock: number;
  readonly created_at: string;
}
```

**Field Validation & UI Rules**:
- `sku`: Unique product code (e.g., `SKU-LA-101`).
- `warehouse_id`: Warehouse location identifier (`wh-la` for Los Angeles, `wh-zgz` for Zaragoza).
- `current_stock`: Derived inventory stock balance (`SUM(inbound) - SUM(outbound)`).
- `low_stock_threshold`: Numerical threshold for visual stock status indicators.

---

### 2. Inbound Order Payload (`InboundOrderCreate`)

Payload structure submitted to `POST /inventory/orders/inbound` to register incoming supplier deliveries.

```typescript
export interface InboundOrderPayload {
  readonly sku_id: number;
  readonly warehouse_id: string;
  readonly quantity: number;
}
```

**Field Validation & UI Rules**:
- `sku_id`: Must correspond to a valid existing product ID. Selected via UI dropdown showing `name` and `sku`.
- `warehouse_id`: Must match target warehouse (`wh-la` or `wh-zgz`).
- `quantity`: Positive integer (`gt: 0`).

---

### 3. Outbound Order Payload (`OutboundOrderCreate`)

Payload structure submitted to `POST /inventory/orders/outbound` to log stock exits or consumption.

```typescript
export interface OutboundOrderPayload {
  readonly sku_id: number;
  readonly warehouse_id: string;
  readonly quantity: number;
}
```

**Field Validation & UI Rules**:
- `sku_id`: Selected product ID.
- `quantity`: Positive integer (`gt: 0`). Client warning rendered if `quantity > current_stock`.

---

### 4. Order Record (`InventoryOrderResponse`)

Read-only inventory order ledger record returned by `GET /inventory/orders`, `POST /inventory/orders/inbound`, and `POST /inventory/orders/outbound`.

```typescript
export interface InventoryOrderRecord {
  readonly id: number;
  readonly order_type: 'inbound' | 'outbound';
  readonly sku_id: number;
  readonly sku_code: string;
  readonly warehouse_id: string;
  readonly quantity: number;
  readonly user_uuid: string;
  readonly created_at: string;
}
```

---

### 5. UI State Interfaces

```typescript
export interface StockStatusBadgeProps {
  readonly currentStock: number;
  readonly lowStockThreshold: number;
}

export type StockLevelStatus = 'healthy' | 'low' | 'out_of_stock';
```
