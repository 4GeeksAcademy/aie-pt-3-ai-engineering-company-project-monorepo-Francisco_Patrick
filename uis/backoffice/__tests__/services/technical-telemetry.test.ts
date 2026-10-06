import { track, telemetryService } from "../../app/services/telemetry";

describe("Technical Telemetry Instrumentation", () => {
  beforeEach(() => {
    telemetryService.resetForTesting();
  });

  it("should capture uncaught frontend errors conforming to schema", () => {
    track("frontend_error_captured", {
      errorName: "TypeError",
      errorMessage: "Cannot read property 'undefined' of null",
      stackTraceSnippet: "TypeError at Component.render (index.tsx:42)",
      url: "/inventory",
      componentName: "InventoryTable",
    });

    const events = telemetryService.getQueuedEvents();
    expect(events).toHaveLength(1);
    const event = events[0];
    expect(event).toBeDefined();
    if (event) {
      expect(event.event_type).toBe("frontend_error_captured");
      expect(event.properties.errorName).toBe("TypeError");
      expect(event.properties.componentName).toBe("InventoryTable");
    }
  });

  it("should capture API latency measurements", () => {
    track("api_latency_recorded", {
      endpointPath: "/api/v1/inventory",
      httpMethod: "GET",
      durationMs: 42.5,
      httpStatusCode: 200,
      success: true,
    });

    const events = telemetryService.getQueuedEvents();
    expect(events).toHaveLength(1);
    const event = events[0];
    expect(event).toBeDefined();
    if (event) {
      expect(event.event_type).toBe("api_latency_recorded");
      expect(event.properties.durationMs).toBe(42.5);
      expect(event.properties.httpStatusCode).toBe(200);
      expect(event.properties.success).toBe(true);
    }
  });

  it("should capture section navigation transitions", () => {
    track("section_navigation_tracked", {
      sourceSection: "/inventory",
      destinationSection: "/incidents",
      navigationDurationMs: 120,
    });

    const events = telemetryService.getQueuedEvents();
    expect(events).toHaveLength(1);
    const event = events[0];
    expect(event).toBeDefined();
    if (event) {
      expect(event.event_type).toBe("section_navigation_tracked");
      expect(event.properties.sourceSection).toBe("/inventory");
      expect(event.properties.destinationSection).toBe("/incidents");
    }
  });
});
