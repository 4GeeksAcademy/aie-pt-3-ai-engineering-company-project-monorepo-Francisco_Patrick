import React from 'react';
import type { ErrorDistributionMetric } from '@repo/shared-types';

export interface ErrorDistributionProps {
  /** Array of categorical error distribution metrics. */
  readonly data: readonly ErrorDistributionMetric[];
}

/**
 * Renders an accessible table and progress bar visualizer for operational error taxonomy distributions.
 *
 * @param props - Component properties containing the error metrics array.
 * @returns React.ReactElement rendering the error distribution breakdown or nominal zero-error state.
 */
export default function ErrorDistribution(props: ErrorDistributionProps): React.ReactElement {
  const { data } = props;

  if (data.length === 0) {
    return (
      <section
        className="rounded-xl border border-slate-800 bg-slate-900/80 p-6 shadow-xl backdrop-blur-sm"
        role="region"
        aria-label="Operational Error Distribution"
      >
        <div className="flex items-center gap-2 mb-4">
          <span className="h-2 w-2 rounded-full bg-emerald-400" />
          <h3 className="text-base font-semibold text-slate-100">Operational Error Distribution</h3>
        </div>
        <div className="rounded-lg border border-emerald-900/40 bg-emerald-950/20 p-6 text-center">
          <p className="text-sm font-semibold text-emerald-300">Zero Operational Errors</p>
          <p className="mt-1 text-xs text-slate-400">
            No errors detected during the reporting window. All monitored subsystems are operating nominally.
          </p>
        </div>
      </section>
    );
  }

  const totalErrors = data.reduce((acc, item) => acc + item.count, 0);

  return (
    <section
      className="rounded-xl border border-slate-800 bg-slate-900/80 p-6 shadow-xl backdrop-blur-sm"
      role="region"
      aria-label="Operational Error Distribution"
    >
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-6">
        <div>
          <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-rose-400" />
            Operational Error Distribution
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Breakdown of system exceptions, failures, and threshold triggers by taxonomy type
          </p>
        </div>
        <div className="bg-slate-800/80 border border-slate-700/60 rounded-lg px-3 py-1.5 self-start sm:self-auto">
          <span className="text-xs text-slate-400">Total Errors: </span>
          <span className="text-xs font-bold text-rose-400">{totalErrors.toLocaleString()}</span>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs" aria-label="Error distribution by event type">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400 font-medium">
              <th scope="col" className="pb-3 pr-4">Event Type</th>
              <th scope="col" className="pb-3 px-4 text-right">Occurrences</th>
              <th scope="col" className="pb-3 px-4 text-right">Share (%)</th>
              <th scope="col" className="pb-3 pl-4 min-w-[140px]">Distribution</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {data.map((item) => (
              <tr key={item.event_type} className="hover:bg-slate-800/30 transition-colors">
                <td className="py-3 pr-4 font-mono font-medium text-slate-200">
                  <span className="inline-block rounded bg-slate-800 px-2 py-0.5 text-xs text-rose-300 border border-rose-900/30">
                    {item.event_type}
                  </span>
                </td>
                <td className="py-3 px-4 text-right font-semibold text-slate-100">
                  {item.count.toLocaleString()}
                </td>
                <td className="py-3 px-4 text-right font-semibold text-slate-300">
                  {item.percentage.toFixed(1)}%
                </td>
                <td className="py-3 pl-4">
                  <div className="h-2 w-full overflow-hidden rounded-full bg-slate-800">
                    <div
                      className="h-full rounded-full bg-rose-500/80 transition-all duration-300"
                      style={{ width: `${Math.min(100, Math.max(2, item.percentage))}%` }}
                      role="progressbar"
                      aria-valuenow={item.percentage}
                      aria-valuemin={0}
                      aria-valuemax={100}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
