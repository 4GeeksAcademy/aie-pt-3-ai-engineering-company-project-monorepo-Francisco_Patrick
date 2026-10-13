import React from 'react';
import dynamic from 'next/dynamic';

const OperationalOverview = dynamic(
  () =>
    import('./components/dashboard/OperationalOverview').then(
      (mod) => mod.OperationalOverview
    ),
  { ssr: true }
);

const QuickActionCards = dynamic(
  () =>
    import('./components/dashboard/QuickActionCards').then(
      (mod) => mod.QuickActionCards
    ),
  { ssr: true }
);

/**
 * Entry page route (`/`) inside `./uis/backoffice` providing administrative welcome screen,
 * high-level metrics overview, and quick action shortcuts.
 *
 * @returns JSX element rendering the entry dashboard view
 */
export default function BackofficeHomePage(): React.ReactElement {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 sm:p-8 max-w-7xl mx-auto space-y-8">
      <section className="relative overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/90 p-8 shadow-2xl backdrop-blur-xl">
        {/* Subtle background glow effect */}
        <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 -left-24 h-72 w-72 rounded-full bg-emerald-500/10 blur-3xl" />

        <div className="relative z-10 flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-widest text-cyan-400 font-semibold">
              TrackFlow Operations Control
            </p>
            <h1 className="mt-1 text-2xl font-bold text-slate-100 sm:text-3xl">
              Bienvenido al Panel Interno de Operaciones
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
              Visibilidad consolidada de inventario, transportistas y logística inversa para los hubs de Los Angeles y Zaragoza.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="rounded-lg border border-slate-700/80 bg-slate-950/80 px-4 py-2 text-xs font-semibold text-cyan-300 shadow-inner">
              Ambiente: Monorepo Internal
            </span>
          </div>
        </div>
      </section>

      <OperationalOverview />
      <QuickActionCards />
    </div>
  );
}
