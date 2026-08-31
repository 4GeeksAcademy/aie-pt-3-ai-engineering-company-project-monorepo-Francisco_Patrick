import React from 'react';
import type { Metadata } from 'next';
import { ApplicationForm } from '../components/home/ApplicationForm';

export const metadata: Metadata = {
  title: 'TrackFlow | Application Form',
  description:
    'Solicita tu implementación con TrackFlow para digitalizar inventario, última milla y devoluciones en Estados Unidos y España.',
};

const APPLICATION_PAGE_SCHEMA = {
  '@context': 'https://schema.org',
  '@type': 'WebPage',
  name: 'TrackFlow Application Form',
  url: 'https://www.trackflow.example/application',
  description:
    'Formulario de solicitud para marcas e-commerce que quieren modernizar su operación logística con TrackFlow.',
  isPartOf: {
    '@type': 'WebSite',
    name: 'TrackFlow',
    url: 'https://www.trackflow.example',
  },
};

/**
 * Application intake form page (`/application`) for prospective e-commerce clients.
 *
 * @returns JSX element rendering the intake form page
 */
export default function ApplicationPage(): React.ReactElement {
  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(APPLICATION_PAGE_SCHEMA) }}
      />
      <section
        className="relative overflow-hidden border-b border-slate-800"
        aria-labelledby="application-title"
      >
        <div
          className="absolute inset-0 bg-[radial-gradient(circle_at_15%_20%,rgba(45,212,191,0.2),transparent_35%),radial-gradient(circle_at_85%_10%,rgba(56,189,248,0.16),transparent_35%)]"
          aria-hidden="true"
        />
        <div className="relative mx-auto grid w-full max-w-6xl gap-10 px-4 py-14 sm:px-6 sm:py-18 lg:grid-cols-[1.05fr_0.95fr] lg:items-start lg:gap-12 lg:px-8 lg:py-20">
          <section aria-labelledby="application-title">
            <p className="mb-4 inline-block rounded-full border border-cyan-300/40 bg-cyan-300/10 px-4 py-1 text-xs uppercase tracking-[0.18em] text-cyan-200">
              Implementation Intake
            </p>
            <h1
              id="application-title"
              className="text-3xl font-semibold leading-tight text-slate-100 sm:text-4xl lg:text-5xl"
            >
              Solicita tu onboarding con una operación pensada para crecer sin
              fricción.
            </h1>
            <p className="mt-5 max-w-xl text-sm leading-7 text-slate-300 sm:text-base">
              Este formulario nos ayuda a entender tu volumen, mercados y retos
              operativos para proponer una implantación realista de inventario,
              fulfillment, tracking y devoluciones.
            </p>

            <div className="mt-8 grid gap-4 sm:grid-cols-2">
              <article className="rounded-xl border border-slate-800 bg-slate-900/90 p-5">
                <h2 className="text-base font-semibold text-slate-100">Lo que evaluamos</h2>
                <p className="mt-2 text-sm leading-7 text-slate-300">
                  Cobertura geográfica, complejidad operativa, necesidades de
                  integración y urgencia de despliegue.
                </p>
              </article>
              <article className="rounded-xl border border-slate-800 bg-slate-900/90 p-5">
                <h2 className="text-base font-semibold text-slate-100">Lo que recibes</h2>
                <p className="mt-2 text-sm leading-7 text-slate-300">
                  Una recomendación inicial de alcance, mercados prioritarios y
                  siguiente paso comercial con TrackFlow.
                </p>
              </article>
            </div>

            <section
              className="mt-8 rounded-2xl border border-slate-800 bg-slate-900/80 p-6"
              aria-labelledby="benefits-title"
            >
              <h2 id="benefits-title" className="text-lg font-semibold text-slate-100">
                Por qué las marcas aplican con TrackFlow
              </h2>
              <ul className="mt-4 space-y-3 text-sm text-slate-300">
                <li>
                  • Visibilidad unificada de inventario entre Los Angeles y Zaragoza.
                </li>
                <li>
                  • Integración con transportistas y seguimiento consolidado para soporte B2B y B2C.
                </li>
                <li>
                  • Procesos de devolución y última milla con automatización orientada a SLA y margen operativo.
                </li>
              </ul>
            </section>
          </section>

          <section
            className="rounded-2xl border border-slate-700 bg-slate-900/95 p-6 shadow-2xl shadow-cyan-950/30"
            aria-labelledby="form-title"
          >
            <h2 id="form-title" className="text-2xl font-semibold text-slate-100">
              Application / Sign-up Form
            </h2>
            <p className="mt-2 text-sm leading-7 text-slate-300">
              Completa todos los campos para que podamos preparar una evaluación
              inicial de tu operación.
            </p>

            <ApplicationForm />
          </section>
        </div>
      </section>
    </>
  );
}
