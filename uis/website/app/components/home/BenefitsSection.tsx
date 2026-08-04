import React from 'react';

export interface BenefitCard {
  readonly id: string;
  readonly title: string;
  readonly description: string;
}

const DEFAULT_BENEFITS: readonly BenefitCard[] = [
  {
    id: 'benefit-1',
    title: 'Menos errores de inventario',
    description:
      'Consolidación de stock por SKU entre Los Angeles y Zaragoza en una sola vista operativa.',
  },
  {
    id: 'benefit-2',
    title: 'Entregas más predecibles',
    description:
      'Motor de decisión de transportista por coste, urgencia y rendimiento histórico de ruta.',
  },
  {
    id: 'benefit-3',
    title: 'Mejor experiencia cliente',
    description:
      'Portal de tracking y resolución de incidencias con menos fricción para marcas y consumidores.',
  },
];

/**
 * Benefits section component detailing key operational advantages for e-commerce brands.
 *
 * @returns JSX element rendering the benefits grid section
 */
export function BenefitsSection(): React.ReactElement {
  return (
    <section
      id="beneficios"
      className="mx-auto w-full max-w-6xl px-4 py-14 sm:px-6 sm:py-16 lg:px-8 lg:py-20"
      aria-labelledby="beneficios-title"
    >
      <h2 id="beneficios-title" className="text-2xl font-semibold text-slate-100 sm:text-3xl">
        Beneficios para tu operación
      </h2>
      <p className="mt-3 max-w-3xl text-sm leading-7 text-slate-300 sm:text-base">
        Diseñado para equipos de operaciones, account managers y dirección que
        necesitan tomar decisiones con datos fiables.
      </p>
      <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {DEFAULT_BENEFITS.map((benefit) => (
          <article
            key={benefit.id}
            className="rounded-xl border border-slate-800 bg-slate-900 p-6"
          >
            <h3 className="text-lg font-semibold text-slate-100">{benefit.title}</h3>
            <p className="mt-2 text-sm leading-7 text-slate-300">
              {benefit.description}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}
