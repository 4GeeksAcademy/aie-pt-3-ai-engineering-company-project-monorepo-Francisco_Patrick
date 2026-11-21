'use client';

import React, { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import type {
  IntakeTicketAcceptedResponseDTO,
  IntakeTicketListResponseDTO,
  IntakeTicketSummaryDTO,
  TicketStatus,
} from '@repo/shared-types';
import { RFPUploadForm } from '../../components/rfp/RFPUploadForm';
import { TicketStatusBadge } from '../../components/rfp/TicketStatusBadge';

/**
 * Dashboard page for RFP proposals ingestion, status tracking, and ticket browsing.
 *
 * @returns JSX Element rendering the RFP intake dashboard.
 */
export default function RFPIntakePage(): React.ReactElement {
  const [tickets, setTickets] = useState<IntakeTicketSummaryDTO[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTickets = useCallback(async (): Promise<void> => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const query = statusFilter !== 'all' ? `?status=${statusFilter}&limit=50` : '?limit=50';
      const response = await fetch(`${apiUrl}/api/v1/rfp/tickets${query}`);
      if (!response.ok) {
        throw new Error('Error al consultar lista de propuestas.');
      }
      const data = (await response.json()) as IntakeTicketListResponseDTO;
      setTickets(data.items);
      setError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error desconocido de conexión.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchTickets();
  }, [fetchTickets]);

  // Polling mechanism: if any ticket is in 'analizando' state, refresh every 3 seconds
  useEffect(() => {
    const hasAnalyzing = tickets.some((t) => t.status === 'analizando');
    if (!hasAnalyzing) return;

    const interval = setInterval(() => {
      fetchTickets();
    }, 3000);

    return () => clearInterval(interval);
  }, [tickets, fetchTickets]);

  const handleUploadSuccess = (newTicket: IntakeTicketAcceptedResponseDTO): void => {
    // Optimistically prepend ticket to list and refresh
    fetchTickets();
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100 tracking-tight">
          Entrada y Análisis Inteligente de Propuestas (RFP)
        </h1>
        <p className="text-sm text-slate-400 mt-1">
          Ingesta asíncrona de pliegos PDF, cálculo de legibilidad, filtrado de validez y análisis multidepartamental.
        </p>
      </div>

      {/* Upload Dropzone Section */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-200 mb-4">Subir Nueva Propuesta de Cliente</h2>
        <RFPUploadForm onUploadSuccess={handleUploadSuccess} />
      </div>

      {/* Tickets List Section */}
      <div className="space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center space-x-2">
            <h2 className="text-base font-semibold text-slate-100">Propuestas Registradas</h2>
            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-300">
              {tickets.length}
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
                    Ticket #
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Cliente
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Archivo PDF
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
                    <td colSpan={6} className="px-6 py-10 text-center text-slate-400 text-sm">
                      <span className="inline-block w-5 h-5 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin mr-2 align-middle" />
                      Cargando propuestas...
                    </td>
                  </tr>
                ) : tickets.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-6 py-12 text-center text-slate-500 text-sm">
                      No se encontraron propuestas registradas con el filtro seleccionado.
                    </td>
                  </tr>
                ) : (
                  tickets.map((ticket) => (
                    <tr key={ticket.ticket_id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap text-xs font-mono font-bold text-slate-200">
                        {ticket.ticket_number}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-xs font-medium text-slate-100">
                        {ticket.client_name || <span className="text-slate-500 italic">Extrayendo...</span>}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-xs text-slate-400">
                        {ticket.raw_pdf_filename}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <TicketStatusBadge status={ticket.status as TicketStatus} />
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
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
