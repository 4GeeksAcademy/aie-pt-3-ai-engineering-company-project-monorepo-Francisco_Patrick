/**
 * Authenticated Server-Sent Events (SSE) client, W3C frame parser, exponential backoff calculator,
 * and ticket deduplication utilities for Real-Time RFP Ticket Notifications (Part 1).
 */

import type {
  ClientCountry,
  DepartmentId,
  IntakeTicketSummaryDTO,
  RFPTicketCreatedEventDTO,
} from '@repo/shared-types';

/**
 * Custom error thrown when the SSE stream rejects credentials with HTTP 401 or 403.
 * Used to halt automatic reconnection attempts immediately (FR-010, SC-002).
 */
export class SSEAuthError extends Error {
  /** HTTP status code returned by the server (401 or 403). */
  public readonly statusCode: number;

  /**
   * Create an SSEAuthError instance.
   *
   * @param statusCode - HTTP response status code (401 or 403).
   * @param message - Human-readable authentication rejection description.
   */
  public constructor(statusCode: number, message: string) {
    super(message);
    this.name = 'SSEAuthError';
    this.statusCode = statusCode;
  }
}

/**
 * Parsed W3C Server-Sent Events frame representation.
 */
export interface ParsedSSEFrame {
  /** Frame classification: named/unnamed data event or comment heartbeat. */
  type: 'event' | 'comment';
  /** Optional monotonic SSE event ID (`id:` line). */
  id: string | null;
  /** Event type name (`event:` line; defaults to `"message"` per W3C spec). */
  event: string;
  /** Raw concatenated `data:` payload string, or comment text for comment frames. */
  data: string;
}

/**
 * Result of parsing an incoming stream text buffer into complete SSE frames and remaining partial line tail.
 */
export interface SSEChunkParseResult {
  /** Complete SSE frames extracted from double-newline delimited blocks. */
  frames: ParsedSSEFrame[];
  /** Incomplete trailing text buffer to prepend to the next stream chunk. */
  remainder: string;
}

/**
 * Options for connecting to the authenticated RFP SSE notification stream.
 */
export interface ConnectRFPStreamOptions {
  /** Base API URL (e.g. `http://localhost:8000`). */
  apiUrl: string;
  /** Backoffice Bearer JWT token passed strictly in the `Authorization` header. */
  token: string;
  /** Optional last received monotonic SSE event ID for `Last-Event-ID` missed-event replay. */
  lastEventId?: string | null;
  /** AbortSignal used to cancel the stream on unmount or manual disconnect. */
  signal?: AbortSignal;
  /** Callback fired immediately when the HTTP 200 `text/event-stream` handshake succeeds. */
  onOpen?: () => void;
  /** Callback fired when a valid `rfp_ticket_created` event frame is received. */
  onTicketCreated: (event: RFPTicketCreatedEventDTO, eventId: string | null) => void;
  /** Optional callback fired when a `: keep-alive` heartbeat comment frame is received. */
  onKeepAlive?: () => void;
  /** Optional custom `fetch` implementation for deterministic unit testing. */
  fetchImpl?: typeof fetch;
}

const VALID_COUNTRIES: ReadonlySet<ClientCountry> = new Set<ClientCountry>(['US', 'ES']);
const VALID_DEPARTMENTS: ReadonlySet<DepartmentId> = new Set<DepartmentId>([
  'warehouse',
  'lastmile',
  'reverse',
]);

/**
 * Parse a buffered SSE stream text chunk into complete W3C SSE frames and any trailing incomplete block.
 *
 * Normalizes `\r\n` and `\r` line endings to `\n` and splits on `\n\n` frame boundaries.
 *
 * @param buffer - Accumulated raw UTF-8 text from the stream reader.
 * @returns Object containing parsed `frames` and the unconsumed `remainder` string.
 */
export function parseSSEChunk(buffer: string): SSEChunkParseResult {
  const normalized = buffer.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  const lastDoubleNewline = normalized.lastIndexOf('\n\n');

  if (lastDoubleNewline === -1) {
    return { frames: [], remainder: normalized };
  }

  const completePortion = normalized.slice(0, lastDoubleNewline);
  const remainder = normalized.slice(lastDoubleNewline + 2);
  const rawBlocks = completePortion.split('\n\n');
  const frames: ParsedSSEFrame[] = [];

  for (const block of rawBlocks) {
    const trimmedBlock = block.trim();
    if (!trimmedBlock) {
      continue;
    }

    const lines = block.split('\n');
    const isCommentOnly = lines.every((line) => line.trim().startsWith(':'));
    if (isCommentOnly) {
      frames.push({
        type: 'comment',
        id: null,
        event: 'comment',
        data: lines
          .map((line) => line.trim().replace(/^:\s?/, ''))
          .join('\n')
          .trim(),
      });
      continue;
    }

    let eventId: string | null = null;
    let eventName = 'message';
    const dataLines: string[] = [];

    for (const line of lines) {
      if (!line || line.startsWith(':')) {
        continue;
      }
      if (line.startsWith('id:')) {
        eventId = line.slice(3).trim();
      } else if (line.startsWith('event:')) {
        eventName = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim());
      }
    }

    frames.push({
      type: 'event',
      id: eventId,
      event: eventName,
      data: dataLines.join('\n'),
    });
  }

  return { frames, remainder };
}

