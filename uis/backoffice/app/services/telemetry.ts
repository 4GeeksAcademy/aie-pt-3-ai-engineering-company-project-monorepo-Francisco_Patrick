/**
 * TelemetryService for TrackFlow Backoffice.
 * Buffers telemetry events in memory, dispatches in 10s / 20-event batches,
 * flushes reliably on tab exit via sendBeacon, and implements exponential backoff retries.
 */

import type {
  TelemetryEvent,
  TelemetryBatch,
} from "./telemetry-types";
import {
  SCHEMA_VERSION,
  DEFAULT_BATCH_INTERVAL_MS,
  DEFAULT_BATCH_MAX_SIZE,
  MAX_QUEUE_CAPACITY,
  MAX_RETRY_ATTEMPTS,
} from "./telemetry-types";

class TelemetryServiceImpl {
  private queue: TelemetryEvent[] = [];
  private flushTimer: ReturnType<typeof setTimeout> | null = null;
  private endpointUrl: string;
  private sessionId: string;
  private userId: string | null = null;
  private isProcessing: boolean = false;
  private listenersAttached: boolean = false;

  public constructor() {
    this.endpointUrl =
      (typeof process !== "undefined" &&
        process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT) ||
      "http://localhost:8000/telemetry/events";

    this.sessionId = this.initializeSessionId();
    this.attachLifecycleListeners();
  }

  /**
   * Initializes or restores session identifier from session storage.
   * @returns Stable session UUID string.
   */
  private initializeSessionId(): string {
    if (typeof window !== "undefined" && window.sessionStorage) {
      try {
        const stored = window.sessionStorage.getItem("tf_telemetry_session_id");
        if (stored) {
          return stored;
        }
        const created = this.generateUuid();
        window.sessionStorage.setItem("tf_telemetry_session_id", created);
        return created;
      } catch {
        // Fallback for restricted storage environments
        return this.generateUuid();
      }
    }
    return this.generateUuid();
  }

