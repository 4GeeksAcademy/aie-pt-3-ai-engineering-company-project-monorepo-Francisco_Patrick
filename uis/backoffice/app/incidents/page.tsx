import React from 'react';
import Link from 'next/link';
import dynamic from 'next/dynamic';

const DynamicIncidentSummaryPanel = dynamic(
  () =>
    import('../../components/incidents/IncidentSummaryPanel').then(
      (mod) => mod.IncidentSummaryPanel
    ),
  {
    loading: () => (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl space-y-6 animate-pulse">
        <div className="h-6 bg-slate-800 rounded w-1/4" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 bg-slate-950/60 rounded-lg border border-slate-800 p-4" />
          ))}
        </div>
      </div>
    ),
    ssr: false,
  }
);

const DynamicIncidentListPanel = dynamic(
  () =>
    import('../../components/incidents/IncidentListPanel').then(
      (mod) => mod.IncidentListPanel
    ),
  {
    loading: () => (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl space-y-6 animate-pulse">
        <div className="h-6 bg-slate-800 rounded w-1/4" />
        <div className="h-48 bg-slate-950/60 rounded-lg border border-slate-800" />
      </div>
    ),
    ssr: false,
  }
);

export const metadata = {
  title: 'Centralized Incident Manager | Backoffice',
  description: 'Manage, filter, and track operational incident reports and summary metrics.',
};

/**
 * Incident Management Dashboard Page with lazy-loaded summary metrics and list panels.
 *
 * @returns JSX Element rendering summary metrics and list panel components.
 */
export default function IncidentsPage(): React.ReactElement {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-4 sm:p-8">
      <div className="max-w-7xl mx-auto space-y-8">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Centralized Incident Manager
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Real-time operational dashboard for incident tracking, status updates, and metric summary.
            </p>
          </div>

          <Link
            href="/incidents/register"
            className="inline-flex items-center gap-2 text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-500 px-5 py-2.5 rounded-lg transition-all shadow-lg shadow-emerald-950/40 shrink-0"
          >
            <span>+</span> Register New Incident
          </Link>
        </div>

        {/* Summary Metrics Panel */}
        <DynamicIncidentSummaryPanel />

        {/* Incidents List Panel */}
        <DynamicIncidentListPanel />
      </div>
    </main>
  );
}
