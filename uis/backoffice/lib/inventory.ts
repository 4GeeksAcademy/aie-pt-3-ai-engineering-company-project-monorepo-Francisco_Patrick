import { fetchWithAuth } from './api';

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
  return data;
}

/**
 * Registers an outbound inventory order (stock exit or consumption) in the backend.
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
    throw new Error(message);
  }

  const data = (await response.json()) as InventoryOrderRecord;
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
