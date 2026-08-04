import React from 'react';
import Link from 'next/link';

export interface ActionCardItem {
  readonly title: string;
  readonly description: string;
  readonly href: string;
  readonly ctaText: string;
}

const ACTION_CARDS: readonly ActionCardItem[] = [
  {
    title: 'Ejecutar Business Logic Suite',
    description:
      'Accede a la suite interactiva para ejecutar filtros de envíos, evaluación de transportistas, ordenamiento y reportes de agregación de Milestone 2.',
    href: '/business-logic',
    ctaText: 'Abrir Business Logic Suite →',
  },
  {
    title: 'Gestión de Inventario Multinave',
    description:
      'Inspecciona el stock por SKU consolidado entre el almacén comercial de Los Angeles y las hojas sincronizadas de Zaragoza.',
    href: '#inventory',
    ctaText: 'Ver Inventario →',
  },
  {
    title: 'Agregador de Transportistas',
    description:
      'Monitorea la tasa de entregas a tiempo e incidencias por cada 100 envíos en las 8 APIs de transportistas unificadas.',
    href: '#carriers',
    ctaText: 'Ver Transportistas →',
  },
];

/**
 * Quick action cards component for backoffice operations.
 *
 * @returns JSX element rendering operational quick access cards
 */
export function QuickActionCards(): React.ReactElement {
  return (
    <section className="mt-8 grid gap-6 md:grid-cols-3">
      {ACTION_CARDS.map((card) => (
        <article
          key={card.title}
          className="flex flex-col justify-between rounded-xl border border-slate-800 bg-slate-900/80 p-6 transition-all hover:border-slate-700"
        >
          <div>
            <h2 className="text-base font-semibold text-slate-100">{card.title}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              {card.description}
            </p>
          </div>
          <div className="mt-6">
            <Link
              href={card.href}
              className="inline-flex items-center text-xs font-semibold text-cyan-300 hover:text-cyan-200"
            >
              {card.ctaText}
            </Link>
          </div>
        </article>
      ))}
    </section>
  );
}
