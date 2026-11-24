'use client';

/**
 * React hook managing the real-time RFP Server-Sent Events (SSE) notification lifecycle,
 * exponential backoff reconnection, hybrid missed-ticket recovery (`Last-Event-ID` + REST
 * reconciliation), and strict `ticket_id` deduplication.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  IntakeTicketListResponseDTO,
  IntakeTicketSummaryDTO,
  RFPTicketCreatedEventDTO,
  SSEConnectionStatus,
} from '@repo/shared-types';
import { getToken } from '../lib/auth';
import {
  SSEAuthError,
  calculateReconnectBackoffMs,
  connectRFPNotificationStream,
  mapRFPEventToTicketSummary,
  mergeAndDeduplicateTickets,
} from '../lib/rfpNotificationsClient';

/**
 * Configuration parameters for the `useRFPNotifications` hook.
 */
export interface UseRFPNotificationsOptions {
  /** Optional API base URL override (defaults to `NEXT_PUBLIC_API_URL` or `http://localhost:8000`). */
  apiUrl?: string;
  /** Optional status filter (`"all"`, `"analizando"`, `"analisis_completo"`, `"descartado"`). */
  statusFilter?: string;
  /**
   * Optional maximum tickets to retrieve during REST fallback reconciliation (defaults to 100).
   * For network drops exceeding this threshold, client-side deduplication guarantees idempotency,
   * while table pagination or page refresh covers deep historical backlog.
   */
  reconciliationLimit?: number;
  /** Callback invoked whenever live or recovered tickets should be merged into dashboard state. */
  onTicketsReceived?: (incomingTickets: IntakeTicketSummaryDTO[]) => void;
}

/**
 * State and actions returned by `useRFPNotifications`.
 */
export interface UseRFPNotificationsResult {
  /** Current SSE stream connection status. */
  connectionStatus: SSEConnectionStatus;
  /** Most recent `rfp_ticket_created` event received in real time (for toast/banner display). */
  latestArrival: RFPTicketCreatedEventDTO | null;
  /** Set of `ticket_id` values that arrived via real-time SSE during this session. */
  realtimeTicketIds: ReadonlySet<string>;
  /** Current reconnection attempt counter (`0` when connected). */
  reconnectAttempt: number;
  /** Last monotonic SSE `id:` received from the server. */
  lastEventId: string | null;
  /** Dismiss the active real-time arrival toast/banner notification. */
  dismissLatestArrival: () => void;
  /** Manually trigger an immediate reconnection and missed-ticket recovery check. */
  retryConnection: () => void;
}

/**
 * Subscribe to real-time RFP ticket notifications over SSE with progressive backoff and hybrid recovery.
 *
 * @param options - Configuration callbacks for merging incoming and reconciled tickets.
 * @returns Live connection status, latest real-time arrival payload, highlight IDs, and control actions.
 */