  /**
   * Generates standard UUIDv4 identifier.
   * @returns Formatted UUIDv4 string.
   */
  private generateUuid(): string {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (char) => {
      const rand = (Math.random() * 16) | 0;
      const value = char === "x" ? rand : (rand & 0x3) | 0x8;
      return value.toString(16);
    });
  }

  /**
   * Sets the authenticated user ID for subsequent event metadata.
   * @param id Authenticated user ID or null on logout.
   */
  public setUserId(id: string | null): void {
    this.userId = id;
  }

  /**
   * Captures and queues a telemetry event with automatic metadata enrichment.
   * @param eventType Normalized entity_action taxonomy string.
   * @param properties Domain-specific key-value payload.
   */
  public track(eventType: string, properties: Record<string, unknown>): void {
    const enrichedEvent: TelemetryEvent = {
      eventId: this.generateUuid(),
      timestamp: new Date().toISOString(),
      sessionId: this.sessionId,
      userId: this.userId,
      event_type: eventType,
      schemaVersion: SCHEMA_VERSION,
      requestId: this.generateUuid(),
      properties: { ...properties },
    };

    if (this.queue.length >= MAX_QUEUE_CAPACITY) {
      // Discard oldest event to prevent unbounded memory growth
      this.queue.shift();
    }

    this.queue.push(enrichedEvent);

    if (this.queue.length >= DEFAULT_BATCH_MAX_SIZE) {
      this.flushBatch();
    } else {
      this.scheduleTimer();
    }
  }

  /**
   * Schedules or maintains the 10-second debounce timer.
   */
  private scheduleTimer(): void {
    if (this.flushTimer !== null) {
      return;
    }
    this.flushTimer = setTimeout(() => {
      this.flushTimer = null;
      this.flushBatch();
    }, DEFAULT_BATCH_INTERVAL_MS);
  }

  /**
   * Clears active flush timer.
   */
  private clearTimer(): void {
    if (this.flushTimer !== null) {
      clearTimeout(this.flushTimer);
      this.flushTimer = null;
    }
  }

  /**
   * Dispatches the current memory queue in a batch via HTTP POST.
   * @param retryCount Current retry attempt index.
   */
  public flushBatch(retryCount: number = 0): void {
    this.clearTimer();

    if (this.queue.length === 0) {
      return;
    }

    const batchToSend = [...this.queue];
    this.queue = [];

    const payload: TelemetryBatch = {
      events: batchToSend,
    };

    this.sendWithRetry(payload, retryCount);
  }

  /**
   * Transmits payload with exponential backoff on failure.
   * @param payload Batch payload to send.
   * @param retryCount Current attempt count.
   */
  private sendWithRetry(payload: TelemetryBatch, retryCount: number): void {
    if (typeof fetch === "undefined") {
      return;
    }

    fetch(this.endpointUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Telemetry ingestion returned status ${response.status}`);
        }
      })
      .catch((_error: unknown) => {
        if (retryCount < MAX_RETRY_ATTEMPTS) {
          const delayMs = Math.pow(2, retryCount) * 1000;
          setTimeout(() => {
            this.sendWithRetry(payload, retryCount + 1);
          }, delayMs);
        }
        // If max retries exceeded, batch is dropped safely without raising exceptions
      });
  }

  /**
   * Flushes queue synchronously during page lifecycle exits.
   */
  public flushSync(): void {
    this.clearTimer();

    if (this.queue.length === 0) {
      return;
    }

    const batchToSend = [...this.queue];
    this.queue = [];

    const payload: TelemetryBatch = {
      events: batchToSend,
    };
    const serialized = JSON.stringify(payload);

    let beaconSent = false;
    if (
      typeof navigator !== "undefined" &&
      typeof navigator.sendBeacon === "function"
    ) {
      try {
        const blob = new Blob([serialized], { type: "application/json" });
        beaconSent = navigator.sendBeacon(this.endpointUrl, blob);
      } catch {
        beaconSent = false;
      }
    }

    if (!beaconSent && typeof fetch !== "undefined") {
      try {
        fetch(this.endpointUrl, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: serialized,
          keepalive: true,
        }).catch(() => {
          // Ignore exit flush failures
        });
      } catch {
        // Fallback catch
      }
    }
  }

  /**
   * Attaches browser visibility and unload listeners for reliable delivery.
   */
  private attachLifecycleListeners(): void {
    if (this.listenersAttached || typeof document === "undefined") {
      return;
    }

    const onVisibilityChange = (): void => {
      if (document.visibilityState === "hidden") {
        this.flushSync();
      }
    };

    document.addEventListener("visibilitychange", onVisibilityChange);

    if (typeof window !== "undefined") {
      window.addEventListener("pagehide", () => this.flushSync());
      window.addEventListener("beforeunload", () => this.flushSync());
    }

    this.listenersAttached = true;
  }

  /**
   * Retrieves current in-memory queue size (for diagnostics/testing).
   * @returns Number of pending events in buffer.
   */
  public getQueueSize(): number {
    return this.queue.length;
  }

  /**
   * Retrieves copy of queued events (for diagnostics/testing).
   * @returns Array of pending events.
   */
  public getQueuedEvents(): TelemetryEvent[] {
    return [...this.queue];
  }

  /**
   * Resets internal state for clean unit tests.
   */
  public resetForTesting(): void {
    this.clearTimer();
    this.queue = [];
    this.userId = null;
    this.isProcessing = false;
  }
}

export const telemetryService = new TelemetryServiceImpl();

/**
 * Public global tracking function.
 * All backoffice telemetry MUST pass through this function.
 * @param eventType Normalized entity_action taxonomy name.
 * @param properties Domain properties payload adhering to event allowlist.
 */
export function track(
  eventType: string,
  properties: Record<string, unknown>
): void {
  telemetryService.track(eventType, properties);
}
