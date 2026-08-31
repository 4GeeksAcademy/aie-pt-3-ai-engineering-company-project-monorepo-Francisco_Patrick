'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

export interface NavLinkItem {
  readonly label: string;
  readonly href: string;
  readonly iconName: string;
}

const NAV_LINKS: readonly NavLinkItem[] = [
  { label: 'Dashboard', href: '/', iconName: 'dashboard' },
  { label: 'Business Logic Suite', href: '/business-logic', iconName: 'cpu' },
];

/**
 * Vertical navigation sidebar component for TrackFlow internal backoffice control panel.
 *
 * @returns JSX element rendering the administrative navigation sidebar
 */
export function Sidebar(): React.ReactElement {
  const pathname = usePathname();

  return (
    <aside
      className="flex w-64 flex-col border-r border-slate-800 bg-slate-900/95"
      aria-label="Navegación del sistema interno"
    >
      <div className="flex h-16 items-center gap-3 border-b border-slate-800 px-6">
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-cyan-400 text-base font-bold text-slate-950">
          TF
        </span>
        <div>
          <p className="text-sm font-semibold tracking-tight text-slate-100">
            TrackFlow Backoffice
          </p>
          <p className="text-[10px] uppercase tracking-wider text-cyan-300">
            Ops Control Suite
          </p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-4 py-6" aria-label="Menú principal de ops">
        {NAV_LINKS.map((link) => {
          const isActive = pathname === link.href;
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-cyan-400/10 text-cyan-300 border border-cyan-400/30'
                  : 'text-slate-400 hover:bg-slate-800 hover:text-slate-200'
              }`}
            >
              <span className="inline-block h-2 w-2 rounded-full bg-cyan-400" />
              <span>{link.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-slate-800 p-4">
        <div className="rounded-lg bg-slate-950 p-3 text-xs text-slate-400">
          <p className="font-semibold text-slate-300">Monorepo Integration</p>
          <p className="mt-1">Milestone 2 Domain Logic Loaded</p>
        </div>
      </div>
    </aside>
  );
}
