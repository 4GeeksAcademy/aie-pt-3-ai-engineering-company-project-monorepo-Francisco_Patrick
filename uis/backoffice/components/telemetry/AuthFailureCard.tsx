import React from 'react';
import type { AuthFailureRateMetric } from '@repo/shared-types';

export interface AuthFailureCardProps {
  /** Array of daily authentication reliability metrics. */
  readonly data: readonly AuthFailureRateMetric[];
}

/**
 * Renders an authentication reliability scorecard displaying login failure rates and daily trends.
 *
 * @param props - Component properties containing the auth failure rate time-series.
 * @returns React.ReactElement rendering the scorecard and daily metrics breakdown.
 */
export default function AuthFailureCard(props: AuthFailureCardProps): React.ReactElement {
  const { data } = props;

  if (data.length === 0) {
    return (
      <section
        className="rounded-xl border border-slate-800 bg-slate-900/80 p-6 shadow-xl backdrop-blur-sm"
        role="region"
        aria-label="Authentication Flow Reliability"
      >
        <div className="flex items-center gap-2 mb-4">
          <span className="h-2 w-2 rounded-full bg-cyan-400" />
          <h3 className="text-base font-semibold text-slate-100">Authentication Flow Reliability</h3>
        </div>
        <p className="text-sm text-slate-400">
          No authentication activity recorded for the selected reporting period.
        </p>
      </section>
    );
  }

  const totalAttempts = data.reduce((acc, item) => acc + item.total_attempts, 0);
  const totalFailed = data.reduce((acc, item) => acc + item.failed_attempts, 0);
  const overallFailureRate = totalAttempts > 0 ? (totalFailed / totalAttempts) : 0.0;
  const failurePercentage = (overallFailureRate * 100).toFixed(1);

  // Status color based on failure rate
  const rateColorClass =
    overallFailureRate === 0
      ? 'text-emerald-400'
      : overallFailureRate < 0.05
      ? 'text-cyan-400'
      : overallFailureRate < 0.15
      ? 'text-amber-400'
      : 'text-rose-400';

  return (
    <section
      className="rounded-xl border border-slate-800 bg-slate-900/80 p-6 shadow-xl backdrop-blur-sm"
      role="region"
      aria-label="Authentication Flow Reliability"
    >
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-6">
        <div>
          <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-cyan-400" />
            Authentication Flow Reliability
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Daily ratio of failed user authentication attempts against total login volume
          </p>
        </div>
        <div className="text-xs text-slate-400">
          Total Attempts: <span className="font-bold text-slate-200">{totalAttempts.toLocaleString()}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
          <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Overall Failure Rate</p>
          <p className={`mt-2 text-2xl font-extrabold ${rateColorClass}`}>{failurePercentage}%</p>
          <p className="mt-1 text-[11px] text-slate-500">Target SLA: &lt; 5.0%</p>
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
          <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Total Attempts</p>
          <p className="mt-2 text-2xl font-extrabold text-slate-100">{totalAttempts.toLocaleString()}</p>
          <p className="mt-1 text-[11px] text-slate-500">Succeeded + Failed attempts</p>
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
          <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold">Failed Attempts</p>
          <p className="mt-2 text-2xl font-extrabold text-rose-400">{totalFailed.toLocaleString()}</p>
          <p className="mt-1 text-[11px] text-slate-500">Rejected credentials or locked accounts</p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs" aria-label="Daily authentication failure rate">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400 font-medium">
              <th scope="col" className="pb-3 pr-4">Date</th>
              <th scope="col" className="pb-3 px-4 text-right">Attempts</th>
              <th scope="col" className="pb-3 px-4 text-right">Failures</th>
              <th scope="col" className="pb-3 pl-4 text-right">Daily Failure Rate</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {data.map((item) => (
              <tr key={item.date} className="hover:bg-slate-800/30 transition-colors">
                <td className="py-2.5 pr-4 text-slate-300 font-medium">{item.date}</td>
                <td className="py-2.5 px-4 text-right text-slate-300">{item.total_attempts}</td>
                <td className="py-2.5 px-4 text-right text-rose-300">{item.failed_attempts}</td>
                <td className="py-2.5 pl-4 text-right font-semibold">
                  <span
                    className={
                      item.failure_rate === 0
                        ? 'text-emerald-400'
                        : item.failure_rate < 0.1
                        ? 'text-cyan-400'
                        : 'text-rose-400'
                    }
                  >
                    {(item.failure_rate * 100).toFixed(1)}%
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
