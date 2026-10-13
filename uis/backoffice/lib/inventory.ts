import { fetchWithAuth } from './api';
import { track } from '../app/services/telemetry';

/**
 * Domain entity representing an inventory product (SKU) stored in a warehouse.
 */
export interface InventoryProduct {
  readonly id: number;
  readonly sku: string;
  readonly name: string;
  readonly warehouse_id: string;
  readonly low_stock_threshold: number;
  readonly current_stock: number;
  readonly created_at: string;
}

/**
 * Payload payload schema for creating an inbound inventory order.
 */
export interface InboundOrderPayload {
  readonly sku_id: number;
  readonly warehouse_id: string;
  readonly quantity: number;
}

/**
 * Payload schema for creating an outbound inventory order.
 */
export interface OutboundOrderPayload {
  readonly sku_id: number;
  readonly warehouse_id: string;
  readonly quantity: number;
}

/**
 * Read-only inventory order ledger record schema returned by the backend API.
 */
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

/**
 * Backend error payload contract for JSON error parsing.
 */
interface ApiErrorBody {
  readonly detail?: string | ReadonlyArray<{ readonly msg?: string }> | undefined;
  readonly message?: string | undefined;
}

/**
 * Extracts a human-readable error message string from an API error response body.
 *
 * @param body - The parsed JSON error response body from the backend.
 * @param fallbackMessage - Default message to return if no specific detail is found.
 * @returns Human-readable string explaining the error.
 */
function extractErrorMessage(body: ApiErrorBody, fallbackMessage: string): string {
  if (typeof body.detail === 'string' && body.detail.trim().length > 0) {
    return body.detail;
  }
  if (Array.isArray(body.detail) && body.detail.length > 0) {
    const firstItem = body.detail[0];
    if (firstItem && typeof firstItem.msg === 'string') {
      return firstItem.msg;
    }
  }
  if (typeof body.message === 'string' && body.message.trim().length > 0) {
    return body.message;
  }
  return fallbackMessage;
}

/**
 * Fetches all inventory product SKUs from the backend API.
 * Emits stock_threshold_triggered for SKUs with low stock levels.
 *
 * @returns Promise resolving to an array of inventory product records.
 * @throws Error when the backend returns a non-2xx status or network failure occurs.
 */
export async function getInventoryProducts(): Promise<readonly InventoryProduct[]> {
  const response = await fetchWithAuth('/inventory/products', {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => ({}))) as ApiErrorBody;
    const message = extractErrorMessage(errorBody, 'Failed to fetch inventory products list.');
    throw new Error(message);
  }

  const data = (await response.json()) as readonly InventoryProduct[];

  // Emit stock threshold telemetry for any products at or below safety threshold
  for (const product of data) {
    if (product.current_stock <= product.low_stock_threshold) {
      track('stock_threshold_triggered', {
        skuId: product.sku,
        warehouseCode: product.warehouse_id,
        currentAvailableQuantity: product.current_stock,
        safetyThresholdQuantity: product.low_stock_threshold,
        triggerSeverity: product.current_stock === 0 ? 'CRITICAL' : 'WARNING',
      });
    }
  }

  return data;
}

/**
 * Fetches a single inventory product SKU by ID from the backend API.
 *
 * @param id - Numeric unique identifier of the target product SKU.
 * @returns Promise resolving to the target inventory product record.
 * @throws Error when product is not found (404) or API returns a non-2xx status code.
 */
export async function getInventoryProductById(id: number): Promise<InventoryProduct> {
  const response = await fetchWithAuth(`/inventory/products/${id}`, {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => ({}))) as ApiErrorBody;
    const message = extractErrorMessage(errorBody, `Product with ID ${id} not found.`);
    throw new Error(message);
  }

  const data = (await response.json()) as InventoryProduct;
  return data;
}

/**
 * Registers an inbound inventory order (supplier delivery) in the backend.
 * Emits inbound_order_created telemetry on success.
 *
 * @param payload - Inbound order details including sku_id, warehouse_id, and quantity.
 * @returns Promise resolving to the created order record.
 * @throws Error when validation fails (400/404/500) with details from response body.
 */
export async function createInboundOrder(payload: InboundOrderPayload): Promise<InventoryOrderRecord> {
  const response = await fetchWithAuth('/inventory/orders/inbound', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => ({}))) as ApiErrorBody;
    const message = extractErrorMessage(errorBody, 'Failed to submit inbound inventory order.');
    throw new Error(message);
  }

  const data = (await response.json()) as InventoryOrderRecord;

  track('inbound_order_created', {
    inboundOrderId: String(data.id),
    clientId: data.user_uuid,
    warehouseCode: data.warehouse_id,
    totalSkus: 1,
    totalUnits: data.quantity,
    sourceChannel: 'PORTAL',
  });

  return data;
}

/**
 * Registers an outbound inventory order (stock exit or consumption) in the backend.
 * Emits outbound_order_fulfilled on success or stock_validation_failed on error.
 *
 * @param payload - Outbound order details including sku_id, warehouse_id, and quantity.
 * @returns Promise resolving to the created order record.
 * @throws Error when stock is insufficient (400) or API returns a failure status code.
 */
export async function createOutboundOrder(payload: OutboundOrderPayload): Promise<InventoryOrderRecord> {
  const response = await fetchWithAuth('/inventory/orders/outbound', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => ({}))) as ApiErrorBody;
    const message = extractErrorMessage(errorBody, 'Failed to submit outbound inventory order.');

    track('stock_validation_failed', {
      orderId: 'PENDING',
      warehouseCode: payload.warehouse_id,
      skuId: String(payload.sku_id),
      expectedQuantity: payload.quantity,
      actualQuantity: 0,
      failureReason: message,
    });

    throw new Error(message);
  }

  const data = (await response.json()) as InventoryOrderRecord;

  track('outbound_order_fulfilled', {
    orderId: String(data.id),
    clientId: data.user_uuid,
    warehouseCode: data.warehouse_id,
    carrierCode: 'FEDEX',
    fulfillmentDurationSeconds: 1.5,
    totalItems: data.quantity,
  });

  return data;
}

/**
 * Fetches all historical inventory stock orders (inbound & outbound) from the backend API.
 *
 * @returns Promise resolving to an array of order records sorted chronologically.
 * @throws Error when backend request fails or returns non-2xx status code.
 */
export async function getInventoryOrders(): Promise<readonly InventoryOrderRecord[]> {
  const response = await fetchWithAuth('/inventory/orders', {
    method: 'GET',
    headers: {
      'Accept': 'application/json',
    },
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => ({}))) as ApiErrorBody;
    const message = extractErrorMessage(errorBody, 'Failed to fetch inventory orders history.');
    throw new Error(message);
  }

  const data = (await response.json()) as readonly InventoryOrderRecord[];
  return data;
}
