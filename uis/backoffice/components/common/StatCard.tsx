import React from 'react';
import type { BadgeVariant } from './StatusBadge';
import { StatusBadge } from './StatusBadge';

export interface StatCardProps {
  /** Metric card title label */
  readonly title: string;
  /** Primary metric display value */
  readonly value: string;
  /** Secondary subtitle or comparative metrics text */
  readonly subtitle?: string;
  /** Optional badge text label */
  readonly badgeText?: string;
  /** Optional badge color variant */
  readonly badgeVariant?: BadgeVariant;
  /** Optional extra CSS utility classes */
  readonly className?: string;
}

/**
 * Reusable StatCard component to standardize metric widgets across operational overview dashboards.
 *
 * @param props - Metric card properties including title, value, subtitle, and status badge properties.
 * @returns JSX Element rendering formatted statistical summary card.
 */
export function StatCard(props: StatCardProps): React.ReactElement {
  const { title, value, subtitle, badgeText, badgeVariant = 'slate', className = '' } = props;

  return (
    <article
      className={`rounded-xl border border-slate-800 bg-slate-900/90 p-5 shadow-lg transition-all hover:border-slate-700/80 ${className}`}
    >
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-slate-400">{title}</span>
        {badgeText !== undefined && badgeText !== '' && (
          <StatusBadge text={badgeText} variant={badgeVariant} />
        )}
      </div>
      <p className="mt-3 text-2xl font-bold text-slate-100">{value}</p>
      {subtitle !== undefined && subtitle !== '' && (
        <p className="mt-1 text-xs text-slate-400">{subtitle}</p>
      )}
    </article>
  );
}
