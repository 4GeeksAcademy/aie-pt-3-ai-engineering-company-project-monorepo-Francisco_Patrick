'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import Link from 'next/link';
import type {
  IntakeTicketAcceptedResponseDTO,
  IntakeTicketListResponseDTO,
  IntakeTicketSummaryDTO,
  TicketStatus,
} from '@repo/shared-types';
import { RFPUploadForm } from '../../components/rfp/RFPUploadForm';
import { RFPRealtimeNotificationBanner } from '../../components/rfp/RFPRealtimeNotificationBanner';
import { TicketStatusBadge } from '../../components/rfp/TicketStatusBadge';
import { useRFPNotifications } from '../../hooks/useRFPNotifications';
import { getToken } from '../../lib/auth';
import { mergeAndDeduplicateTickets } from '../../lib/rfpNotificationsClient';

/**
 * Dashboard page for RFP proposals ingestion, real-time SSE notifications, status tracking,
 * and ticket browsing.
 *
 * Replaces manual refresh and periodic full-list polling for new ticket discovery with an
 * authenticated Server-Sent Events (SSE) stream (`GET /api/v1/rfp/notifications/stream`).
 *
 * @returns JSX Element rendering the RFP intake dashboard with real-time notifications.
 */
export default function RFPIntakePage(): React.ReactElement {
  const [tickets, setTickets] = useState<IntakeTicketSummaryDTO[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const handleIncomingRealtimeTickets = useCallback(
    (incomingTickets: IntakeTicketSummaryDTO[]): void => {
      setTickets((prevTickets) =>
        mergeAndDeduplicateTickets(prevTickets, incomingTickets)
      );
    },
    []
  );

  const {
    connectionStatus,
    latestArrival,
    realtimeTicketIds,
    reconnectAttempt,
    dismissLatestArrival,
    retryConnection,
  } = useRFPNotifications({
    statusFilter,
    onTicketsReceived: handleIncomingRealtimeTickets,
  });

  const fetchTickets = useCallback(async (): Promise<void> => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const query =
        statusFilter !== 'all' ? `?status=${statusFilter}&limit=50` : '?limit=50';
      const token = getToken();
      const headers: Record<string, string> = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }
      const response = await fetch(`${apiUrl}/api/v1/rfp/tickets${query}`, {
        headers,
      });
      if (!response.ok) {
        throw new Error('Error al consultar lista de propuestas.');
      }
      const data = (await response.json()) as IntakeTicketListResponseDTO;
      setTickets((prevTickets) =>
        mergeAndDeduplicateTickets(prevTickets, data.items)
      );
      setError(null);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Error desconocido de conexión.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    void fetchTickets();
  }, [fetchTickets]);

  const handleUploadSuccess = useCallback(
    (_newTicket: IntakeTicketAcceptedResponseDTO): void => {
      void fetchTickets();
    },
    [fetchTickets]
  );

  const visibleTickets = useMemo((): IntakeTicketSummaryDTO[] => {
    if (statusFilter === 'all') {
      return tickets;
    }
    return tickets.filter((ticket) => ticket.status === statusFilter);
  }, [tickets, statusFilter]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Page Header & Real-Time SSE Status */}
      <div className="flex flex-col gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight">
            Entrada y Análisis Inteligente de Propuestas (RFP)
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Canal en tiempo real (SSE) para el equipo comercial de Miguel Torres: recepción instantánea de nuevos tickets RFP en estado analizando.
          </p>
        </div>

        <RFPRealtimeNotificationBanner
          connectionStatus={connectionStatus}
          latestArrival={latestArrival}
          reconnectAttempt={reconnectAttempt}
          onDismissArrival={dismissLatestArrival}
          onRetryConnection={retryConnection}
        />
      </div>

      {/* Upload Dropzone Section */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-200 mb-4">
          Subir Nueva Propuesta de Cliente
        </h2>
        <RFPUploadForm onUploadSuccess={handleUploadSuccess} />
      </div>

      {/* Tickets List Section */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center space-x-2">
            <h2 className="text-base font-semibold text-slate-100">
              Propuestas Registradas
            </h2>
            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-300">
              {visibleTickets.length}
            </span>
          </div>

          {/* Status Filter Tabs */}
          <div className="flex bg-slate-900 border border-slate-800 rounded-lg p-1 space-x-1">
            {[
              { id: 'all', label: 'Todas' },
              { id: 'analizando', label: 'Analizando' },
              { id: 'analisis_completo', label: 'Completadas' },
              { id: 'descartado', label: 'Descartadas' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setStatusFilter(tab.id)}
                className={`px-3 py-1 text-xs font-semibold rounded-md transition-colors ${
                  statusFilter === tab.id
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs">
            {error}
          </div>
        )}

        {/* Table */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-800">
              <thead className="bg-slate-950/50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Ticket / RFP ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Cliente & País
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Servicios Solicitados
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Estado
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Fecha de Entrada
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Acciones
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {isLoading ? (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-6 py-10 text-center text-slate-400 text-sm"
                    >
                      <span className="inline-block w-5 h-5 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin mr-2 align-middle" />
                      Cargando propuestas...
                    </td>
                  </tr>
                ) : visibleTickets.length === 0 ? (
                  <tr>
                    <td
                      colSpan={6}
                      className="px-6 py-12 text-center text-slate-500 text-sm"
                    >
                      No se encontraron propuestas registradas con el filtro seleccionado.
                    </td>
                  </tr>
                ) : (
                  visibleTickets.map((ticket) => {
                    const isRealtime =
                      Boolean(ticket.isNewRealtimeArrival) ||
                      realtimeTicketIds.has(ticket.ticket_id);

                    return (
                      <tr
                        key={ticket.ticket_id}
                        data-testid={`rfp-ticket-row-${ticket.ticket_id}`}
                        className={`transition-colors ${
                          isRealtime
                            ? 'bg-emerald-950/25 hover:bg-emerald-900/30'
                            : 'hover:bg-slate-800/30'
                        }`}
                      >
                        <td className="px-6 py-4 whitespace-nowrap text-xs font-mono font-bold text-slate-200">
                          <div className="flex flex-col gap-1">
                            <div className="flex items-center gap-2">
                              <span>{ticket.ticket_id}</span>
                              {isRealtime && (
                                <span
                                  data-testid={`realtime-badge-${ticket.ticket_id}`}
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-sans font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                                >
                                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                                  Nuevo en tiempo real
                                </span>
                              )}
                            </div>
                            <span className="text-[11px] font-normal text-slate-400">
                              RFP: {ticket.rfp_id || ticket.ticket_number}
                            </span>
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-xs font-medium text-slate-100">
                          <div className="flex items-center gap-2">
                            <span>
                              {ticket.client_name || (
                                <span className="text-slate-500 italic">
                                  Extrayendo...
                                </span>
                              )}
                            </span>
                            {ticket.client_country && (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-slate-800 text-slate-300 border border-slate-700">
                                {ticket.client_country}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-xs text-slate-300">
                          {ticket.services_requested &&
                          ticket.services_requested.length > 0 ? (
                            <div className="flex flex-wrap gap-1">
                              {ticket.services_requested.map((service) => (
                                <span
                                  key={service}
                                  className="px-2 py-0.5 rounded text-[11px] font-medium bg-slate-800 text-slate-300 border border-slate-700"
                                >
                                  {service}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-slate-500">
                              {ticket.raw_pdf_filename}
                            </span>
                          )}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <TicketStatusBadge
                            status={ticket.status as TicketStatus}
                          />
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-xs text-slate-400">
                          {new Date(ticket.created_at).toLocaleString()}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-right text-xs">
                          <Link
                            href={`/rfp/${ticket.ticket_id}`}
                            className="font-semibold text-emerald-400 hover:text-emerald-300 transition-colors"
                          >
                            Ver Detalle →
                          </Link>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
