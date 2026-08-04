import React from 'react';

export interface OverviewMetricCard {
  readonly title: string;
  readonly value: string;
  readonly subtitle: string;
  readonly badgeText: string;
  readonly badgeVariant: 'emerald' | 'cyan' | 'amber';
}

const OVERVIEW_METRICS: readonly OverviewMetricCard[] = [
  {
    title: 'Almacenes Activos',
    value: '2 Hubs',
    subtitle: 'Los Angeles (US) + Zaragoza (ES)',
    badgeText: 'Operativo',
    badgeVariant: 'emerald',
  },
  {
    title: 'APIs Transportistas',
    value: '8 Integraciones',
    subtitle: 'UPS, FedEx, DHL, MRW, SEUR...',
    badgeText: 'Live Feed',
    badgeVariant: 'cyan',
  },
  {
    title: 'SLA Envíos On-Time',
    value: '98.4%',
    subtitle: 'Promedio consolidado en 30 días',
    badgeText: '+1.2% vs mes ant.',
    badgeVariant: 'emerald',
  },
  {
    title: 'Devoluciones en Proceso',
    value: '14 Solicitudes',
    subtitle: 'Aprobación automática configurada',
    badgeText: 'En cola',
    badgeVariant: 'amber',
  },
];

/**
 * Operational overview metrics widget component for the backoffice dashboard entry page.
 *
 * @returns JSX element rendering the operational metrics grid
 */
export function OperationalOverview(): React.ReactElement {
  return (
    <section className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
      {OVERVIEW_METRICS.map((metric) => (
        <article
          key={metric.title}
          className="rounded-xl border border-slate-800 bg-slate-900/90 p-5 shadow-lg"
        >
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400 font-medium">{metric.title}</span>
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${
                metric.badgeVariant === 'emerald'
                  ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                  : metric.badgeVariant === 'cyan'
                  ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                  : 'bg-amber-950 text-amber-300 border border-amber-800'
              }`}
            >
              {metric.badgeText}
            </span>
          </div>
          <p className="mt-3 text-2xl font-bold text-slate-100">{metric.value}</p>
          <p className="mt-1 text-xs text-slate-400">{metric.subtitle}</p>
        </article>
      ))}
    </section>
  );
}
