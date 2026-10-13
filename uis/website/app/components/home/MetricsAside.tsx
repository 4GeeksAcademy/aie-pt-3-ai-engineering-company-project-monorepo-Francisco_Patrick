import React from 'react';

export interface MetricItem {
  readonly label: string;
  readonly value: string;
}

export interface MetricsAsideProps {
  /** Optional custom title for metrics section */
  readonly title?: string;
  /** Optional array of metric key-value pairs */
  readonly metrics?: readonly MetricItem[];
}

const DEFAULT_METRICS: readonly MetricItem[] = [
  { label: 'Visibilidad de inventario multinave', value: 'En tiempo real' },
  { label: 'Seguimiento de transportistas', value: '8 APIs unificadas' },
  { label: 'Automatización de devoluciones', value: 'Hasta 25% del flujo' },
  { label: 'Soporte operativo', value: 'ES / EN' },
];

/**
 * Metrics aside component displaying core operational performance indicators.
 *
 * @param props - Custom metrics title and key-value payload list
 * @returns JSX element rendering the metrics highlights panel
 */
export function MetricsAside(props: MetricsAsideProps): React.ReactElement {
  const title = props.title ?? 'Resultados que importan';
  const metrics = props.metrics ?? DEFAULT_METRICS;

  return (
    <aside
      className="rounded-2xl border border-slate-700 bg-slate-900/90 p-6 shadow-2xl shadow-cyan-900/30"
      aria-label="Indicadores operativos"
    >
      <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
      <ul className="mt-5 space-y-4 text-sm">
        {metrics.map((item, index) => {
          const isLast = index === metrics.length - 1;
          return (
            <li
              key={item.label}
              className={`flex items-start justify-between gap-4 ${
                isLast ? '' : 'border-b border-slate-800 pb-3'
              }`}
            >
              <span className="text-slate-300">{item.label}</span>
              <span className="font-semibold text-cyan-300">{item.value}</span>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
