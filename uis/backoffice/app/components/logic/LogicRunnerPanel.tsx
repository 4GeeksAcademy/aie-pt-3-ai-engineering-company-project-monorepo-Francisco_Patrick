'use client';

import React from 'react';

export type LogicActionType =
  | 'filter-shipments'
  | 'filter-carriers'
  | 'filter-returns'
  | 'sort-asc'
  | 'sort-desc'
  | 'sort-multi'
  | 'linear-search'
  | 'binary-search'
  | 'report'
  | 'validate';

export interface LogicRunnerPanelProps {
  /** Active action identifier */
  readonly activeAction: LogicActionType;
  /** Callback fired when an action trigger button is clicked */
  readonly onTriggerAction: (action: LogicActionType) => void;
}

/**
 * Interactive control panel offering action triggers for executing Milestone 2 business logic functions.
 *
 * @param props - Active action state and trigger callback
 * @returns JSX element rendering the business logic action buttons
 */
export function LogicRunnerPanel(props: LogicRunnerPanelProps): React.ReactElement {
  const { activeAction, onTriggerAction } = props;

  const buttons: readonly { id: LogicActionType; label: string; group: string }[] = [
    { id: 'filter-shipments', label: 'Filtrar Shipments (ES + Express)', group: 'Filtrado' },
    { id: 'filter-carriers', label: 'Filtrar Carriers (US + SLA >= 90%)', group: 'Filtrado' },
    { id: 'filter-returns', label: 'Filtrar Devoluciones (US + Aprobado)', group: 'Filtrado' },
    { id: 'sort-asc', label: 'Orden ASC (Operational Cost)', group: 'Ordenamiento' },
    { id: 'sort-desc', label: 'Orden DESC (Weight Kg)', group: 'Ordenamiento' },
    { id: 'sort-multi', label: 'Orden Múltiple (Country + Cost)', group: 'Ordenamiento' },
    { id: 'linear-search', label: 'Búsqueda Lineal (sh-1003)', group: 'Búsqueda' },
    { id: 'binary-search', label: 'Búsqueda Binaria (sh-1004)', group: 'Búsqueda' },
    { id: 'report', label: 'Generar Reporte Agregado', group: 'Reportes' },
    { id: 'validate', label: 'Auditar Reglas de Negocio', group: 'Validación' },
  ];

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/90 p-6">
      <h2 className="text-base font-semibold text-slate-100">
        Disparadores de Lógica de Negocio
      </h2>
      <p className="mt-1 text-xs text-slate-400">
        Selecciona una acción para ejecutar los algoritmos del módulo de dominio directamente en la interfaz.
      </p>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {buttons.map((btn) => {
          const isActive = activeAction === btn.id;
          return (
            <button
              key={btn.id}
              type="button"
              onClick={() => onTriggerAction(btn.id)}
              className={`flex flex-col items-start justify-between rounded-lg border px-4 py-3 text-left text-xs transition-all ${
                isActive
                  ? 'border-cyan-400 bg-cyan-400/10 text-cyan-300 font-semibold shadow-lg shadow-cyan-950/40'
                  : 'border-slate-700 bg-slate-950 text-slate-300 hover:border-slate-600 hover:bg-slate-900'
              }`}
            >
              <span className="text-[10px] uppercase tracking-wider text-slate-400">
                {btn.group}
              </span>
              <span className="mt-1 font-medium">{btn.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
