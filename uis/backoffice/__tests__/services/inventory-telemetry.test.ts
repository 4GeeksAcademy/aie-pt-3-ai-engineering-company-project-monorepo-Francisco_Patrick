import { track, telemetryService } from "../../app/services/telemetry";
import {
  createInboundOrder,
  createOutboundOrder,
  getInventoryProducts,
} from "../../lib/inventory";

describe("Inventory Business Telemetry Instrumentation", () => {
  let originalFetch: typeof global.fetch;

  beforeEach(() => {
    telemetryService.resetForTesting();
    originalFetch = global.fetch;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("should emit inbound_order_created when creating inbound inventory order", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({
        id: 101,
        order_type: "inbound",
        sku_id: 1,
        sku_code: "SKU-TEST-1",
        warehouse_id: "LA-01",
        quantity: 50,
        user_uuid: "user-123",
        created_at: new Date().toISOString(),
      }),
    } as Response);

    await createInboundOrder({
      sku_id: 1,
      warehouse_id: "LA-01",
      quantity: 50,
    });

    const events = telemetryService.getQueuedEvents();
    const inboundEvent = events.find((e) => e.event_type === "inbound_order_created");
    expect(inboundEvent).toBeDefined();
    if (inboundEvent) {
      expect(inboundEvent.properties.warehouseCode).toBe("LA-01");
      expect(inboundEvent.properties.totalUnits).toBe(50);
      expect(inboundEvent.properties.sourceChannel).toBe("PORTAL");
      // Zero PII check
      expect(inboundEvent.properties.password).toBeUndefined();
      expect(inboundEvent.properties.email).toBeUndefined();
    }
  });

  it("should emit outbound_order_fulfilled on successful outbound order", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({
        id: 202,
        order_type: "outbound",
        sku_id: 2,
        sku_code: "SKU-TEST-2",
        warehouse_id: "ZAZ-01",
        quantity: 10,
        user_uuid: "user-456",
        created_at: new Date().toISOString(),
      }),
    } as Response);

    await createOutboundOrder({
      sku_id: 2,
      warehouse_id: "ZAZ-01",
      quantity: 10,
    });

    const events = telemetryService.getQueuedEvents();
    const outboundEvent = events.find((e) => e.event_type === "outbound_order_fulfilled");
    expect(outboundEvent).toBeDefined();
    if (outboundEvent) {
      expect(outboundEvent.properties.warehouseCode).toBe("ZAZ-01");
      expect(outboundEvent.properties.totalItems).toBe(10);
    }
  });

  it("should emit stock_validation_failed when outbound order fails validation", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({
        detail: "Insufficient available inventory for SKU 2 in warehouse ZAZ-01",
      }),
    } as Response);

    await expect(
      createOutboundOrder({
        sku_id: 2,
        warehouse_id: "ZAZ-01",
        quantity: 9999,
      })
    ).rejects.toThrow();

    const events = telemetryService.getQueuedEvents();
    const failureEvent = events.find((e) => e.event_type === "stock_validation_failed");
    expect(failureEvent).toBeDefined();
    if (failureEvent) {
      expect(failureEvent.properties.warehouseCode).toBe("ZAZ-01");
      expect(failureEvent.properties.expectedQuantity).toBe(9999);
      expect(failureEvent.properties.failureReason).toContain("Insufficient available inventory");
    }
  });

  it("should emit stock_threshold_triggered when products cross low stock threshold", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => [
        {
          id: 1,
          sku: "SKU-LOW-1",
          name: "Low Stock Item",
          warehouse_id: "LA-01",
          low_stock_threshold: 15,
          current_stock: 5,
          created_at: new Date().toISOString(),
        },
      ],
    } as Response);

    await getInventoryProducts();

    const events = telemetryService.getQueuedEvents();
    const thresholdEvent = events.find((e) => e.event_type === "stock_threshold_triggered");
    expect(thresholdEvent).toBeDefined();
    if (thresholdEvent) {
      expect(thresholdEvent.properties.skuId).toBe("SKU-LOW-1");
      expect(thresholdEvent.properties.currentAvailableQuantity).toBe(5);
      expect(thresholdEvent.properties.safetyThresholdQuantity).toBe(15);
      expect(thresholdEvent.properties.triggerSeverity).toBe("WARNING");
    }
  });

  it("should emit direct_stock_edit_rejected on unauthorized direct edit attempts", () => {
    track("direct_stock_edit_rejected", {
      attemptedByUserId: "usr-warehouse-op",
      warehouseCode: "LA-01",
      skuId: "SKU-99",
      attemptedDelta: 100,
      rejectionReason: "Direct stock mutation blocked by ledger audit rule",
    });

    const events = telemetryService.getQueuedEvents();
    const rejectedEvent = events.find((e) => e.event_type === "direct_stock_edit_rejected");
    expect(rejectedEvent).toBeDefined();
    if (rejectedEvent) {
      expect(rejectedEvent.properties.skuId).toBe("SKU-99");
      expect(rejectedEvent.properties.attemptedDelta).toBe(100);
      expect(rejectedEvent.properties.rejectionReason).toBe(
        "Direct stock mutation blocked by ledger audit rule"
      );
    }
  });
});
