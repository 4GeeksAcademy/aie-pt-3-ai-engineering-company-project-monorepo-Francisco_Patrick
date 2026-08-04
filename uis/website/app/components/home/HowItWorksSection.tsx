import React from 'react';

export interface WorkflowStep {
  readonly stepNumber: number;
  readonly title: string;
  readonly description: string;
}

const DEFAULT_STEPS: readonly WorkflowStep[] = [
  {
    stepNumber: 1,
    title: 'Conectamos tus fuentes',
    description:
      'Integramos tus canales de pedidos, almacenes y transportistas sin interrumpir la operativa diaria.',
  },
  {
    stepNumber: 2,
    title: 'Activamos automatizaciones',
    description:
      'Orquestamos reglas para asignación de envío, tracking unificado y gestión inteligente de devoluciones.',
  },
  {
    stepNumber: 3,
    title: 'Medimos y optimizamos',
    description:
      'Entregamos dashboards ejecutivos y operativos para mejorar SLA, costes y satisfacción de cliente.',
  },
];

/**
 * How It Works section component outlining the 3-step TrackFlow onboarding process.
 *
 * @returns JSX element rendering the workflow steps section
 */
export function HowItWorksSection(): React.ReactElement {
  return (
    <section
      id="como-funciona"
      className="border-y border-slate-800 bg-slate-900/60"
      aria-labelledby="como-funciona-title"
    >
      <div className="mx-auto w-full max-w-6xl px-4 py-14 sm:px-6 sm:py-16 lg:px-8 lg:py-20">
        <h2
          id="como-funciona-title"
          className="text-2xl font-semibold text-slate-100 sm:text-3xl"
        >
          Cómo funciona
        </h2>
        <ol className="mt-8 grid gap-5 md:grid-cols-3">
          {DEFAULT_STEPS.map((step) => (
            <li
              key={step.stepNumber}
              className="rounded-xl border border-slate-700 bg-slate-950 p-6"
            >
              <p className="text-xs font-semibold uppercase tracking-wider text-cyan-300">
                Paso {step.stepNumber}
              </p>
              <h3 className="mt-2 text-lg font-semibold text-slate-100">
                {step.title}
              </h3>
              <p className="mt-2 text-sm leading-7 text-slate-300">
                {step.description}
              </p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