export function useRFPNotifications(
  options: UseRFPNotificationsOptions = {}
): UseRFPNotificationsResult {
  const apiUrl =
    options.apiUrl || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const onTicketsReceivedRef = useRef(options.onTicketsReceived);
  onTicketsReceivedRef.current = options.onTicketsReceived;

  const [connectionStatus, setConnectionStatus] =
    useState<SSEConnectionStatus>('connecting');
  const [latestArrival, setLatestArrival] =
    useState<RFPTicketCreatedEventDTO | null>(null);
  const [realtimeTicketIds, setRealtimeTicketIds] = useState<ReadonlySet<string>>(
    () => new Set<string>()
  );
  const [reconnectAttempt, setReconnectAttempt] = useState<number>(0);
  const [lastEventId, setLastEventId] = useState<string | null>(null);
  const [manualRetryNonce, setManualRetryNonce] = useState<number>(0);

  const lastEventIdRef = useRef<string | null>(null);
  const seenTicketIdsRef = useRef<Set<string>>(new Set<string>());
  const hasConnectedOnceRef = useRef<boolean>(false);

  const reconciliationLimit = options.reconciliationLimit ?? 100;

  const dismissLatestArrival = useCallback((): void => {
    setLatestArrival(null);
  }, []);

  const reconcileMissedTickets = useCallback(
    async (token: string): Promise<void> => {
      try {
        const response = await fetch(
          `${apiUrl.replace(/\/$/, '')}/api/v1/rfp/tickets?limit=${reconciliationLimit}`,
          {
            method: 'GET',
            headers: {
              Authorization: `Bearer ${token}`,
            },
            cache: 'no-store',
          }
        );
        if (!response.ok) {
          return;
        }
        const data = (await response.json()) as IntakeTicketListResponseDTO;
        if (Array.isArray(data.items) && data.items.length > 0) {
          const deduplicated = mergeAndDeduplicateTickets([], data.items);
          for (const item of deduplicated) {
            seenTicketIdsRef.current.add(item.ticket_id);
          }
          onTicketsReceivedRef.current?.(deduplicated);
        }
      } catch {
        // Reconciliation failure is non-fatal; subsequent SSE frames or reconnect will retry
      }
    },
    [apiUrl, reconciliationLimit]
  );

  const retryConnection = useCallback((): void => {
    setReconnectAttempt(0);
    setConnectionStatus('connecting');
    setManualRetryNonce((prev) => prev + 1);
  }, []);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setConnectionStatus('unauthorized');
      return;
    }

    let isMounted = true;
    let abortController: AbortController | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let currentAttempt = 0;

    const clearTimer = (): void => {
      if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };

    const startStream = async (): Promise<void> => {
      if (!isMounted) {
        return;
      }

      const activeToken = getToken();
      if (!activeToken) {
        setConnectionStatus('unauthorized');
        return;
      }

      const isReconnecting = currentAttempt > 0 || hasConnectedOnceRef.current;
      setConnectionStatus(isReconnecting ? 'reconnecting' : 'connecting');

      abortController = new AbortController();

      try {
        await connectRFPNotificationStream({
          apiUrl,
          token: activeToken,
          lastEventId: lastEventIdRef.current,
          signal: abortController.signal,
          onOpen: () => {
            if (!isMounted) {
              return;
            }
            const wasReconnect = hasConnectedOnceRef.current || currentAttempt > 0;
            hasConnectedOnceRef.current = true;
            currentAttempt = 0;
            setReconnectAttempt(0);
            setConnectionStatus('connected');

            if (wasReconnect) {
              void reconcileMissedTickets(activeToken);
            }
          },
          onTicketCreated: (event: RFPTicketCreatedEventDTO, eventId: string | null) => {
            if (!isMounted) {
              return;
            }
            if (eventId) {
              lastEventIdRef.current = eventId;
              setLastEventId(eventId);
            }

            const summary = mapRFPEventToTicketSummary(event);
            const isFirstTimeSeen = !seenTicketIdsRef.current.has(event.ticket_id);
            seenTicketIdsRef.current.add(event.ticket_id);

            setRealtimeTicketIds((prev) => {
              if (prev.has(event.ticket_id)) {
                return prev;
              }
              const next = new Set(prev);
              next.add(event.ticket_id);
              return next;
            });

            if (isFirstTimeSeen) {
              setLatestArrival(event);
            }
            onTicketsReceivedRef.current?.([summary]);
          },
        });

        // If stream closed cleanly by server without abort, schedule progressive backoff reconnect
        if (isMounted && !abortController.signal.aborted) {
          const delayMs = calculateReconnectBackoffMs(currentAttempt);
          currentAttempt += 1;
          setReconnectAttempt(currentAttempt);
          setConnectionStatus('reconnecting');
          clearTimer();
          reconnectTimer = setTimeout(() => {
            void startStream();
          }, delayMs);
        }
      } catch (err: unknown) {
        if (!isMounted || abortController?.signal.aborted) {
          return;
        }

        if (err instanceof SSEAuthError) {
          setConnectionStatus('unauthorized');
          setReconnectAttempt(0);
          return;
        }

        const delayMs = calculateReconnectBackoffMs(currentAttempt);
        currentAttempt += 1;
        setReconnectAttempt(currentAttempt);
        setConnectionStatus('reconnecting');
        clearTimer();
        reconnectTimer = setTimeout(() => {
          void startStream();
        }, delayMs);
      }
    };

    void startStream();

    return () => {
      isMounted = false;
      clearTimer();
      if (abortController) {
        abortController.abort();
      }
      setConnectionStatus('disconnected');
    };
  }, [apiUrl, manualRetryNonce, reconcileMissedTickets]);

  return {
    connectionStatus,
    latestArrival,
    realtimeTicketIds,
    reconnectAttempt,
    lastEventId,
    dismissLatestArrival,
    retryConnection,
  };
}
