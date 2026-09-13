'use client';

import React, { useEffect, useState } from 'react';
import type { IncidentSummaryMetrics } from '@repo/shared-types';
import { getIncidentSummary, IncidentApiError } from '../../lib/api/incidents';

export interface IncidentSummaryPanelProps {
  className?: string | undefined;
}

/**
 * Operational Summary Panel component displaying 4-dimension metric totals
 * (status, category, origin, branch) with localized loading and error boundaries.
 *
 * @param props - Component options including optional className.
 * @returns JSX Element rendering 4-dimension metric cards or localized error boundary.
 */
export const IncidentSummaryPanel: React.FC<IncidentSummaryPanelProps> = ({
  className = '',
}): React.ReactElement => {
  const [summary, setSummary] = useState<IncidentSummaryMetrics | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getIncidentSummary();
      setSummary(data);
    } catch (err: unknown) {
      if (err instanceof IncidentApiError) {
        setError(err.message);
      } else {
        setError('Failed to load summary metrics.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSummary();
  }, []);

  return (
    <div
      className={`bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-xl space-y-6 ${className}`}
    >
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Operational Metrics Summary</h2>
          <p className="text-sm text-slate-400 mt-0.5">
            Real-time incident aggregation across status, category, origin, and branch locations.
          </p>
        </div>

        {summary && (
          <div className="bg-emerald-950/40 border border-emerald-500/40 px-4 py-2 rounded-lg text-center">
            <div className="text-2xl font-extrabold text-emerald-400">
              {summary.total_incidents}
            </div>
            <div className="text-[10px] font-semibold text-emerald-300 uppercase tracking-wider">
              Total Incidents
            </div>
          </div>
        )}
      </div>

      {/* Loading Skeleton */}
      {isLoading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 animate-pulse">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 bg-slate-950/60 rounded-lg border border-slate-800 p-4" />
          ))}
        </div>
      )}

      {/* Localized Error Boundary */}
      {!isLoading && error && (
        <div className="p-4 rounded-lg bg-rose-950/30 border border-rose-500/30 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-lg">⚠️</span>
            <div>
              <p className="text-xs font-semibold text-rose-200">Unable to load summary metrics</p>
              <p className="text-[11px] text-rose-300">{error}</p>
            </div>
          </div>
          <button
            onClick={fetchSummary}
            className="text-xs font-semibold px-3 py-1.5 rounded-md bg-rose-600 hover:bg-rose-500 text-white transition-all"
          >
            Retry
          </button>
        </div>
      )}

      {/* Metric Cards Grid */}
      {!isLoading && !error && summary && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Status Metric Card */}
          <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-4 space-y-2">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-400" />
              By Status
            </h3>
            <div className="space-y-1.5 text-xs text-slate-300">
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Open:</span>
                <span className="font-bold text-amber-300">{summary.by_status.open ?? 0}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">In Progress:</span>
                <span className="font-bold text-blue-300">{summary.by_status.in_progress ?? 0}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Resolved:</span>
                <span className="font-bold text-emerald-400">{summary.by_status.resolved ?? 0}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Discarded:</span>
                <span className="font-bold text-slate-500">{summary.by_status.discarded ?? 0}</span>
              </div>
            </div>
          </div>

          {/* Category Metric Card */}
          <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-4 space-y-2">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-400" />
              By Category
            </h3>
            <div className="space-y-1.5 text-xs text-slate-300">
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Warehouse:</span>
                <span className="font-bold text-slate-100">{summary.by_category.warehouse ?? 0}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Reverse Logistics:</span>
                <span className="font-bold text-slate-100">{summary.by_category.reverse_logistics ?? 0}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Last Mile:</span>
                <span className="font-bold text-slate-100">{summary.by_category.last_mile ?? 0}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Customer Exp:</span>
                <span className="font-bold text-slate-100">{summary.by_category.customer_experience ?? 0}</span>
              </div>
            </div>
          </div>

          {/* Origin Metric Card */}
          <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-4 space-y-2">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400" />
              By Origin
            </h3>
            <div className="space-y-1.5 text-xs text-slate-300">
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Customer:</span>
                <span className="font-bold text-slate-100">{summary.by_origin.customer ?? 0}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Branch:</span>
                <span className="font-bold text-slate-100">{summary.by_origin.branch ?? 0}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-slate-400">Internal:</span>
                <span className="font-bold text-slate-100">{summary.by_origin.internal ?? 0}</span>
              </div>
            </div>
          </div>

          {/* Branch Top Locations */}
          <div className="bg-slate-950/70 border border-slate-800 rounded-lg p-4 space-y-2">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-purple-400" />
              Top Branches
            </h3>
            <div className="space-y-1.5 text-xs text-slate-300 max-h-24 overflow-y-auto">
              {Object.keys(summary.by_branch).length === 0 ? (
                <p className="text-[11px] text-slate-500 italic">No branch records</p>
              ) : (
                Object.entries(summary.by_branch).map(([branch, count]) => (
                  <div key={branch} className="flex justify-between items-center capitalize">
                    <span className="text-slate-400">{branch}:</span>
                    <span className="font-bold text-slate-100">{count}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
