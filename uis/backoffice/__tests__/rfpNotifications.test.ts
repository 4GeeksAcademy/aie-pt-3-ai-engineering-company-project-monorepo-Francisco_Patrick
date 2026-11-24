/**
 * Automated unit and integration tests for Real-Time RFP Ticket Notifications (SSE Part 1).
 *
 * Covers:
 * - User Story 1 (T009): W3C SSE line-buffered frame parsing (`id:`, `event: rfp_ticket_created`,
 *   flat `data:` JSON validation, rejection of nested `{"event","data"}` wrappers) and real-time
 *   ticket prepend mapping (`mapRFPEventToTicketSummary`).
 * - User Story 2 (T018): Authenticated `Authorization: Bearer <token>` header transmission with
 *   zero JWT exposure in URL query string, `: keep-alive` comment frame handling without false
 *   event triggers, and immediate `SSEAuthError` halt on HTTP 401/403.
 * - User Story 3 (T023): Exponential reconnection backoff schedule (`calculateReconnectBackoffMs`:
 *   `1s, 2s, 4s, 8s, 16s`, capped at `30s`), `Last-Event-ID` header propagation on reconnect,
 *   and deterministic `mergeAndDeduplicateTickets` by `ticket_id` across live, replayed, and
 *   REST-reconciled records.
 */

import { TextDecoder, TextEncoder } from 'util';
import type {
  IntakeTicketSummaryDTO,
  RFPTicketCreatedEventDTO,
} from '@repo/shared-types';
import {
  SSEAuthError,
  calculateReconnectBackoffMs,
  connectRFPNotificationStream,
  mapRFPEventToTicketSummary,
  mergeAndDeduplicateTickets,
  parseRFPTicketCreatedPayload,
  parseSSEChunk,
} from '../lib/rfpNotificationsClient';

if (typeof globalThis.TextEncoder === 'undefined') {
  Object.assign(globalThis, { TextEncoder, TextDecoder });
}

/**
 * Helper to create a mock ReadableStream yielding encoded UTF-8 chunks sequentially.
 */
function createMockReadableStream(chunks: readonly string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let index = 0;

  return {
    getReader() {
      return {
        async read(): Promise<{ value: Uint8Array | undefined; done: boolean }> {
          if (index >= chunks.length) {
            return { value: undefined, done: true };
          }
          const chunk = chunks[index];
          index += 1;
          return {
            value: encoder.encode(chunk ?? ''),
            done: false,
          };
        },
        releaseLock(): void {
          // no-op
        },
      };
    },
  } as unknown as ReadableStream<Uint8Array>;
}

