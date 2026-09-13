'use client';

import React, { useEffect, useState, useCallback } from 'react';
import type {
  Incident,
  IncidentFilterOptions,
  IncidentStatus,
  IncidentOrigin,
} from '@repo/shared-types';
import { BRANCH_OPTIONS } from '@repo/shared-types';
import { listIncidents, updateIncidentStatus, IncidentApiError } from '../../lib/api/incidents';

export interface IncidentListPanelProps {
  className?: string | undefined;
}

const STATUS_OPTIONS: Array<{ value: string; label: string }> = [
  { value: '', label: 'All Statuses' },
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'discarded', label: 'Discarded' },
];

const ORIGIN_OPTIONS: Array<{ value: string; label: string }> = [
  { value: '', label: 'All Origins' },
  { value: 'customer', label: 'Customer' },
  { value: 'branch', label: 'Branch Location' },
  { value: 'internal', label: 'Internal Tool' },
];

/**
 * Resilient Incident List Panel component with multi-attribute filtering,
 * loading/empty/error states, and inline status updating with visual rollback.
 *
 * @param props - Component options including optional className.
 * @returns JSX Element rendering incident table or fallback states.
 */
export const IncidentListPanel: React.FC<IncidentListPanelProps> = ({
  className = '',
}): React.ReactElement => {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [filters, setFilters] = useState<IncidentFilterOptions>({
    status: '',
    origin: '',
    branch: '',
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<{
    type: 'success' | 'error';
    text: string;
  } | null>(null);

  const fetchIncidents = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listIncidents(filters);
      setIncidents(data);
    } catch (err: unknown) {
      if (err instanceof IncidentApiError) {
        setError(err.message);
      } else {
        setError('Failed to fetch incidents list. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    fetchIncidents();
  }, [fetchIncidents]);

  const handleFilterChange = (
    e: React.ChangeEvent<HTMLSelectElement | HTMLInputElement>
  ): void => {
    const { name, value } = e.target;
    setFilters((prev) => ({ ...prev, [name]: value }));
  };

  const handleStatusChange = async (
    incidentId: string,
    newStatus: IncidentStatus,
    previousStatus: IncidentStatus
  ): Promise<void> => {
    setUpdatingId(incidentId);
    setActionNotice(null);

    // Optimistic UI update
    setIncidents((prev) =>
      prev.map((inc) => (inc.id === incidentId ? { ...inc, status: newStatus } : inc))
    );

    try {
      const updated = await updateIncidentStatus(incidentId, newStatus);
      setIncidents((prev) =>
        prev.map((inc) => (inc.id === incidentId ? updated : inc))
      );
      setActionNotice({
        type: 'success',
        text: `Incident ${incidentId} status updated to "${newStatus}".`,
      });
    } catch (err: unknown) {
      // Revert visual state on error
      setIncidents((prev) =>
        prev.map((inc) => (inc.id === incidentId ? { ...inc, status: previousStatus } : inc))
      );

      const errorMessage =
        err instanceof IncidentApiError
          ? err.message
          : 'Status update failed. Reverting to previous state.';

      setActionNotice({
        type: 'error',
        text: `Failed to update status for ${incidentId}: ${errorMessage}`,
      });
    } finally {
      setUpdatingId(null);
    }
  };

  const clearFilters = (): void => {
    setFilters({ status: '', origin: '', branch: '' });
  };

  return (
    <div
      className={`bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl space-y-6 ${className}`}
    >
      {/* Header & Controls */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Registered Incidents</h2>
          <p className="text-sm text-slate-400 mt-0.5">
            View, filter, and manage operational incident records.
          </p>
        </div>

        {/* Filter Controls */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* Status Filter */}
          <select
            name="status"
            value={filters.status || ''}
            onChange={handleFilterChange}
            className="px-3 py-2 rounded-lg text-xs bg-slate-950 text-slate-200 border border-slate-700 focus:ring-2 focus:ring-emerald-500/50 focus:outline-none"
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          {/* Origin Filter */}
          <select
            name="origin"
            value={filters.origin || ''}
            onChange={handleFilterChange}
            className="px-3 py-2 rounded-lg text-xs bg-slate-950 text-slate-200 border border-slate-700 focus:ring-2 focus:ring-emerald-500/50 focus:outline-none"
          >
            {ORIGIN_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          {/* Branch Filter */}
          <select
            name="branch"
            value={filters.branch || ''}
            onChange={handleFilterChange}
            className="px-3 py-2 rounded-lg text-xs bg-slate-950 text-slate-200 border border-slate-700 focus:ring-2 focus:ring-emerald-500/50 focus:outline-none"
          >
            <option value="">All Branches</option>
            {BRANCH_OPTIONS.map((b) => (
              <option key={b.value} value={b.value}>
                {b.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Action Notice Alert */}
      {actionNotice && (
        <div
          className={`p-3.5 rounded-lg text-xs font-medium flex items-center justify-between transition-all ${
            actionNotice.type === 'success'
              ? 'bg-emerald-950/40 border border-emerald-500/40 text-emerald-300'
              : 'bg-rose-950/40 border border-rose-500/40 text-rose-300'
          }`}
        >
          <span>{actionNotice.text}</span>
          <button
            onClick={() => setActionNotice(null)}
            className="ml-2 text-slate-400 hover:text-slate-200"
          >
            ✕
          </button>
        </div>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="py-12 flex flex-col items-center justify-center text-slate-400 gap-3">
          <svg className="animate-spin h-7 w-7 text-emerald-500" fill="none" viewBox="0 0 24 24">
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          <p className="text-xs font-medium">Loading operational incidents...</p>
        </div>
      )}

      {/* Error State with Retry Button */}
      {!isLoading && error && (
        <div className="p-6 rounded-xl bg-rose-950/20 border border-rose-500/30 text-center space-y-4">
          <svg
            className="w-10 h-10 text-rose-400 mx-auto"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M12 9v3m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
          <div>
            <h3 className="text-sm font-bold text-rose-200">Failed to Load Incidents</h3>
            <p className="text-xs text-rose-300 mt-1 max-w-md mx-auto">{error}</p>
          </div>
          <button
            onClick={() => fetchIncidents()}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-rose-600 hover:bg-rose-500 text-white transition-all shadow-md shadow-rose-950/50"
          >
            🔄 Retry Loading
          </button>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && !error && incidents.length === 0 && (
        <div className="py-12 px-4 rounded-xl border border-dashed border-slate-800 bg-slate-950/50 text-center space-y-3">
          <div className="w-12 h-12 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center mx-auto text-slate-500">
            📋
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-200">No Incidents Found</h3>
            <p className="text-xs text-slate-400 mt-1 max-w-sm mx-auto">
              {filters.status || filters.origin || filters.branch
                ? 'No recorded incidents match your current filter parameters.'
                : 'No operational incidents have been registered in the database yet.'}
            </p>
          </div>
          {(filters.status || filters.origin || filters.branch) && (
            <button
              onClick={clearFilters}
              className="text-xs font-semibold text-emerald-400 hover:text-emerald-300 underline"
            >
              Clear Filters
            </button>
          )}
        </div>
      )}

      {/* Incident Data Table */}
      {!isLoading && !error && incidents.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-slate-800">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-950 text-slate-400 font-semibold border-b border-slate-800 uppercase tracking-wider">
              <tr>
                <th className="p-3.5">ID / Date</th>
                <th className="p-3.5">Incident Title</th>
                <th className="p-3.5">Category</th>
                <th className="p-3.5">Origin / Branch</th>
                <th className="p-3.5">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-900">
              {incidents.map((incident) => {
                const isUpdatingThis = updatingId === incident.id;
                return (
                  <tr
                    key={incident.id}
                    className="hover:bg-slate-850 transition-colors"
                  >
                    <td className="p-3.5 font-mono text-slate-400 whitespace-nowrap">
                      <div className="font-semibold text-slate-200">{incident.id}</div>
                      <div className="text-[10px] text-slate-500 mt-0.5">
                        {incident.created_at
                          ? new Date(incident.created_at).toLocaleDateString()
                          : 'N/A'}
                      </div>
                    </td>

                    <td className="p-3.5">
                      <div className="font-semibold text-white">{incident.title}</div>
                      <div className="text-slate-400 line-clamp-1 mt-0.5 max-w-xs">
                        {incident.description}
                      </div>
                    </td>

                    <td className="p-3.5 whitespace-nowrap">
                      <span className="inline-block px-2.5 py-1 rounded-md text-[11px] font-medium bg-slate-800 text-slate-300 border border-slate-700 capitalize">
                        {incident.category.replace('_', ' ')}
                      </span>
                    </td>

                    <td className="p-3.5 whitespace-nowrap">
                      <div className="font-medium text-slate-200 capitalize">
                        {incident.branch}
                      </div>
                      <div className="text-[10px] text-slate-400 mt-0.5 capitalize">
                        Origin: {incident.origin}
                      </div>
                    </td>

                    <td className="p-3.5 whitespace-nowrap">
                      <div className="flex items-center gap-2">
                        <select
                          value={incident.status}
                          disabled={isUpdatingThis}
                          onChange={(e) =>
                            handleStatusChange(
                              incident.id,
                              e.target.value as IncidentStatus,
                              incident.status
                            )
                          }
                          className={`px-2.5 py-1.5 rounded-md text-xs font-semibold border transition-all focus:outline-none disabled:opacity-50 cursor-pointer ${
                            incident.status === 'open'
                              ? 'bg-amber-950/30 text-amber-300 border-amber-500/40'
                              : incident.status === 'in_progress'
                                ? 'bg-blue-950/30 text-blue-300 border-blue-500/40'
                                : incident.status === 'resolved'
                                  ? 'bg-emerald-950/30 text-emerald-300 border-emerald-500/40'
                                  : 'bg-slate-800 text-slate-400 border-slate-700'
                          }`}
                        >
                          <option value="open">open</option>
                          <option value="in_progress">in_progress</option>
                          <option value="resolved">resolved</option>
                          <option value="discarded">discarded</option>
                        </select>
                        {isUpdatingThis && (
                          <svg
                            className="animate-spin h-3.5 w-3.5 text-emerald-400"
                            fill="none"
                            viewBox="0 0 24 24"
                          >
                            <circle
                              className="opacity-25"
                              cx="12"
                              cy="12"
                              r="10"
                              stroke="currentColor"
                              strokeWidth="4"
                            />
                            <path
                              className="opacity-75"
                              fill="currentColor"
                              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                            />
                          </svg>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
