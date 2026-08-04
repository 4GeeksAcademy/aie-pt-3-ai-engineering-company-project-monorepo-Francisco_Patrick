'use client';

import React, { useState } from 'react';

export interface TopbarProps {
  /** Optional title for current view */
  readonly title?: string;
}

/**
 * Navigation topbar component for internal backoffice shell with active hub selector
 * (Los Angeles / Zaragoza) and user status indicators.
 *
 * @param props - Custom view title
 * @returns JSX element rendering the topbar header
 */
export function Topbar(props: TopbarProps): React.ReactElement {
  const [activeHub, setActiveHub] = useState<'LA' | 'ZAG'>('LA');
  const title = props.title ?? 'Operaciones Globales';

  return (
    <header className="flex h-16 items-center justify-between border-b border-slate-800 bg-slate-900/80 px-8 backdrop-blur">
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-semibold text-slate-100">{title}</h1>
        <span className="inline-block h-4 w-px bg-slate-700" />
        <span className="inline-flex items-center gap-1.5 text-xs text-slate-400">
          <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          Sistemas Operativos 24/7
        </span>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center rounded-lg border border-slate-700 bg-slate-950 p-1 text-xs">
          <button
            type="button"
            onClick={() => setActiveHub('LA')}
            className={`rounded px-2.5 py-1 font-medium transition-colors ${
              activeHub === 'LA'
                ? 'bg-cyan-400 text-slate-950 font-semibold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            LA (US)
          </button>
          <button
            type="button"
            onClick={() => setActiveHub('ZAG')}
            className={`rounded px-2.5 py-1 font-medium transition-colors ${
              activeHub === 'ZAG'
                ? 'bg-cyan-400 text-slate-950 font-semibold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Zaragoza (ES)
          </button>
        </div>

        <div className="flex items-center gap-3 border-l border-slate-800 pl-4 text-xs text-slate-300">
          <div className="text-right">
            <p className="font-semibold text-slate-100">Logistics Admin</p>
            <p className="text-slate-400">ops-admin@trackflow.example</p>
          </div>
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-slate-800 font-bold text-cyan-300 border border-cyan-400/30">
            OP
          </span>
        </div>
      </div>
    </header>
  );
}
