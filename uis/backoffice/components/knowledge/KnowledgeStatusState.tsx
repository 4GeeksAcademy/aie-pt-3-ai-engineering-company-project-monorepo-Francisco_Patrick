'use client';

import React from 'react';

/**
 * Props for the KnowledgeStatusState component.
 */
export interface KnowledgeStatusStateProps {
  /** Indicates whether a query request is currently loading. */
  readonly isLoading: boolean;
  /** Optional error message when a network or service failure occurs. */
  readonly errorMessage: string | null;
  /** Callback to retry the last submitted query. */
  readonly onRetry?: (() => void) | undefined;
}

/**
 * Renders accessible loading skeleton states during in-flight requests and
 * actionable error banners with retry CTAs when backend communication fails.
 *
 * Designed with fixed dimensions to preserve zero Cumulative Layout Shift (CLS = 0).
 *
 * @param props - Status state properties.
 * @returns Rendered JSX element or null when idle.
 */
export default function KnowledgeStatusState({
  isLoading,
  errorMessage,
  onRetry,
}: KnowledgeStatusStateProps): React.ReactElement | null {
  if (isLoading) {
    return (
      <div
        data-testid="knowledge-loading-skeleton"
        role="status"
        aria-live="polite"
        aria-busy="true"
        className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg min-h-[220px] animate-pulse space-y-4"
      >
        <div className="flex items-center justify-between">
          <div className="h-5 w-44 bg-slate-800 rounded-full" />
          <div className="h-4 w-16 bg-slate-800 rounded" />
        </div>
        <div className="h-4 w-2/3 bg-slate-800 rounded" />
        <div className="space-y-2 bg-slate-950/60 p-4 rounded-lg border border-slate-800/60">
          <div className="h-4 w-full bg-slate-800 rounded" />
          <div className="h-4 w-11/12 bg-slate-800 rounded" />
          <div className="h-4 w-3/4 bg-slate-800 rounded" />
        </div>
        <span className="sr-only">Searching corporate policy knowledge base...</span>
      </div>
    );
  }

  if (errorMessage !== null) {
    return (
      <div
        data-testid="knowledge-error-banner"
        role="alert"
        className="bg-rose-950/50 border border-rose-700/70 rounded-xl p-6 shadow-lg flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
      >
        <div>
          <h2 className="text-sm font-bold text-rose-300">
            Knowledge Base Service Interruption
          </h2>
          <p className="text-xs text-rose-200/90 mt-1">{errorMessage}</p>
        </div>

        {onRetry !== undefined ? (
          <button
            type="button"
            data-testid="knowledge-retry-btn"
            onClick={onRetry}
            className="px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-xs font-semibold text-white shadow-sm focus:outline-none focus:ring-2 focus:ring-rose-400 transition-colors"
          >
            Retry Inquiry
          </button>
        ) : null}
      </div>
    );
  }

  return null;
}
