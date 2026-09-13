import React from 'react';
import Link from 'next/link';
import { IncidentSummaryPanel } from '../../components/incidents/IncidentSummaryPanel';
import { IncidentListPanel } from '../../components/incidents/IncidentListPanel';

export const metadata = {
  title: 'Centralized Incident Manager | Backoffice',
  description: 'Manage, filter, and track operational incident reports and summary metrics.',
};

/**
 * Incident Management Dashboard Page.
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
        <IncidentSummaryPanel />

        {/* Incidents List Panel */}
        <IncidentListPanel />
      </div>
    </main>
  );
}
