import React from 'react';
import { OperationalOverview } from './components/dashboard/OperationalOverview';
import { QuickActionCards } from './components/dashboard/QuickActionCards';

/**
 * Entry page route (`/`) inside `./uis/backoffice` providing administrative welcome screen,
 * high-level metrics overview, and quick action shortcuts.
 *
 * @returns JSX element rendering the entry dashboard view
 */
export default function BackofficeHomePage(): React.ReactElement {
  return (
    <div className="space-y-8">
      <section className="rounded-2xl border border-slate-800 bg-slate-900/90 p-8 shadow-xl">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs uppercase tracking-widest text-cyan-300 font-semibold">
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
            <span className="rounded-lg border border-slate-700 bg-slate-950 px-4 py-2 text-xs font-semibold text-cyan-300">
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
