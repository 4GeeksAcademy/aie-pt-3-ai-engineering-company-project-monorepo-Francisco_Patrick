'use client';

import React from 'react';
import type { TicketStatus } from '@repo/shared-types';

/**
 * Props for the TicketStatusBadge component.
 */
export interface TicketStatusBadgeProps {
  /** Current lifecycle status of the ticket. */
  status: TicketStatus;
}

/**
 * Visual badge displaying ticket processing state with distinct status styling.
 *
 * @param props - Component props containing ticket status.
 * @returns JSX Element rendering colored status chip.
 */
export function TicketStatusBadge({ status }: TicketStatusBadgeProps): React.ReactElement {
  switch (status) {
    case 'analizando':
      return (
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse mr-1.5" />
          Analizando
        </span>
      );
    case 'descartado':
      return (
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/20">
          <span className="w-1.5 h-1.5 rounded-full bg-rose-400 mr-1.5" />
          Descartado
        </span>
      );
    case 'analisis_completo':
      return (
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5" />
          Análisis Completo
        </span>
      );
    case 'esperando_aprobación':
      return (
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-500/10 text-sky-400 border border-sky-500/20">
          <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse mr-1.5" />
          Esperando Aprobación
        </span>
      );
    case 'terminado':
      return (
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-400/30">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-300 mr-1.5" />
          Terminado
        </span>
      );
    case 'needs_human_review':
      return (
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-300 border border-amber-500/20">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-300 mr-1.5" />
          Revisión Humana
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-500/10 text-slate-400 border border-slate-500/20">
          {status}
        </span>
      );
  }
}
