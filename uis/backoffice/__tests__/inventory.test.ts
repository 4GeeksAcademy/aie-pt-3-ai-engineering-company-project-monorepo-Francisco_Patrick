import {
  getInventoryProducts,
  getInventoryProductById,
  createInboundOrder,
  createOutboundOrder,
  getInventoryOrders,
  type InventoryProduct,
  type InventoryOrderRecord,
} from '../lib/inventory';

// Mock global fetch
const globalFetch = jest.fn() as jest.MockedFunction<typeof fetch>;
global.fetch = globalFetch;

describe('Centralized Inventory API Integration Layer (lib/inventory.ts)', (): void => {
  beforeEach((): void => {
    jest.clearAllMocks();
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('auth_token', 'mock-bearer-token');
    }
  });

  describe('getInventoryProducts', (): void => {
    test('Happy Path: returns list of products with current stock values', async (): Promise<void> => {
      const mockProducts: readonly InventoryProduct[] = [
        {
          id: 1,
          sku: 'SKU-LA-001',
          name: 'Heavy Duty Shipping Box L',
          warehouse_id: 'wh-la',
          low_stock_threshold: 10,
          current_stock: 45,
          created_at: '2026-09-17T10:00:00Z',
        },
      ];

      globalFetch.mockResolvedValueOnce({
        ok: true,
        json: async (): Promise<unknown> => mockProducts,
      } as Response);

      const result = await getInventoryProducts();

      expect(result).toEqual(mockProducts);
      expect(globalFetch).toHaveBeenCalledWith(
        expect.stringContaining('/inventory/products'),
        expect.objectContaining({
          method: 'GET',
          headers: expect.objectContaining({
            Authorization: 'Bearer mock-bearer-token',
          }),
        })
      );
    });

    test('Failure Mode: throws Error when API returns non-2xx status code', async (): Promise<void> => {
      globalFetch.mockResolvedValueOnce({
        ok: false,
        json: async (): Promise<unknown> => ({ detail: 'Internal Server Error' }),
      } as Response);

      await expect(getInventoryProducts()).rejects.toThrow('Internal Server Error');
    });
  });

  describe('getInventoryProductById', (): void => {
    test('Happy Path: returns target product by ID', async (): Promise<void> => {
      const mockProduct: InventoryProduct = {
        id: 1,
        sku: 'SKU-LA-001',
        name: 'Heavy Duty Shipping Box L',
        warehouse_id: 'wh-la',
        low_stock_threshold: 10,
        current_stock: 45,
        created_at: '2026-09-17T10:00:00Z',
      };

      globalFetch.mockResolvedValueOnce({
        ok: true,
        json: async (): Promise<unknown> => mockProduct,
      } as Response);

      const result = await getInventoryProductById(1);

      expect(result).toEqual(mockProduct);
      expect(globalFetch).toHaveBeenCalledWith(
        expect.stringContaining('/inventory/products/1'),
        expect.objectContaining({ method: 'GET' })
      );
    });

    test('Failure Mode: throws Error when product is not found (404)', async (): Promise<void> => {
      globalFetch.mockResolvedValueOnce({
        ok: false,
        json: async (): Promise<unknown> => ({ detail: 'Product with ID 999 not found' }),
      } as Response);

      await expect(getInventoryProductById(999)).rejects.toThrow('Product with ID 999 not found');
    });
  });

  describe('createInboundOrder', (): void => {
    test('Happy Path: posts inbound order payload and returns created record', async (): Promise<void> => {
      const mockOrderRecord: InventoryOrderRecord = {
        id: 101,
        order_type: 'inbound',
        sku_id: 1,
        sku_code: 'SKU-LA-001',
        warehouse_id: 'wh-la',
        quantity: 50,
        user_uuid: 'usr-12345678',
        created_at: '2026-09-17T11:00:00Z',
      };

      globalFetch.mockResolvedValueOnce({
        ok: true,
        json: async (): Promise<unknown> => mockOrderRecord,
      } as Response);

      const payload = { sku_id: 1, warehouse_id: 'wh-la', quantity: 50 };
      const result = await createInboundOrder(payload);

      expect(result).toEqual(mockOrderRecord);
      expect(globalFetch).toHaveBeenCalledWith(
        expect.stringContaining('/inventory/orders/inbound'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(payload),
        })
      );
    });

    test('Failure Mode: throws Error when payload validation fails', async (): Promise<void> => {
      globalFetch.mockResolvedValueOnce({
        ok: false,
        json: async (): Promise<unknown> => ({ detail: 'Quantity must be greater than 0' }),
      } as Response);

      await expect(
        createInboundOrder({ sku_id: 1, warehouse_id: 'wh-la', quantity: 0 })
      ).rejects.toThrow('Quantity must be greater than 0');
    });
  });

  describe('createOutboundOrder', (): void => {
    test('Happy Path: posts outbound order payload and returns created record', async (): Promise<void> => {
      const mockOrderRecord: InventoryOrderRecord = {
        id: 102,
        order_type: 'outbound',
        sku_id: 1,
        sku_code: 'SKU-LA-001',
        warehouse_id: 'wh-la',
        quantity: 5,
        user_uuid: 'usr-12345678',
        created_at: '2026-09-17T11:05:00Z',
      };

      globalFetch.mockResolvedValueOnce({
        ok: true,
        json: async (): Promise<unknown> => mockOrderRecord,
      } as Response);

      const payload = { sku_id: 1, warehouse_id: 'wh-la', quantity: 5 };
      const result = await createOutboundOrder(payload);

      expect(result).toEqual(mockOrderRecord);
      expect(globalFetch).toHaveBeenCalledWith(
        expect.stringContaining('/inventory/orders/outbound'),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify(payload),
        })
      );
    });

    test('Failure Mode: surfaces HTTP 400 insufficient stock error message', async (): Promise<void> => {
      const errorMsg = "Insufficient stock for SKU 'SKU-LA-001' in warehouse 'wh-la'. Requested: 100, Available: 45";
      globalFetch.mockResolvedValueOnce({
        ok: false,
        json: async (): Promise<unknown> => ({ detail: errorMsg }),
      } as Response);

      await expect(
        createOutboundOrder({ sku_id: 1, warehouse_id: 'wh-la', quantity: 100 })
      ).rejects.toThrow(errorMsg);
    });
  });

  describe('getInventoryOrders', (): void => {
    test('Happy Path: returns array of historical inventory orders', async (): Promise<void> => {
      const mockOrders: readonly InventoryOrderRecord[] = [
        {
          id: 102,
          order_type: 'outbound',
          sku_id: 1,
          sku_code: 'SKU-LA-001',
          warehouse_id: 'wh-la',
          quantity: 5,
          user_uuid: 'usr-12345678',
          created_at: '2026-09-17T11:05:00Z',
        },
        {
          id: 101,
          order_type: 'inbound',
          sku_id: 1,
          sku_code: 'SKU-LA-001',
          warehouse_id: 'wh-la',
          quantity: 50,
          user_uuid: 'usr-12345678',
          created_at: '2026-09-17T11:00:00Z',
        },
      ];

      globalFetch.mockResolvedValueOnce({
        ok: true,
        json: async (): Promise<unknown> => mockOrders,
      } as Response);

      const result = await getInventoryOrders();

      expect(result).toEqual(mockOrders);
      expect(globalFetch).toHaveBeenCalledWith(
        expect.stringContaining('/inventory/orders'),
        expect.objectContaining({ method: 'GET' })
      );
    });
  });
});
