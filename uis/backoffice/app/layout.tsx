import React from 'react';
import type { Metadata } from 'next';
import './globals.css';
import { Sidebar } from './components/layout/Sidebar';
import { Topbar } from './components/layout/Topbar';

export const metadata: Metadata = {
  title: 'TrackFlow Backoffice | Operational Control Suite',
  description: 'Sistema interno de gestión logística, monitoreo de hubs y ejecución de reglas de negocio.',
};

export interface BackofficeLayoutProps {
  /** Page content node */
  readonly children: React.ReactNode;
}

/**
 * Isolated internal layout shell for TrackFlow backoffice application, separate from
 * the public website layout shell.
 *
 * @param props - Child page components
 * @returns JSX element rendering the administrative application shell
 */
export default function BackofficeLayout(props: BackofficeLayoutProps): React.ReactElement {
  return (
    <html lang="es">
      <body className="flex h-screen overflow-hidden bg-slate-950 text-slate-100 antialiased">
        <Sidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <Topbar />
          <main id="main-content" className="flex-1 overflow-y-auto p-8">
            {props.children}
          </main>
        </div>
      </body>
    </html>
  );
}
