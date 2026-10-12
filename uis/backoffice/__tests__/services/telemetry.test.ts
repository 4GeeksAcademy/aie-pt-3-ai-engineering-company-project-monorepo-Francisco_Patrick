import { telemetryService, track } from "../../app/services/telemetry";
import type { TelemetryEvent } from "../../app/services/telemetry-types";

describe("TelemetryService", () => {
  let originalFetch: typeof global.fetch;
  let sendBeaconMock: jest.Mock;

  beforeEach(() => {
    jest.useFakeTimers();
    originalFetch = global.fetch;
    sendBeaconMock = jest.fn().mockReturnValue(true);

    Object.defineProperty(global.navigator, "sendBeacon", {
      value: sendBeaconMock,
      writable: true,
      configurable: true,
    });

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ received: 1 }),
    } as Response);

    telemetryService.resetForTesting();
  });

  afterEach(() => {
    jest.clearAllTimers();
    jest.useRealTimers();
    global.fetch = originalFetch;
  });

  it("should queue events without initiating immediate fetch calls", () => {
    track("inbound_order_created", {
      inboundOrderId: "INB-100",
      clientId: "client-1",
      warehouseCode: "LA-01",
      totalSkus: 2,
      totalUnits: 10,
      sourceChannel: "PORTAL",
    });

    expect(telemetryService.getQueueSize()).toBe(1);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("should automatically enrich events with standard envelope metadata", () => {
    track("stock_threshold_triggered", {
      skuId: "SKU-999",
      warehouseCode: "LA-01",
      currentAvailableQuantity: 4,
      safetyThresholdQuantity: 10,
      triggerSeverity: "WARNING",
    });

    const queuedEvents = telemetryService.getQueuedEvents();
    expect(queuedEvents).toHaveLength(1);

    const event = queuedEvents[0];
    expect(event).toBeDefined();
    if (event) {
      expect(event.eventId).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
      expect(event.timestamp).toBeDefined();
      expect(event.sessionId).toBeDefined();
      expect(event.schemaVersion).toBe("1.0.0");
      expect(event.requestId).toBeDefined();
      expect(event.event_type).toBe("stock_threshold_triggered");
      expect(event.properties.skuId).toBe("SKU-999");
    }
  });

  it("should flush batch when queue reaches threshold of 20 events", async () => {
    for (let i = 0; i < 20; i++) {
      track("inbound_order_created", {
        inboundOrderId: `INB-${i}`,
        clientId: "client-1",
        warehouseCode: "LA-01",
        totalSkus: 1,
        totalUnits: 5,
        sourceChannel: "PORTAL",
      });
    }

    // Flushes immediately upon reaching 20 events
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(telemetryService.getQueueSize()).toBe(0);
  });

  it("should flush batch after 10-second timer elapses", async () => {
    track("inbound_order_created", {
      inboundOrderId: "INB-SINGLE",
      clientId: "client-1",
      warehouseCode: "LA-01",
      totalSkus: 1,
      totalUnits: 5,
      sourceChannel: "PORTAL",
    });

    expect(global.fetch).not.toHaveBeenCalled();

    // Advance timer by 10 seconds
    jest.advanceTimersByTime(10000);

    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(telemetryService.getQueueSize()).toBe(0);
  });

  it("should flush pending events via sendBeacon on visibilitychange to hidden", () => {
    track("direct_stock_edit_rejected", {
      attemptedByUserId: "usr-1",
      warehouseCode: "ZAZ-01",
      skuId: "SKU-404",
      attemptedDelta: 10,
      rejectionReason: "Direct edit not permitted",
    });

    expect(telemetryService.getQueueSize()).toBe(1);

    // Simulate tab hiding
    Object.defineProperty(document, "visibilityState", {
      value: "hidden",
      writable: true,
      configurable: true,
    });
    document.dispatchEvent(new Event("visibilitychange"));

    expect(sendBeaconMock).toHaveBeenCalledTimes(1);
    expect(telemetryService.getQueueSize()).toBe(0);
  });

  it("should retry with exponential backoff on failure and discard after 3 retries", async () => {
    (global.fetch as jest.Mock).mockRejectedValue(new Error("Network connection dropped"));

    track("stock_validation_failed", {
      orderId: "ORD-1",
      warehouseCode: "LA-01",
      skuId: "SKU-1",
      expectedQuantity: 5,
      actualQuantity: 4,
      failureReason: "Missing item",
    });

    // Trigger flush
    await jest.advanceTimersByTimeAsync(10000);
    expect(global.fetch).toHaveBeenCalledTimes(1);

    // Attempt 1 retry (1000ms)
    await jest.advanceTimersByTimeAsync(1000);
    expect(global.fetch).toHaveBeenCalledTimes(2);

    // Attempt 2 retry (2000ms)
    await jest.advanceTimersByTimeAsync(2000);
    expect(global.fetch).toHaveBeenCalledTimes(3);

    // Attempt 3 retry (4000ms)
    await jest.advanceTimersByTimeAsync(4000);
    expect(global.fetch).toHaveBeenCalledTimes(4);

    // Advance more time - no more retries
    await jest.advanceTimersByTimeAsync(10000);
    expect(global.fetch).toHaveBeenCalledTimes(4);
  });
});