describe('Real-Time RFP SSE Notifications Client (US1, US2, US3)', () => {
  // =========================================================================
  // User Story 1: W3C SSE Frame Parsing & Real-Time Ticket Mapping (T009)
  // =========================================================================
  describe('US1: W3C SSE wire parsing and flat rfp_ticket_created payload mapping', () => {
    it('parses complete W3C SSE named event frames and preserves trailing incomplete chunks', () => {
      const rawChunk1 =
        'id: 1\nevent: rfp_ticket_created\ndata: {"ticket_id":"tkt_0225","rfp_id":"rfp_0071","client_name":"Northline Apparel","client_country":"US","services_requested":["warehouse","lastmile"],"status":"analyzing","created_at":"2026-07-24T14:32:00Z"}\n\nid: 2\nevent: rfp_ticket_cre';

      const firstPass = parseSSEChunk(rawChunk1);
      expect(firstPass.frames).toHaveLength(1);
      expect(firstPass.frames[0]).toEqual({
        type: 'event',
        id: '1',
        event: 'rfp_ticket_created',
        data: '{"ticket_id":"tkt_0225","rfp_id":"rfp_0071","client_name":"Northline Apparel","client_country":"US","services_requested":["warehouse","lastmile"],"status":"analyzing","created_at":"2026-07-24T14:32:00Z"}',
      });
      expect(firstPass.remainder).toBe('id: 2\nevent: rfp_ticket_cre');

      const rawChunk2 =
        firstPass.remainder +
        'ated\ndata: {"ticket_id":"tkt_0226","rfp_id":"rfp_0072","client_name":"Iberia Fashion","client_country":"ES","services_requested":["reverse"],"status":"analyzing","created_at":"2026-07-24T14:35:00Z"}\n\n';

      const secondPass = parseSSEChunk(rawChunk2);
      expect(secondPass.frames).toHaveLength(1);
      expect(secondPass.frames[0]?.id).toBe('2');
      expect(secondPass.frames[0]?.event).toBe('rfp_ticket_created');
      expect(secondPass.remainder).toBe('');
    });

    it('validates flat rfp_ticket_created JSON payloads and rejects nested {"event","data"} wrappers', () => {
      const validFlatJson = JSON.stringify({
        ticket_id: 'tkt_0225',
        rfp_id: 'rfp_0071',
        client_name: 'Northline Apparel',
        client_country: 'US',
        services_requested: ['warehouse', 'lastmile'],
        status: 'analyzing',
        created_at: '2026-07-24T14:32:00Z',
      });

      const parsed = parseRFPTicketCreatedPayload(validFlatJson);
      expect(parsed).toEqual({
        ticket_id: 'tkt_0225',
        rfp_id: 'rfp_0071',
        client_name: 'Northline Apparel',
        client_country: 'US',
        services_requested: ['warehouse', 'lastmile'],
        status: 'analyzing',
        created_at: '2026-07-24T14:32:00Z',
      });

      // Nested wrapper forbidden by briefing §3 / FR-003
      const forbiddenNestedWrapper = JSON.stringify({
        event: 'rfp_ticket_created',
        data: {
          ticket_id: 'tkt_0225',
          rfp_id: 'rfp_0071',
          client_name: 'Northline Apparel',
          client_country: 'US',
          services_requested: ['warehouse'],
          status: 'analyzing',
          created_at: '2026-07-24T14:32:00Z',
        },
      });
      expect(parseRFPTicketCreatedPayload(forbiddenNestedWrapper)).toBeNull();
    });

    it('maps RFPTicketCreatedEventDTO to an enriched IntakeTicketSummaryDTO with isNewRealtimeArrival=true', () => {
      const event: RFPTicketCreatedEventDTO = {
        ticket_id: 'tkt_0225',
        rfp_id: 'rfp_0071',
        client_name: 'Northline Apparel',
        client_country: 'US',
        services_requested: ['warehouse', 'lastmile'],
        status: 'analyzing',
        created_at: '2026-07-24T14:32:00Z',
      };

      const summary = mapRFPEventToTicketSummary(event);
      expect(summary.ticket_id).toBe('tkt_0225');
      expect(summary.rfp_id).toBe('rfp_0071');
      expect(summary.ticket_number).toBe('rfp_0071');
      expect(summary.client_name).toBe('Northline Apparel');
      expect(summary.client_country).toBe('US');
      expect(summary.services_requested).toEqual(['warehouse', 'lastmile']);
      expect(summary.status).toBe('analizando');
      expect(summary.isNewRealtimeArrival).toBe(true);
    });
  });

  // =========================================================================
  // User Story 2: Authenticated Stream Access & Keep-Alive Heartbeats (T018)
  // =========================================================================
  describe('US2: Bearer JWT header transmission, keep-alive comments, and 401/403 halt', () => {
    it('sends Authorization: Bearer <token> in headers (never in URL) and handles : keep-alive comments without false ticket triggers', async () => {
      const receivedEvents: RFPTicketCreatedEventDTO[] = [];
      let keepAliveCount = 0;
      let capturedUrl = '';
      let capturedHeaders: Record<string, string> = {};

      const mockFetch = jest.fn(
        async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
          capturedUrl = String(input);
          capturedHeaders = (init?.headers ?? {}) as Record<string, string>;

          const stream = createMockReadableStream([
            ': keep-alive\n\n',
            'id: 7\nevent: rfp_ticket_created\ndata: {"ticket_id":"tkt_0225","rfp_id":"rfp_0071","client_name":"Northline Apparel","client_country":"US","services_requested":["warehouse","lastmile"],"status":"analyzing","created_at":"2026-07-24T14:32:00Z"}\n\n',
            ': keep-alive\n\n',
          ]);

          return {
            ok: true,
            status: 200,
            headers: {
              get: (name: string) =>
                name.toLowerCase() === 'content-type'
                  ? 'text/event-stream; charset=utf-8'
                  : null,
            },
            body: stream,
          } as unknown as Response;
        }
      );

      await connectRFPNotificationStream({
        apiUrl: 'http://localhost:8000',
        token: 'secret-jwt-token-123',
        fetchImpl: mockFetch as unknown as typeof fetch,
        onKeepAlive: () => {
          keepAliveCount += 1;
        },
        onTicketCreated: (ev) => {
          receivedEvents.push(ev);
        },
      });

      expect(capturedUrl).toBe('http://localhost:8000/api/v1/rfp/notifications/stream');
      expect(capturedUrl).not.toContain('secret-jwt-token-123');
      expect(capturedHeaders['Authorization']).toBe('Bearer secret-jwt-token-123');
      expect(keepAliveCount).toBe(2);
      expect(receivedEvents).toHaveLength(1);
      expect(receivedEvents[0]?.ticket_id).toBe('tkt_0225');
    });

    it('throws SSEAuthError immediately when the server returns HTTP 401 or 403', async () => {
      const mockFetch401 = jest.fn(async (): Promise<Response> => {
        return {
          ok: false,
          status: 401,
          headers: { get: () => 'application/json' },
        } as unknown as Response;
      });

      await expect(
        connectRFPNotificationStream({
          apiUrl: 'http://localhost:8000',
          token: 'expired-token',
          fetchImpl: mockFetch401 as unknown as typeof fetch,
          onTicketCreated: jest.fn(),
        })
      ).rejects.toThrow(SSEAuthError);
    });
  });

  // =========================================================================
  // User Story 3: Exponential Backoff, Last-Event-ID & Deduplication (T023)
  // =========================================================================
  describe('US3: Progressive backoff schedule, Last-Event-ID propagation, and ticket_id deduplication', () => {
    it('computes exponential backoff delays of 1s, 2s, 4s, 8s, 16s and caps at 30s', () => {
      expect(calculateReconnectBackoffMs(0)).toBe(1000);
      expect(calculateReconnectBackoffMs(1)).toBe(2000);
      expect(calculateReconnectBackoffMs(2)).toBe(4000);
      expect(calculateReconnectBackoffMs(3)).toBe(8000);
      expect(calculateReconnectBackoffMs(4)).toBe(16000);
      expect(calculateReconnectBackoffMs(5)).toBe(30000);
      expect(calculateReconnectBackoffMs(10)).toBe(30000);
    });

    it('propagates Last-Event-ID header when reconnecting to recover missed ring-buffer events', async () => {
      let capturedHeaders: Record<string, string> = {};

      const mockFetch = jest.fn(
        async (_input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
          capturedHeaders = (init?.headers ?? {}) as Record<string, string>;
          return {
            ok: true,
            status: 200,
            headers: {
              get: (name: string) =>
                name.toLowerCase() === 'content-type' ? 'text/event-stream' : null,
            },
            body: createMockReadableStream([]),
          } as unknown as Response;
        }
      );

      await connectRFPNotificationStream({
        apiUrl: 'http://localhost:8000',
        token: 'valid-token',
        lastEventId: '42',
        fetchImpl: mockFetch as unknown as typeof fetch,
        onTicketCreated: jest.fn(),
      });

      expect(capturedHeaders['Last-Event-ID']).toBe('42');
    });

    it('deduplicates tickets by ticket_id across initial load, live SSE events, and REST reconciliation', () => {
      const existingList: IntakeTicketSummaryDTO[] = [
        {
          ticket_id: 'tkt_0224',
          ticket_number: 'rfp_0070',
          rfp_id: 'rfp_0070',
          status: 'analisis_completo',
          raw_pdf_filename: 'rfp_0070.pdf',
          client_name: 'Legacy Corp',
          client_country: 'ES',
          services_requested: ['warehouse'],
          rejection_reason: null,
          created_at: '2026-07-24T12:00:00Z',
          updated_at: '2026-07-24T12:05:00Z',
        },
      ];

      // Ticket tkt_0225 arrives via live SSE
      const liveArrival = mapRFPEventToTicketSummary({
        ticket_id: 'tkt_0225',
        rfp_id: 'rfp_0071',
        client_name: 'Northline Apparel',
        client_country: 'US',
        services_requested: ['warehouse', 'lastmile'],
        status: 'analyzing',
        created_at: '2026-07-24T14:32:00Z',
      });

      const afterLive = mergeAndDeduplicateTickets(existingList, [liveArrival]);
      expect(afterLive).toHaveLength(2);
      expect(afterLive[0]?.ticket_id).toBe('tkt_0225');
      expect(afterLive[0]?.isNewRealtimeArrival).toBe(true);

      // Reconnection reconciliation returns both tkt_0225 (duplicate) and missed tkt_0226
      const reconciledFromRest: IntakeTicketSummaryDTO[] = [
        {
          ticket_id: 'tkt_0226',
          ticket_number: 'rfp_0072',
          rfp_id: 'rfp_0072',
          status: 'analizando',
          raw_pdf_filename: 'rfp_0072.pdf',
          client_name: 'Atlántico Distribución',
          client_country: 'ES',
          services_requested: ['lastmile', 'reverse'],
          rejection_reason: null,
          created_at: '2026-07-24T14:40:00Z',
          updated_at: '2026-07-24T14:40:00Z',
        },
        {
          ticket_id: 'tkt_0225',
          ticket_number: 'rfp_0071',
          rfp_id: 'rfp_0071',
          status: 'analizando',
          raw_pdf_filename: 'rfp_0071.pdf',
          client_name: 'Northline Apparel',
          client_country: 'US',
          services_requested: ['warehouse', 'lastmile'],
          rejection_reason: null,
          created_at: '2026-07-24T14:32:00Z',
          updated_at: '2026-07-24T14:32:00Z',
        },
      ];

      const afterReconcile = mergeAndDeduplicateTickets(afterLive, reconciledFromRest);
      expect(afterReconcile).toHaveLength(3);
      expect(afterReconcile.map((t) => t.ticket_id)).toEqual([
        'tkt_0226',
        'tkt_0225',
        'tkt_0224',
      ]);

      // Preserves the realtime highlight badge on tkt_0225 even after REST merge
      const mergedTkt0225 = afterReconcile.find((t) => t.ticket_id === 'tkt_0225');
      expect(mergedTkt0225?.isNewRealtimeArrival).toBe(true);
    });
  });
});
