import React from 'react';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Supplier Directory | TrackFlow',
  description: 'Manage TrackFlow suppliers and carriers.',
};

export default function SuppliersLayout({
  children,
}: {
  readonly children: React.ReactNode;
}): React.ReactElement {
  return (
    <div className="flex h-full flex-col">
      <header className="mb-6">
        <h1 className="text-3xl font-bold tracking-tight text-slate-100">
          Supplier Directory
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Manage and configure logistics suppliers across multiple regions.
        </p>
      </header>
      <div className="flex-1 overflow-auto rounded-xl border border-slate-800 bg-slate-900/50 p-6">
        {children}
      </div>
    </div>
  );
}
