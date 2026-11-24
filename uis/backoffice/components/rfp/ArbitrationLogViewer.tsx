'use client';

import React from 'react';
import type { ArbitrationLogDTO, ArbitrationTriggerId } from '@repo/shared-types';

/**
 * Props for the ArbitrationLogViewer component.
 */
export interface ArbitrationLogViewerProps {
  /** Chronological list of deterministic conflict arbitration records for the ticket. */
  logs: ArbitrationLogDTO[];
}

const TRIGGER_LABELS: Record<ArbitrationTriggerId, string> = {
  'volume-vs-capacity': 'Volume vs. Warehouse Capacity',
  'returns-sla-breach': 'Returns SLA Breach (< 48h)',
  'currency-mismatch': 'Canonical Currency Mismatch',
};

/**
 * Displays the audit timeline of deterministic cross-department conflict arbitrations
 * resolved by Miguel Torres (Commercial Director) and Sofía Ramos (Reverse Logistics Lead).
 *
 * @param props - Component props containing the list of arbitration log entries.
 * @returns JSX Element rendering the arbitration audit log timeline.
 */
export function ArbitrationLogViewer({ logs }: ArbitrationLogViewerProps): React.ReactElement {
  if (logs.length === 0) {
    return (
      <div
        data-testid="arbitration-log-empty"
        className="bg-slate-900 border border-slate-800 rounded-xl p-5 text-xs text-slate-400"
      >
        Sin conflictos interdepartamentales detectados por el nodo de arbitraje determinista.
      </div>
    );
  }

  return (
    <div
      data-testid="arbitration-log-viewer"
      className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4 shadow-sm"
    >
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div>
          <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
            Registro de Arbitraje Determinista (Reglas de Briefing §7)
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Resoluciones ejecutadas automáticamente bajo supervisión de Miguel Torres y Sofía Ramos.
          </p>
        </div>
        <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30">
          {logs.length} {logs.length === 1 ? 'Arbitraje' : 'Arbitrajes'}
        </span>
      </div>

      <div className="space-y-3">
        {logs.map((log) => {
          const triggerLabel = TRIGGER_LABELS[log.trigger_id] ?? log.trigger_id;
          const affected = log.resolution_details.affected_departments.join(', ');

          return (
            <div
              key={log.id}
              data-testid={`arbitration-log-item-${log.trigger_id}`}
              className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 space-y-2"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center space-x-2">
                  <span className="px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                    {log.trigger_id}
                  </span>
                  <span className="text-xs font-semibold text-slate-200">{triggerLabel}</span>
                </div>
                <span className="text-xs text-emerald-400 font-semibold">
                  Árbitro: {log.arbiter}
                </span>
              </div>

              <p className="text-xs text-slate-300 leading-relaxed">{log.rule_applied}</p>

              <div className="bg-slate-900/80 border border-slate-800 rounded-lg p-3 text-xs space-y-1">
                <p className="text-slate-200">
                  <span className="font-semibold text-slate-400">Acción Aplicada: </span>
                  {log.resolution_details.action_taken}
                </p>
                <p className="text-slate-400">
                  <span className="font-semibold">Departamentos Afectados: </span>
                  <span className="text-slate-200 font-mono">{affected}</span>
                </p>
                {log.resolution_details.capped_volume !== undefined &&
                  log.resolution_details.capped_volume !== null && (
                    <p className="text-slate-400">
                      <span className="font-semibold">Volumen Máximo Fijado: </span>
                      <span className="text-emerald-400 font-bold">
                        {log.resolution_details.capped_volume} pedidos/mes
                      </span>
                    </p>
                  )}
                {log.resolution_details.enforced_currency && (
                  <p className="text-slate-400">
                    <span className="font-semibold">Moneda Canónica Aplicada: </span>
                    <span className="text-emerald-400 font-bold">
                      {log.resolution_details.enforced_currency}
                    </span>
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
