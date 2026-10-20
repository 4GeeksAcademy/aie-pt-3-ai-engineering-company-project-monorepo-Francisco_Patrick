'use client';

import React, { useCallback, useEffect, useState } from 'react';
import type { TelemetryReportResponse } from '@repo/shared-types';
import EventVolumeChart from '../../components/telemetry/EventVolumeChart';
import ErrorDistribution from '../../components/telemetry/ErrorDistribution';
import AuthFailureCard from '../../components/telemetry/AuthFailureCard';
import { fetchWithAuth } from '../../lib/api';

/**
 * Engineering Operational Telemetry Dashboard Page.
 *
 * Provides real-time and historical operational health metrics including
 * daily event volume, error category distribution, and authentication reliability.
 *
 * @returns React.ReactElement rendering the operational telemetry dashboard.
 */
export default function TelemetryDashboardPage(): React.ReactElement {
  const [report, setReport] = useState<TelemetryReportResponse | null>(null);
  const [cacheStatus, setCacheStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  const loadReport = useCallback(
    async (start?: string, end?: string): Promise<void> => {
      setLoading(true);
      setError(null);

      const queryParts: string[] = [];
      if (start) {
        queryParts.push(`start_date=${encodeURIComponent(start)}`);
      }
      if (end) {
        queryParts.push(`end_date=${encodeURIComponent(end)}`);
      }
      const queryString = queryParts.length > 0 ? `?${queryParts.join('&')}` : '';

      try {
        const response = await fetchWithAuth(`/telemetry/report${queryString}`, {
          method: 'GET',
          headers: {
            Accept: 'application/json',
          },
        });

        if (!response.ok) {
          let errorMsg = `HTTP Error ${response.status}: Failed to retrieve telemetry report`;
          try {
            const errData = (await response.json()) as { detail?: string };
            if (errData.detail) {
              errorMsg = errData.detail;
            }
          } catch {
            // Non-JSON error body
          }
          throw new Error(errorMsg);
        }

        const xCache = response.headers.get('X-Cache');
        if (xCache) {
          setCacheStatus(xCache);
        }

        const data = (await response.json()) as TelemetryReportResponse;
        setReport(data);
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'An unexpected error occurred while loading telemetry';
        setError(message);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    void loadReport();
  }, [loadReport]);

  const handleApplyFilter = (e: React.FormEvent): void => {
    e.preventDefault();
    void loadReport(startDate || undefined, endDate || undefined);
  };

  const handleResetFilter = (): void => {
    setStartDate('');
    setEndDate('');
    void loadReport();
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 sm:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header section */}
      <section className="relative overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/90 p-6 sm:p-8 shadow-2xl backdrop-blur-xl">
        <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 -left-24 h-72 w-72 rounded-full bg-emerald-500/10 blur-3xl" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-400 animate-pulse" />
              <p className="text-xs uppercase tracking-widest text-cyan-400 font-semibold">
                Operational Observability
              </p>
            </div>
            <h1 className="mt-1 text-2xl font-bold text-slate-100 sm:text-3xl tracking-tight">
              Telemetry &amp; Operational Health
            </h1>
            <p className="mt-1.5 max-w-2xl text-xs sm:text-sm text-slate-400 leading-relaxed">
              Consolidated system performance, error distributions, and authentication reliability metrics.
            </p>
          </div>

          {/* Active Period Display & Cache Indicator */}
          {report && (
            <div className="flex flex-col sm:items-end gap-1.5 self-start md:self-center">
              <div className="flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-950/80 px-3.5 py-2 text-xs">
                <span className="text-slate-400">Reporting Window:</span>
                <span className="font-mono text-emerald-400 font-medium">
                  {report.period.from}
                </span>
                <span className="text-slate-500">to</span>
                <span className="font-mono text-emerald-400 font-medium">
                  {report.period.to}
                </span>
              </div>
              {cacheStatus && (
                <div className="flex items-center gap-2 text-[11px] text-slate-400">
                  <span>Cache Status:</span>
                  <span
                    className={`font-semibold px-1.5 py-0.5 rounded text-[10px] ${
                      cacheStatus === 'HIT'
                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-800/60'
                        : 'bg-slate-800 text-slate-300 border border-slate-700/60'
                    }`}
                  >
                    {cacheStatus}
                  </span>
                  <span className="text-slate-500">(60s TTL)</span>
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Filter and Period Controls */}
      <section className="rounded-xl border border-slate-800/80 bg-slate-900/60 p-4">
        <form onSubmit={handleApplyFilter} className="flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2">
            <label htmlFor="telemetry-start-date" className="text-xs text-slate-400 font-medium">
              Start Date:
            </label>
            <input
              id="telemetry-start-date"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-200 focus:border-emerald-500 focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-2">
            <label htmlFor="telemetry-end-date" className="text-xs text-slate-400 font-medium">
              End Date:
            </label>
            <input
              id="telemetry-end-date"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-slate-200 focus:border-emerald-500 focus:outline-none"
            />
          </div>

          <div className="flex items-center gap-2 ml-auto">
            <button
              type="submit"
              disabled={loading}
              className="rounded-lg bg-emerald-600 hover:bg-emerald-500 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors disabled:opacity-50"
            >
              Filter Period
            </button>
            <button
              type="button"
              onClick={handleResetFilter}
              disabled={loading}
              className="rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 px-3.5 py-1.5 text-xs font-semibold text-slate-300 transition-colors disabled:opacity-50"
            >
              Reset (Default 7-Day)
            </button>
            <button
              type="button"
              onClick={() => void loadReport(startDate || undefined, endDate || undefined)}
              disabled={loading}
              className="rounded-lg border border-slate-700 bg-slate-800 hover:bg-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-300 transition-colors disabled:opacity-50"
              title="Refresh telemetry"
            >
              ↻ Refresh
            </button>
          </div>
        </form>
      </section>

      {/* Error state */}
      {error && (
        <div
          role="alert"
          className="rounded-xl border border-rose-900/60 bg-rose-950/30 p-6 text-rose-200 shadow-xl"
        >
          <div className="flex items-start justify-between gap-4">
            <div>
              <h3 className="text-sm font-bold text-rose-400">Failed to Load Telemetry Report</h3>
              <p className="mt-1 text-xs text-rose-300/80 leading-relaxed">{error}</p>
            </div>
            <button
              type="button"
              data-testid="retry-telemetry-btn"
              onClick={() => void loadReport(startDate || undefined, endDate || undefined)}
              className="rounded-lg bg-rose-600 hover:bg-rose-500 px-4 py-2 text-xs font-semibold text-white transition-colors"
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {/* Loading skeleton */}
      {loading && !report && (
        <div className="space-y-6 animate-pulse">
          <div className="h-64 rounded-xl bg-slate-900/60 border border-slate-800" />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="h-64 rounded-xl bg-slate-900/60 border border-slate-800" />
            <div className="h-64 rounded-xl bg-slate-900/60 border border-slate-800" />
          </div>
        </div>
      )}

      {/* Report Metrics Grid */}
      {report && (
        <div className="space-y-6">
          {/* Daily Event Volume */}
          <EventVolumeChart data={report.metrics.events_per_day} />

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Operational Error Distribution */}
            <ErrorDistribution data={report.metrics.error_rate_by_type} />

            {/* Authentication Flow Reliability */}
            <AuthFailureCard data={report.metrics.auth_failure_rate} />
          </div>
        </div>
      )}
    </div>
  );
}