/**
 * Validate and parse a flat JSON string from an `rfp_ticket_created` SSE `data:` line.
 *
 * Enforces the flat schema required by `docs/real-time-notification/trackflow-BRIEFING.es.md` §3
 * (`ticket_id`, `rfp_id`, `client_name`, `client_country`, `services_requested`, `status: "analyzing"`, `created_at`).
 *
 * @param rawJson - Raw JSON string from the SSE frame's `data:` field.
 * @returns Validated `RFPTicketCreatedEventDTO`, or `null` if the payload is malformed or wrapped.
 */
export function parseRFPTicketCreatedPayload(rawJson: string): RFPTicketCreatedEventDTO | null {
  try {
    const parsed: unknown = JSON.parse(rawJson);
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
      return null;
    }

    const record = parsed as Record<string, unknown>;

    // Reject nested {"event", "data"} envelopes per FR-003
    if ('event' in record && 'data' in record) {
      return null;
    }

    const ticketId = typeof record['ticket_id'] === 'string' ? record['ticket_id'].trim() : '';
    const rfpId = typeof record['rfp_id'] === 'string' ? record['rfp_id'].trim() : '';
    const clientName =
      typeof record['client_name'] === 'string' ? record['client_name'].trim() : '';
    const clientCountryRaw = record['client_country'];
    const statusRaw = record['status'];
    const createdAt =
      typeof record['created_at'] === 'string' ? record['created_at'].trim() : '';
    const servicesRaw = record['services_requested'];

    if (!ticketId || !rfpId || !clientName || !createdAt) {
      return null;
    }
    if (
      typeof clientCountryRaw !== 'string' ||
      !VALID_COUNTRIES.has(clientCountryRaw as ClientCountry)
    ) {
      return null;
    }
    if (statusRaw !== 'analyzing') {
      return null;
    }
    if (!Array.isArray(servicesRaw) || servicesRaw.length === 0) {
      return null;
    }

    const services: DepartmentId[] = [];
    for (const item of servicesRaw) {
      if (typeof item === 'string' && VALID_DEPARTMENTS.has(item as DepartmentId)) {
        services.push(item as DepartmentId);
      } else {
        return null;
      }
    }

    return {
      ticket_id: ticketId,
      rfp_id: rfpId,
      client_name: clientName,
      client_country: clientCountryRaw as ClientCountry,
      services_requested: services,
      status: 'analyzing',
      created_at: createdAt,
    };
  } catch {
    return null;
  }
}

/**
 * Convert a validated `RFPTicketCreatedEventDTO` SSE event into an `IntakeTicketSummaryDTO`
 * ready to be prepended to the backoffice RFP dashboard table.
 *
 * @param event - Validated `rfp_ticket_created` SSE event payload.
 * @returns Enriched `IntakeTicketSummaryDTO` marked with `isNewRealtimeArrival: true`.
 */
export function mapRFPEventToTicketSummary(
  event: RFPTicketCreatedEventDTO
): IntakeTicketSummaryDTO {
  return {
    ticket_id: event.ticket_id,
    ticket_number: event.rfp_id,
    status: 'analizando',
    raw_pdf_filename: `${event.rfp_id}.pdf`,
    client_name: event.client_name,
    rejection_reason: null,
    created_at: event.created_at,
    updated_at: event.created_at,
    rfp_id: event.rfp_id,
    client_country: event.client_country,
    services_requested: [...event.services_requested],
    isNewRealtimeArrival: true,
  };
}

/**
 * Calculate the progressive exponential backoff delay in milliseconds for reconnection attempts.
 *
 * Follows the exact schedule `1s, 2s, 4s, 8s, 16s`, capped at `30s` (30,000 ms) per FR-010.
 *
 * @param attempt - Zero-based reconnection attempt index (`0` -> 1000ms, `1` -> 2000ms, etc.).
 * @returns Backoff delay in milliseconds in the range `[1000, 30000]`.
 */
export function calculateReconnectBackoffMs(attempt: number): number {
  const safeAttempt = Math.max(0, Math.floor(attempt));
  const delay = 1000 * Math.pow(2, safeAttempt);
  return Math.min(delay, 30000);
}

