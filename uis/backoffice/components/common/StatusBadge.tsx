import React from 'react';

export type BadgeVariant = 'emerald' | 'cyan' | 'amber' | 'rose' | 'indigo' | 'slate';

export interface StatusBadgeProps {
  /** Text content to display inside the badge */
  readonly text: string;
  /** Visual color theme variant for the badge styling */
  readonly variant?: BadgeVariant;
  /** Optional extra CSS utility classes */
  readonly className?: string;
}

const VARIANT_CLASSES: Record<BadgeVariant, string> = {
  emerald: 'bg-emerald-950 text-emerald-300 border-emerald-800',
  cyan: 'bg-cyan-950 text-cyan-300 border-cyan-800',
  amber: 'bg-amber-950 text-amber-300 border-amber-800',
  rose: 'bg-rose-950 text-rose-300 border-rose-800',
  indigo: 'bg-indigo-950 text-indigo-300 border-indigo-800',
  slate: 'bg-slate-900 text-slate-300 border-slate-700',
};

/**
 * Reusable StatusBadge component providing consistent color variant badges across dashboards and data tables.
 *
 * @param props - Status badge configuration properties including text, color variant, and optional class names.
 * @returns JSX Element rendering styled badge tag.
 */
export function StatusBadge(props: StatusBadgeProps): React.ReactElement {
  const { text, variant = 'slate', className = '' } = props;
  const variantStyle = VARIANT_CLASSES[variant];

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${variantStyle} ${className}`}
    >
      {text}
    </span>
  );
}
