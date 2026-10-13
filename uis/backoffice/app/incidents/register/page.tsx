import React from 'react';
import Link from 'next/link';
import { IncidentRegistrationForm } from '../../../components/incidents/IncidentRegistrationForm';

export const metadata = {
  title: 'Register Incident | Backoffice',
  description: 'Incident registration form for operational issues and customer reports.',
};

/**
 * Incident Registration Page.
 *
 * @returns JSX Element rendering the incident registration page view.
 */
export default function RegisterIncidentPage(): React.ReactElement {
  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 p-4 sm:p-8">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Navigation Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Link href="/incidents" className="hover:text-slate-200 transition-colors">
            Incidents
          </Link>
          <span>/</span>
          <span className="text-slate-200 font-medium">New Incident</span>
        </div>

        {/* Page Title */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              New Operational Incident
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Submit an operational incident report into the central management system.
            </p>
          </div>

          <Link
            href="/incidents"
            className="inline-flex items-center text-sm font-medium text-slate-300 hover:text-white bg-slate-900 border border-slate-800 px-4 py-2 rounded-lg hover:bg-slate-800 transition-all"
          >
            ← Back to Incidents List
          </Link>
        </div>

        {/* Registration Form Component */}
        <IncidentRegistrationForm className="mt-4" />
      </div>
    </main>
  );
}
