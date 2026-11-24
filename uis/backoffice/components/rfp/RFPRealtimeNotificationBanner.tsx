'use client';

/**
 * Real-time SSE connection status badge and newly arrived RFP ticket notification banner
 * for the commercial backoffice dashboard (Miguel Torres's team).
 */

import React from 'react';
import Link from 'next/link';
import type {
  RFPTicketCreatedEventDTO,
  SSEConnectionStatus,
} from '@repo/shared-types';
import { calculateReconnectBackoffMs } from '../../lib/rfpNotificationsClient';

/**
 * Props for `RFPRealtimeNotificationBanner`.
 */
export interface RFPRealtimeNotificationBannerProps {
  /** Current SSE stream connection lifecycle state. */
  connectionStatus: SSEConnectionStatus;
  /** Latest real-time `rfp_ticket_created` arrival payload, if any. */
  latestArrival: RFPTicketCreatedEventDTO | null;
  /** Current progressive backoff attempt count when reconnecting. */
  reconnectAttempt: number;
  /** Handler to dismiss the latest arrival toast banner. */
  onDismissArrival: () => void;
  /** Handler to manually retry the SSE connection. */
  onRetryConnection: () => void;
}

const SERVICE_LABELS: Readonly<Record<string, string>> = {
  warehouse: 'Almacén (Warehouse)',
  lastmile: 'Última Milla (Last Mile)',
  reverse: 'Logística Inversa (Reverse)',
};

/**
 * Render the real-time SSE stream health indicator and an interactive alert banner
 * whenever a new RFP ticket enters the system with `status = analyzing`.
 *
 * @param props - Connection status, latest arrival event, and user action handlers.
 * @returns JSX Element displaying SSE status and real-time arrival alert.
 */
export function RFPRealtimeNotificationBanner({
  connectionStatus,
  latestArrival,
  reconnectAttempt,
  onDismissArrival,
  onRetryConnection,
}: RFPRealtimeNotificationBannerProps): React.ReactElement {
  const nextDelaySeconds = Math.round(
    calculateReconnectBackoffMs(Math.max(0, reconnectAttempt - 1)) / 1000
  );

  const renderConnectionBadge = (): React.ReactElement => {
    switch (connectionStatus) {
      case 'connected':
        return (
          <div
            data-testid="sse-connection-badge"
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
          >
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>Tiempo Real Activo (SSE)</span>
          </div>
        );
      case 'reconnecting':
        return (
          <div
            data-testid="sse-connection-badge"
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20"
          >
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
            <span>
              Reconectando canal SSE (intento #{reconnectAttempt}, próx. en {nextDelaySeconds}s)...
            </span>
            <button
              type="button"
              onClick={onRetryConnection}
              className="ml-1 underline hover:text-amber-200 transition-colors"
            >
              Reintentar ahora
            </button>
          </div>
        );
      case 'unauthorized':
        return (
          <div
            data-testid="sse-connection-badge"
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20"
          >
            <span className="w-2 h-2 rounded-full bg-rose-400" />
            <span>Sesión expirada / No autorizado para canal SSE</span>
            <Link
              href="/login"
              className="ml-1 underline hover:text-rose-200 transition-colors"
            >
              Iniciar sesión
            </Link>
          </div>
        );
      case 'connecting':
        return (
          <div
            data-testid="sse-connection-badge"
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/20"
          >
            <span className="w-2 h-2 rounded-full bg-sky-400 animate-pulse" />
            <span>Conectando notificaciones en tiempo real...</span>
          </div>
        );
      default:
        return (
          <div
            data-testid="sse-connection-badge"
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700"
          >
            <span className="w-2 h-2 rounded-full bg-slate-500" />
            <span>Canal SSE desconectado</span>
          </div>
        );
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {renderConnectionBadge()}
      </div>

      {latestArrival && (
        <div
          role="status"
          aria-live="polite"
          data-testid="rfp-realtime-arrival-banner"
          className="relative overflow-hidden rounded-2xl bg-emerald-950/40 border border-emerald-500/40 p-4 shadow-lg transition-all"
        >
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="space-y-1.5">
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-400/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-300 animate-ping" />
                  Nuevo Ticket RFP en Tiempo Real
                </span>
                <span className="text-xs font-mono font-bold text-emerald-200">
                  {latestArrival.ticket_id}
                </span>
                <span className="text-xs font-mono text-slate-300">
                  ({latestArrival.rfp_id})
                </span>
                <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-sky-500/20 text-sky-300 border border-sky-500/30">
                  {latestArrival.client_country}
                </span>
                <span className="px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  status: {latestArrival.status}
                </span>
              </div>

              <p className="text-sm font-semibold text-slate-100">
                Cliente:{' '}
                <span className="text-emerald-300">{latestArrival.client_name}</span>
              </p>

              <div className="flex flex-wrap items-center gap-1.5 pt-0.5">
                <span className="text-xs text-slate-400">Servicios solicitados:</span>
                {latestArrival.services_requested.map((service) => (
                  <span
                    key={service}
                    className="px-2 py-0.5 rounded-md text-xs font-medium bg-slate-800/90 text-slate-200 border border-slate-700"
                  >
                    {SERVICE_LABELS[service] || service}
                  </span>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-3 self-end sm:self-center">
              <Link
                href={`/rfp/${latestArrival.ticket_id}`}
                className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500 text-slate-950 hover:bg-emerald-400 transition-colors"
              >
                Revisar Ticket →
              </Link>
              <button
                type="button"
                onClick={onDismissArrival}
                aria-label="Cerrar notificación de nuevo ticket RFP"
                className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-300 hover:text-white hover:bg-slate-800/60 transition-colors"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
