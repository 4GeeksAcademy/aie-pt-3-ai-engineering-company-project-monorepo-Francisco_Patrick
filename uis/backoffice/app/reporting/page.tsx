'use client';

import React, { useCallback, useEffect, useState } from 'react';
import type {
  ExecutiveKpiSnapshot,
  ExecutiveKpisResponse,
  PipelineStatusResponse,
  ReportingGeographicScope,
} from '@repo/shared-types';
import { fetchExecutiveKpis, fetchPipelineStatus } from '../../lib/reportingApi';

/**
 * Format ISO UTC date string into executive-readable date string.
 *
 * @param isoDateString - ISO 8601 UTC date timestamp string.
 * @returns Human-readable date string formatted as 'MMM DD, YYYY'.
 */
function formatDate(isoDateString?: string): string {
  if (!isoDateString) {
    return 'N/A';
  }
  try {
    const d = new Date(isoDateString);
    if (isNaN(d.getTime())) {
      return isoDateString;
    }
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      timeZone: 'UTC',
    });
  } catch {
    return isoDateString;
  }
}

/**
 * Format currency number into European Euro display (EUR).
 *
 * @param amount - Numeric value in Euros.
 * @returns Formatted currency string (e.g. '€12,345.67').
 */
function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('de-DE', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

/**
 * Format percentage value.
 *
 * @param rate - Fractional value (0.0 to 1.0) or percentage value (0 to 100).
 * @param isFraction - True if value is fractional 0.0-1.0; false if already 0-100.
 * @returns Formatted percentage string (e.g. '95.4%').
 */
function formatPercentage(rate: number, isFraction: boolean = false): string {
  const percentage = isFraction ? rate * 100 : rate;
  return `${percentage.toFixed(1)}%`;
}

/**
 * Loading skeleton component matching executive metric card geometries.
 *
 * @returns React.ReactElement rendering skeleton layout to prevent CLS.
 */
function ReportingSkeleton(): React.ReactElement {
  return (
    <div className="space-y-6" id="reporting-skeleton">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
        {[1, 2, 3, 4, 5].map((idx) => (
          <div
            key={idx}
            className="rounded-2xl border border-slate-800/80 bg-slate-900/60 p-6 shadow-xl animate-pulse space-y-4"
          >
            <div className="flex justify-between items-center">
              <div className="h-4 w-28 bg-slate-800 rounded" />
              <div className="h-5 w-14 bg-slate-800 rounded-full" />
            </div>
            <div className="h-9 w-32 bg-slate-800 rounded" />
            <div className="h-3 w-40 bg-slate-800 rounded" />
            <div className="pt-2 border-t border-slate-800/50">
              <div className="h-3 w-24 bg-slate-800/80 rounded" />
            </div>
          </div>
        ))}
      </div>
      <div className="rounded-2xl border border-slate-800/80 bg-slate-900/60 p-6 shadow-xl animate-pulse space-y-3">
        <div className="h-5 w-48 bg-slate-800 rounded" />
        <div className="h-4 w-full bg-slate-800/60 rounded" />
      </div>
    </div>
  );
}

/**
 * Executive Reporting Dashboard Page.
 *
 * Renders weekly business performance metrics calculated across dual fulfillment
 * facilities (Los Angeles and Zaragoza) and consolidated globally.
 *
 * @returns React.ReactElement rendering the executive dashboard.
 */
export default function ReportingDashboardPage(): React.ReactElement {
  const [selectedHub, setSelectedHub] = useState<ReportingGeographicScope>('GLOBAL');
  const [kpisResponse, setKpisResponse] = useState<ExecutiveKpisResponse | null>(null);
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async (scope: ReportingGeographicScope): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      const [kpiData, statusData] = await Promise.all([
        fetchExecutiveKpis({ country: scope }),
        fetchPipelineStatus().catch(() => null),
      ]);
      setKpisResponse(kpiData);
      if (statusData) {
        setPipelineStatus(statusData);
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error
          ? err.message
          : 'An unexpected error occurred while loading executive KPIs.';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData(selectedHub);
  }, [selectedHub, loadData]);

  const handleHubSelect = (hub: ReportingGeographicScope): void => {
    setSelectedHub(hub);
  };

  const handleRetry = (): void => {
    void loadData(selectedHub);
  };

  // Find active snapshot matching selected geographic hub scope
  const activeSnapshot: ExecutiveKpiSnapshot | undefined =
    kpisResponse?.snapshots.find((s) => s.country === selectedHub) ??
    kpisResponse?.snapshots[0];

  // Derive unit economics cost per shipment
  const costPerShipment =
    activeSnapshot && activeSnapshot.shipments_volume > 0
      ? activeSnapshot.operational_cost_eur / activeSnapshot.shipments_volume
      : 0;

  const isOnTimeTargetMet = (activeSnapshot?.on_time_delivery_rate ?? 0) >= 0.95;
  const isCsatTargetMet = (activeSnapshot?.customer_satisfaction_score ?? 0) >= 90.0;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 sm:p-8 max-w-7xl mx-auto space-y-8">
      {/* Executive Header Section */}
      <section className="relative overflow-hidden rounded-3xl border border-slate-800 bg-slate-900/90 p-6 sm:p-8 shadow-2xl backdrop-blur-xl">
        <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-emerald-500/10 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 -left-24 h-72 w-72 rounded-full bg-cyan-500/10 blur-3xl" />

        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-3">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                Executive Briefing
              </span>
              {activeSnapshot && (
                <span
                  id="reporting-period-badge"
                  className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700"
                >
                  Period: {formatDate(activeSnapshot.period_start)} – {formatDate(activeSnapshot.period_end)} (UTC)
                </span>
              )}
            </div>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
              Executive Performance Dashboard
            </h1>
            <p className="text-sm sm:text-base text-slate-400 max-w-2xl">
              Consolidated weekly operational performance, carrier SLA compliance, and logistics unit
              economics across TrackFlow fulfillment hubs.
            </p>
          </div>

          {/* Hub Scope Selector & Actions */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <div
              className="inline-flex rounded-xl bg-slate-950/80 p-1 border border-slate-800 shadow-inner"
              role="group"
              aria-label="Geographic hub scope selector"
            >
              {(['GLOBAL', 'US', 'ES'] as const).map((hub) => (
                <button
                  key={hub}
                  id={`hub-selector-${hub.toLowerCase()}`}
                  onClick={() => handleHubSelect(hub)}
                  className={`px-4 py-2 text-xs sm:text-sm font-semibold rounded-lg transition-all ${
                    selectedHub === hub
                      ? 'bg-emerald-500 text-slate-950 shadow-md font-bold'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                  }`}
                  aria-pressed={selectedHub === hub}
                >
                  {hub === 'GLOBAL' ? 'Global Consolidation' : hub === 'US' ? 'US Hub (LAX)' : 'ES Hub (ZAZ)'}
                </button>
              ))}
            </div>

            <button
              id="refresh-kpis-btn"
              onClick={handleRetry}
              disabled={loading}
              className="px-4 py-2 text-xs sm:text-sm font-semibold rounded-xl bg-slate-800 text-slate-200 border border-slate-700 hover:bg-slate-700 hover:text-white transition-all disabled:opacity-50"
              title="Refresh performance KPIs"
            >
              {loading ? 'Refreshing...' : '↻ Refresh'}
            </button>
          </div>
        </div>

        {/* Pipeline Execution Status Mini-Bar */}
        {pipelineStatus && pipelineStatus.latest_run && (
          <div className="mt-6 pt-4 border-t border-slate-800/80 flex flex-wrap items-center justify-between text-xs text-slate-400 gap-2">
            <div className="flex items-center gap-2">
              <span className="font-medium text-slate-300">Pipeline Status:</span>
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold ${
                  pipelineStatus.latest_run.status === 'SUCCESS'
                    ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/50'
                    : pipelineStatus.latest_run.status === 'RUNNING'
                    ? 'bg-cyan-950 text-cyan-400 border border-cyan-800/50 animate-pulse'
                    : 'bg-rose-950 text-rose-400 border border-rose-800/50'
                }`}
              >
                {pipelineStatus.latest_run.status}
              </span>
              <span>• Last run: {formatDate(pipelineStatus.latest_run.started_at)}</span>
            </div>
            <div>
              <span>Extracted & Processed: {pipelineStatus.latest_run.records_processed.toLocaleString()} events</span>
            </div>
          </div>
        )}
      </section>

      {/* Accessible Error Banner with Retry */}
      {error && (
        <section
          role="alert"
          id="reporting-error-banner"
          aria-live="assertive"
          className="rounded-2xl border border-rose-800/50 bg-rose-950/60 p-6 text-rose-200 shadow-xl backdrop-blur-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4"
        >
          <div className="flex items-start gap-3">
            <span className="text-2xl" aria-hidden="true">
              ⚠️
            </span>
            <div>
              <h2 className="text-base font-bold text-rose-100">Unable to Load Executive KPIs</h2>
              <p className="text-xs sm:text-sm text-rose-300/90 mt-1">{error}</p>
            </div>
          </div>
          <button
            id="retry-fetch-btn"
            onClick={handleRetry}
            className="self-start sm:self-center px-4 py-2 rounded-xl text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white shadow transition-all focus:outline-none focus:ring-2 focus:ring-rose-400"
          >
            Retry Fetch
          </button>
        </section>
      )}

      {/* Main KPI Cards Section */}
      {loading ? (
        <ReportingSkeleton />
      ) : kpisResponse && activeSnapshot ? (
        <section className="space-y-6" id="kpi-cards-grid">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-6">
            {/* Card 1: Shipments Volume */}
            <div className="relative overflow-hidden rounded-2xl border border-slate-800/90 bg-gradient-to-br from-slate-900 to-slate-900/60 p-6 shadow-xl hover:border-slate-700 transition-all">
              <div className="flex justify-between items-start">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Shipments Volume
                </span>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-cyan-950 text-cyan-400 border border-cyan-800/50">
                  Fulfilled
                </span>
              </div>
              <div className="mt-4">
                <div
                  id="kpi-shipments-volume"
                  className="text-3xl font-extrabold text-white tracking-tight"
                >
                  {activeSnapshot.shipments_volume.toLocaleString()}
                </div>
                <p className="mt-1 text-xs text-slate-400">Outbound packages dispatched</p>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-800/80 text-[11px] text-slate-400 flex items-center justify-between">
                <span>Facility Scope:</span>
                <span className="font-semibold text-slate-300">{activeSnapshot.country}</span>
              </div>
            </div>

            {/* Card 2: Global On-Time Delivery Rate */}
            <div className="relative overflow-hidden rounded-2xl border border-slate-800/90 bg-gradient-to-br from-slate-900 to-slate-900/60 p-6 shadow-xl hover:border-slate-700 transition-all">
              <div className="flex justify-between items-start">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  On-Time Delivery Rate
                </span>
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold ${
                    isOnTimeTargetMet
                      ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/50'
                      : 'bg-rose-950 text-rose-400 border border-rose-800/50'
                  }`}
                >
                  {isOnTimeTargetMet ? 'SLA Met (≥95%)' : 'Below SLA (<95%)'}
                </span>
              </div>
              <div className="mt-4">
                <div
                  id="kpi-on-time-rate"
                  className="text-3xl font-extrabold text-white tracking-tight"
                >
                  {formatPercentage(activeSnapshot.on_time_delivery_rate, true)}
                </div>
                <p className="mt-1 text-xs text-slate-400">Transit within promised SLA</p>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-800/80 text-[11px] text-slate-400 flex items-center justify-between">
                <span>Carrier Compliance:</span>
                <span
                  className={`font-semibold ${
                    isOnTimeTargetMet ? 'text-emerald-400' : 'text-rose-400'
                  }`}
                >
                  {isOnTimeTargetMet ? 'Healthy' : 'Needs Review'}
                </span>
              </div>
            </div>

            {/* Card 3: Operational Cost (EUR) */}
            <div className="relative overflow-hidden rounded-2xl border border-slate-800/90 bg-gradient-to-br from-slate-900 to-slate-900/60 p-6 shadow-xl hover:border-slate-700 transition-all">
              <div className="flex justify-between items-start">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Operational Cost
                </span>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-indigo-950 text-indigo-400 border border-indigo-800/50">
                  EUR
                </span>
              </div>
              <div className="mt-4">
                <div
                  id="kpi-operational-cost"
                  className="text-3xl font-extrabold text-white tracking-tight"
                >
                  {formatCurrency(activeSnapshot.operational_cost_eur)}
                </div>
                <p className="mt-1 text-xs text-slate-400">Logistics & fulfillment spend</p>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-800/80 text-[11px] text-slate-400 flex items-center justify-between">
                <span>Cost / Shipment:</span>
                <span className="font-semibold text-slate-300">
                  {formatCurrency(costPerShipment)} / pkg
                </span>
              </div>
            </div>

            {/* Card 4: Returns Rate */}
            <div className="relative overflow-hidden rounded-2xl border border-slate-800/90 bg-gradient-to-br from-slate-900 to-slate-900/60 p-6 shadow-xl hover:border-slate-700 transition-all">
              <div className="flex justify-between items-start">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Returns Rate
                </span>
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-medium bg-amber-950 text-amber-400 border border-amber-800/50">
                  Reverse Logistics
                </span>
              </div>
              <div className="mt-4">
                <div
                  id="kpi-returns-rate"
                  className="text-3xl font-extrabold text-white tracking-tight"
                >
                  {formatPercentage(activeSnapshot.returns_rate, false)}
                </div>
                <p className="mt-1 text-xs text-slate-400">Total shipments returned</p>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-800/80 text-[11px] text-slate-400 flex items-center justify-between">
                <span>Benchmark:</span>
                <span className="font-semibold text-slate-300">Target &lt; 5.0%</span>
              </div>
            </div>

            {/* Card 5: Customer Satisfaction Score */}
            <div className="relative overflow-hidden rounded-2xl border border-slate-800/90 bg-gradient-to-br from-slate-900 to-slate-900/60 p-6 shadow-xl hover:border-slate-700 transition-all">
              <div className="flex justify-between items-start">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Customer Satisfaction
                </span>
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold ${
                    isCsatTargetMet
                      ? 'bg-emerald-950 text-emerald-400 border border-emerald-800/50'
                      : 'bg-amber-950 text-amber-400 border border-amber-800/50'
                  }`}
                >
                  CSAT (0-100)
                </span>
              </div>
              <div className="mt-4">
                <div
                  id="kpi-csat-score"
                  className="text-3xl font-extrabold text-white tracking-tight"
                >
                  {activeSnapshot.customer_satisfaction_score.toFixed(1)}
                  <span className="text-sm font-normal text-slate-400">/100</span>
                </div>
                <p className="mt-1 text-xs text-slate-400">Resolved inquiry ratings</p>
              </div>
              <div className="mt-4 pt-3 border-t border-slate-800/80 text-[11px] text-slate-400 flex items-center justify-between">
                <span>Executive Target:</span>
                <span
                  className={`font-semibold ${
                    isCsatTargetMet ? 'text-emerald-400' : 'text-amber-400'
                  }`}
                >
                  ≥ 90.0 CSAT
                </span>
              </div>
            </div>
          </div>

          {/* Regional Hub Comparison Table */}
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 shadow-xl backdrop-blur-md space-y-4">
            <h2 className="text-base sm:text-lg font-bold text-white flex items-center gap-2">
              <span>📊</span>
              <span>Hub Operational Performance Breakdown</span>
            </h2>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-800 text-left text-xs sm:text-sm">
                <thead>
                  <tr className="text-slate-400 font-semibold">
                    <th scope="col" className="py-3 px-4">Hub Scope</th>
                    <th scope="col" className="py-3 px-4">Shipments</th>
                    <th scope="col" className="py-3 px-4">On-Time Rate</th>
                    <th scope="col" className="py-3 px-4">Operational Cost</th>
                    <th scope="col" className="py-3 px-4">Cost / Pkg</th>
                    <th scope="col" className="py-3 px-4">Returns Rate</th>
                    <th scope="col" className="py-3 px-4">CSAT Score</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 text-slate-300">
                  {kpisResponse.snapshots.map((snap) => {
                    const snapUnitCost =
                      snap.shipments_volume > 0 ? snap.operational_cost_eur / snap.shipments_volume : 0;
                    const isSelected = snap.country === selectedHub;
                    return (
                      <tr
                        key={snap.snapshot_id}
                        onClick={() => handleHubSelect(snap.country)}
                        className={`cursor-pointer transition-colors ${
                          isSelected
                            ? 'bg-emerald-950/40 font-semibold text-white'
                            : 'hover:bg-slate-800/40'
                        }`}
                      >
                        <td className="py-3 px-4 flex items-center gap-2">
                          <span
                            className={`h-2 w-2 rounded-full ${
                              isSelected ? 'bg-emerald-400' : 'bg-slate-600'
                            }`}
                          />
                          {snap.country === 'GLOBAL'
                            ? 'GLOBAL (Consolidated)'
                            : snap.country === 'US'
                            ? 'US-LAX-01 (Los Angeles)'
                            : 'ES-ZAZ-01 (Zaragoza)'}
                        </td>
                        <td className="py-3 px-4">{snap.shipments_volume.toLocaleString()}</td>
                        <td className="py-3 px-4">
                          <span
                            className={
                              snap.on_time_delivery_rate >= 0.95
                                ? 'text-emerald-400 font-semibold'
                                : 'text-rose-400 font-semibold'
                            }
                          >
                            {formatPercentage(snap.on_time_delivery_rate, true)}
                          </span>
                        </td>
                        <td className="py-3 px-4">{formatCurrency(snap.operational_cost_eur)}</td>
                        <td className="py-3 px-4">{formatCurrency(snapUnitCost)}</td>
                        <td className="py-3 px-4">{formatPercentage(snap.returns_rate, false)}</td>
                        <td className="py-3 px-4">
                          <span
                            className={
                              snap.customer_satisfaction_score >= 90
                                ? 'text-emerald-400 font-semibold'
                                : 'text-amber-400 font-semibold'
                            }
                          >
                            {snap.customer_satisfaction_score.toFixed(1)}/100
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      ) : (
        <section
          id="no-kpi-data-notice"
          className="rounded-2xl border border-slate-800 bg-slate-900/60 p-8 text-center text-slate-400 space-y-3"
        >
          <div className="text-3xl">📭</div>
          <h2 className="text-base font-semibold text-slate-200">No KPI Snapshots Available</h2>
          <p className="text-xs sm:text-sm max-w-md mx-auto">
            No pre-computed executive KPI snapshots were found for the selected parameters. Trigger the
            data pipeline or check back after the scheduled weekly execution.
          </p>
        </section>
      )}
    </div>
  );
}
