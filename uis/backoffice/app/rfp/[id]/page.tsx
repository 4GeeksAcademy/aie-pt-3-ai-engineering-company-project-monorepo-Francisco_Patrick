'use client';

import React, { useEffect, useState, useCallback, use } from 'react';
import Link from 'next/link';
import type {
  IntakeTicketDetailResponseDTO,
  TicketStatus,
} from '@repo/shared-types';
import { TicketStatusBadge } from '../../../components/rfp/TicketStatusBadge';
import { ReadabilityMetricCard } from '../../../components/rfp/ReadabilityMetricCard';
import { DepartmentKeyAspectsCard } from '../../../components/rfp/DepartmentKeyAspectsCard';
import { HandoffJsonViewer } from '../../../components/rfp/HandoffJsonViewer';

/**
 * Page props interface matching Next.js App Router dynamic route parameters.
 */
export interface RFPDetailPageProps {
  /** Promise containing dynamic route route params. */
  params: Promise<{ id: string }>;
}

/**
 * Detailed view of an RFP intake ticket showing analysis results, department worker findings,
 * executive briefing, and Part 2 proposal generation handoff payload.
 *
 * @param props - Next.js page props with route params.
 * @returns JSX Element rendering the ticket detail page.
 */
export default function RFPDetailPage({ params }: RFPDetailPageProps): React.ReactElement {
  const resolvedParams = use(params);
  const ticketId = resolvedParams.id;

  const [ticket, setTicket] = useState<IntakeTicketDetailResponseDTO | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTicket = useCallback(async (): Promise<void> => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/v1/rfp/tickets/${ticketId}`);
      if (!response.ok) {
        throw new Error(`Error al obtener ticket ${ticketId}.`);
      }
      const data = (await response.json()) as IntakeTicketDetailResponseDTO;
      setTicket(data);
      setError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error desconocido al cargar ticket.';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [ticketId]);

  useEffect(() => {
    fetchTicket();
  }, [fetchTicket]);

  // Polling: if still analyzing, poll every 2.5 seconds
  useEffect(() => {
    if (!ticket || ticket.status !== 'analizando') return;

    const interval = setInterval(() => {
      fetchTicket();
    }, 2500);

    return () => clearInterval(interval);
  }, [ticket, fetchTicket]);

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 text-center text-slate-400">
        <span className="inline-block w-6 h-6 border-2 border-emerald-400 border-t-transparent rounded-full animate-spin mr-3 align-middle" />
        Cargando detalles de la propuesta...
      </div>
    );
  }

  if (error || !ticket) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-16 space-y-4">
        <Link href="/rfp" className="text-xs font-semibold text-emerald-400 hover:underline">
          ← Volver a Propuestas
        </Link>
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-sm">
          {error || 'No se pudo encontrar el ticket solicitado.'}
        </div>
      </div>
    );
  }

  const metadata = ticket.metadata;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
      {/* Breadcrumb Navigation */}
      <div>
        <Link
          href="/rfp"
          className="inline-flex items-center text-xs font-semibold text-slate-400 hover:text-emerald-400 transition-colors"
        >
          ← Volver a Propuestas RFP
        </Link>
      </div>

      {/* Header Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center space-x-3">
              <h1 className="text-2xl font-extrabold text-slate-100 tracking-tight font-mono">
                {ticket.ticket_number}
              </h1>
              <TicketStatusBadge status={ticket.status as TicketStatus} />
            </div>
            <p className="text-sm font-medium text-slate-300 mt-1">
              Cliente:{' '}
              <span className="text-emerald-400 font-semibold">
                {metadata?.client_name || 'En análisis...'}
              </span>
            </p>
            <p className="text-xs text-slate-500 mt-0.5">
              Archivo: {ticket.raw_pdf_filename} ({(ticket.file_size_bytes / 1024).toFixed(1)} KB)
            </p>
          </div>

          {/* Quick Metrics */}
          {metadata && (
            <div className="flex flex-wrap gap-3">
              <div className="bg-slate-800/60 rounded-lg px-3 py-2 border border-slate-800 text-center">
                <p className="text-[10px] text-slate-400 uppercase">País / Moneda</p>
                <p className="text-xs font-bold text-slate-100 mt-0.5">
                  {metadata.client_country} ({metadata.currency})
                </p>
              </div>

              <div className="bg-slate-800/60 rounded-lg px-3 py-2 border border-slate-800 text-center">
                <p className="text-[10px] text-slate-400 uppercase">Volumen Mensual</p>
                <p className="text-xs font-bold text-slate-100 mt-0.5">
                  {metadata.monthly_volume
                    ? `${metadata.monthly_volume.toLocaleString()} pedidos`
                    : 'No especificado'}
                </p>
              </div>

              <div className="bg-slate-800/60 rounded-lg px-3 py-2 border border-slate-800 text-center">
                <p className="text-[10px] text-slate-400 uppercase">Departamentos</p>
                <p className="text-xs font-bold text-emerald-400 mt-0.5">
                  {metadata.departments_needed.join(', ')}
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Discarded Reason Alert */}
      {ticket.status === 'descartado' && (
        <div className="bg-rose-500/10 border border-rose-500/20 rounded-xl p-5 space-y-2">
          <div className="flex items-center space-x-2">
            <svg className="w-5 h-5 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3 className="text-sm font-semibold text-rose-400">Propuesta Descartada por el Clasificador</h3>
          </div>
          <p className="text-xs text-rose-200 leading-relaxed">
            {ticket.rejection_reason || 'El documento no cumple los requisitos para ser clasificado como RFP legítima.'}
          </p>
          {ticket.error_message && (
            <p className="text-[11px] text-rose-400/80 font-mono mt-2">
              Detalle técnico: {ticket.error_message}
            </p>
          )}
        </div>
      )}

      {/* Analyzing Banner */}
      {ticket.status === 'analizando' && (
        <div className="bg-amber-500/10 border border-amber-500/20 rounded-xl p-6 text-center space-y-3">
          <span className="inline-block w-8 h-8 border-3 border-amber-400 border-t-transparent rounded-full animate-spin" />
          <h3 className="text-sm font-semibold text-amber-300">Análisis Multidepartamental en Curso</h3>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            El pipeline LangGraph está convirtiendo el PDF a Markdown, calculando métricas de legibilidad y consultando a los trabajadores departamentales.
          </p>
        </div>
      )}

      {/* Complete Analysis Sections */}
      {ticket.status === 'analisis_completo' && (
        <div className="space-y-8">
          {/* Executive Summary for Sales */}
          {ticket.handoff && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4 shadow-sm">
              <div className="flex items-center space-x-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400" />
                <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
                  Síntesis Comercial para Ventas (Miguel Torres)
                </h3>
              </div>
              <div className="text-xs text-slate-300 leading-relaxed whitespace-pre-line bg-slate-950/60 p-4 rounded-lg border border-slate-800 font-sans">
                {ticket.handoff.executive_summary}
              </div>
            </div>
          )}

          {/* Readability Scores Card */}
          {metadata && <ReadabilityMetricCard scores={metadata.readability_scores} />}

          {/* Department Worker Sections */}
          <DepartmentKeyAspectsCard sections={ticket.department_sections} />

          {/* Handoff Viewer */}
          <HandoffJsonViewer handoff={ticket.handoff} />
        </div>
      )}
    </div>
  );
}
