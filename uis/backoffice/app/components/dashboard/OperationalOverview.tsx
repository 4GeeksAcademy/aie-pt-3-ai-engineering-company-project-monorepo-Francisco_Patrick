import React from 'react';
import type { BadgeVariant } from '../../../components/common/StatusBadge';
import { StatCard } from '../../../components/common/StatCard';

export interface OverviewMetricCard {
  readonly title: string;
  readonly value: string;
  readonly subtitle: string;
  readonly badgeText: string;
  readonly badgeVariant: BadgeVariant;
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
 * Refactored to utilize the reusable StatCard component and memoized for re-render optimization.
 *
 * @returns JSX element rendering the operational metrics grid
 */
export const OperationalOverview = React.memo(function OperationalOverview(): React.ReactElement {
  return (
    <section className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
      {OVERVIEW_METRICS.map((metric) => (
        <StatCard
          key={metric.title}
          title={metric.title}
          value={metric.value}
          subtitle={metric.subtitle}
          badgeText={metric.badgeText}
          badgeVariant={metric.badgeVariant}
        />
      ))}
    </section>
  );
});