/**
 * Merge and strictly deduplicate two lists of RFP ticket summaries by `ticket_id`.
 *
 * Preserves `isNewRealtimeArrival` highlights and enriched metadata fields (`rfp_id`,
 * `client_country`, `services_requested`) when the same `ticket_id` arrives via both
 * live SSE / `Last-Event-ID` replay and REST reconciliation (`GET /api/v1/rfp/tickets`).
 *
 * @param existingTickets - Current dashboard ticket summaries.
 * @param incomingTickets - Newly received or reconciled ticket summaries.
 * @returns Deduplicated array of `IntakeTicketSummaryDTO` ordered with newest arrivals first.
 */
export function mergeAndDeduplicateTickets(
  existingTickets: readonly IntakeTicketSummaryDTO[],
  incomingTickets: readonly IntakeTicketSummaryDTO[]
): IntakeTicketSummaryDTO[] {
  const ticketMap = new Map<string, IntakeTicketSummaryDTO>();

  for (const ticket of [...incomingTickets, ...existingTickets]) {
    const existing = ticketMap.get(ticket.ticket_id);
    if (!existing) {
      ticketMap.set(ticket.ticket_id, { ...ticket });
    } else {
      ticketMap.set(ticket.ticket_id, {
        ...existing,
        ...ticket,
        client_name: ticket.client_name ?? existing.client_name,
        rfp_id: ticket.rfp_id ?? existing.rfp_id ?? existing.ticket_number,
        client_country: ticket.client_country ?? existing.client_country ?? null,
        services_requested:
          ticket.services_requested && ticket.services_requested.length > 0
            ? ticket.services_requested
            : existing.services_requested ?? [],
        isNewRealtimeArrival: Boolean(
          existing.isNewRealtimeArrival || ticket.isNewRealtimeArrival
        ),
      });
    }
  }

  return Array.from(ticketMap.values()).sort((a, b) => {
    const timeA = Date.parse(a.created_at);
    const timeB = Date.parse(b.created_at);
    if (!Number.isNaN(timeA) && !Number.isNaN(timeB) && timeA !== timeB) {
      return timeB - timeA;
    }
    return 0;
  });
}

/**
 * Open and consume an authenticated Server-Sent Events stream from `GET /api/v1/rfp/notifications/stream`.
 *
 * Passes the Bearer JWT strictly via the `Authorization` header (never in the URL query string),
 * attaches `Last-Event-ID` when reconnecting, and streams frames through `parseSSEChunk`.
 *
 * @param options - Connection configuration and frame callbacks.
 * @returns Promise that resolves when the stream closes cleanly or rejects on network / auth error.
 * @throws {SSEAuthError} When the server responds with HTTP 401 or 403.
 */
export async function connectRFPNotificationStream(
  options: ConnectRFPStreamOptions
): Promise<void> {
  const fetchFn = options.fetchImpl ?? fetch;
  const endpointUrl = `${options.apiUrl.replace(/\/$/, '')}/api/v1/rfp/notifications/stream`;

  const headers: Record<string, string> = {
    Accept: 'text/event-stream',
    Authorization: `Bearer ${options.token}`,
    'Cache-Control': 'no-cache',
  };

  if (options.lastEventId) {
    headers['Last-Event-ID'] = options.lastEventId;
  }

  const requestInit: RequestInit = {
    method: 'GET',
    headers,
    cache: 'no-store',
  };
  if (options.signal) {
    requestInit.signal = options.signal;
  }

  const response = await fetchFn(endpointUrl, requestInit);

  if (response.status === 401 || response.status === 403) {
    throw new SSEAuthError(
      response.status,
      `Unauthorized SSE stream connection (HTTP ${response.status}).`
    );
  }

  if (!response.ok) {
    throw new Error(`SSE stream connection failed with HTTP ${response.status}.`);
  }

  const contentType = response.headers.get('content-type') ?? '';
  if (!contentType.includes('text/event-stream')) {
    throw new Error(`Invalid SSE Content-Type: "${contentType}". Expected "text/event-stream".`);
  }

  if (!response.body) {
    throw new Error('SSE response body is empty or ReadableStream is not supported.');
  }

  options.onOpen?.();

  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      if (value) {
        buffer += decoder.decode(value, { stream: true });
        const parsed = parseSSEChunk(buffer);
        buffer = parsed.remainder;

        for (const frame of parsed.frames) {
          if (frame.type === 'comment') {
            options.onKeepAlive?.();
            continue;
          }
          if (frame.type === 'event' && frame.event === 'rfp_ticket_created') {
            const payload = parseRFPTicketCreatedPayload(frame.data);
            if (payload) {
              options.onTicketCreated(payload, frame.id);
            }
          }
        }
      }
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // Reader lock may already be released on abort
    }
  }
}
