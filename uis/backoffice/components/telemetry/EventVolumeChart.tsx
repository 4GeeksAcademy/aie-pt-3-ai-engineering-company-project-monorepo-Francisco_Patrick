import React from 'react';
import type { DailyEventVolumeMetric } from '@repo/shared-types';

export interface EventVolumeChartProps {
  /** Array of daily event volume metrics over the reporting window. */
  readonly data: readonly DailyEventVolumeMetric[];
}

/**
 * Renders an accessible, responsive SVG bar chart visualizing daily telemetry event volumes.
 *
 * @param props - Component properties containing the daily event metrics array.
 * @returns React.ReactElement rendering the bar chart or empty state.
 */
export default function EventVolumeChart(props: EventVolumeChartProps): React.ReactElement {
  const { data } = props;

  if (data.length === 0) {
    return (
      <div
        className="rounded-xl border border-slate-800 bg-slate-900/80 p-6 text-center"
        role="region"
        aria-label="Daily Event Volume Chart"
      >
        <h3 className="text-base font-semibold text-slate-200">Daily Event Volume</h3>
        <p className="mt-4 text-sm text-slate-400">
          No event volume data available for the selected period.
        </p>
      </div>
    );
  }

  const maxCount = Math.max(...data.map((item) => item.count), 1);
  const totalEvents = data.reduce((acc, item) => acc + item.count, 0);
  const dailyAverage = Math.round((totalEvents / data.length) * 10) / 10;

  const chartHeight = 180;
  const barWidth = 36;
  const barGap = 16;
  const paddingX = 24;
  const chartWidth = Math.max(500, paddingX * 2 + data.length * (barWidth + barGap));

  return (
    <section
      className="rounded-xl border border-slate-800 bg-slate-900/80 p-6 shadow-xl backdrop-blur-sm"
      role="region"
      aria-label="Daily Event Volume Chart"
    >
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-6">
        <div>
          <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            Daily Event Volume
          </h3>
          <p className="text-xs text-slate-400 mt-0.5">
            Total system operational telemetry events captured per calendar day (UTC)
          </p>
        </div>
        <div className="flex items-center gap-4 text-xs">
          <div className="bg-slate-800/80 border border-slate-700/60 rounded-lg px-3 py-1.5">
            <span className="text-slate-400">Total: </span>
            <span className="font-bold text-emerald-400">{totalEvents.toLocaleString()}</span>
          </div>
          <div className="bg-slate-800/80 border border-slate-700/60 rounded-lg px-3 py-1.5">
            <span className="text-slate-400">Avg/day: </span>
            <span className="font-bold text-slate-200">{dailyAverage.toLocaleString()}</span>
          </div>
        </div>
      </div>

      <div className="overflow-x-auto pb-2">
        <svg
          viewBox={`0 0 ${chartWidth} ${chartHeight + 40}`}
          className="w-full h-56 select-none"
          role="img"
          aria-label="Bar chart showing events per day"
        >
          {/* Subtle horizontal grid lines */}
          <line
            x1={paddingX}
            y1={chartHeight * 0.25}
            x2={chartWidth - paddingX}
            y2={chartHeight * 0.25}
            stroke="#334155"
            strokeDasharray="4 4"
            strokeWidth="0.5"
          />
          <line
            x1={paddingX}
            y1={chartHeight * 0.5}
            x2={chartWidth - paddingX}
            y2={chartHeight * 0.5}
            stroke="#334155"
            strokeDasharray="4 4"
            strokeWidth="0.5"
          />
          <line
            x1={paddingX}
            y1={chartHeight * 0.75}
            x2={chartWidth - paddingX}
            y2={chartHeight * 0.75}
            stroke="#334155"
            strokeDasharray="4 4"
            strokeWidth="0.5"
          />
          <line
            x1={paddingX}
            y1={chartHeight}
            x2={chartWidth - paddingX}
            y2={chartHeight}
            stroke="#475569"
            strokeWidth="1"
          />

          {data.map((item, index) => {
            const barHeight = Math.max(4, (item.count / maxCount) * (chartHeight - 30));
            const x = paddingX + index * (barWidth + barGap);
            const y = chartHeight - barHeight;

            return (
              <g key={item.date} className="group cursor-pointer">
                <rect
                  data-testid="event-volume-bar"
                  x={x}
                  y={y}
                  width={barWidth}
                  height={barHeight}
                  rx={4}
                  className="fill-emerald-500/80 hover:fill-emerald-400 transition-colors"
                />
                <text
                  x={x + barWidth / 2}
                  y={y - 6}
                  textAnchor="middle"
                  className="fill-slate-300 text-[11px] font-semibold"
                >
                  {item.count}
                </text>
                <text
                  x={x + barWidth / 2}
                  y={chartHeight + 20}
                  textAnchor="middle"
                  className="fill-slate-400 text-[11px]"
                >
                  {item.date}
                </text>
              </g>
            );
          })}
        </svg>
      </div>
    </section>
  );
}
