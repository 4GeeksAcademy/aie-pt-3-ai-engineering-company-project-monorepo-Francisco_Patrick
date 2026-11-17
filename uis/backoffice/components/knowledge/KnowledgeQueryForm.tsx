'use client';

import React, { useState } from 'react';

/**
 * Props for the KnowledgeQueryForm component.
 */
export interface KnowledgeQueryFormProps {
  /** Callback triggered when a valid query is submitted. */
  readonly onSubmit: (query: string) => void | Promise<void>;
  /** Indicates whether a query request is currently in flight. */
  readonly isLoading: boolean;
  /** Optional initial or preset query string. */
  readonly initialQuery?: string | undefined;
}

const QUICK_SAMPLE_QUERIES: readonly string[] = [
  "What is TrackFlow's standard return window and who covers return shipping costs?",
  'What is the standard monthly storage rate in Los Angeles versus Zaragoza?',
  'Which carrier is recommended for rural deliveries in Aragón?',
  'Can we guarantee 90% delivery SLA during Black Friday sales?',
  'Can we offer a discount on storage fees for a client storing 75 cubic meters?',
];

/**
 * Accessible search form for frontline teams to submit natural-language policy inquiries.
 *
 * Performs client-side validation to reject empty, whitespace-only, or overly short queries
 * before dispatching network requests.
 *
 * @param props - Component properties including onSubmit handler and loading state.
 * @returns Rendered JSX form element with sample query pills and validation feedback.
 */
export default function KnowledgeQueryForm({
  onSubmit,
  isLoading,
  initialQuery = '',
}: KnowledgeQueryFormProps): React.ReactElement {
  const [queryText, setQueryText] = useState<string>(initialQuery);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleFormSubmit = (event: React.FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    const trimmed = queryText.trim();

    if (trimmed.length === 0) {
      setValidationError('Please enter a policy or operational question before submitting.');
      return;
    }
    if (trimmed.length < 3) {
      setValidationError('Query must be at least 3 characters long.');
      return;
    }
    if (trimmed.length > 1000) {
      setValidationError('Query must not exceed 1000 characters.');
      return;
    }

    setValidationError(null);
    void onSubmit(trimmed);
  };

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>): void => {
    setQueryText(event.target.value);
    if (validationError !== null) {
      setValidationError(null);
    }
  };

  const handleSampleClick = (sample: string): void => {
    if (isLoading) {
      return;
    }
    setQueryText(sample);
    setValidationError(null);
    void onSubmit(sample);
  };

  return (
    <section
      aria-label="Knowledge Base Query Form"
      className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg"
    >
      <form onSubmit={handleFormSubmit} noValidate>
        <label
          htmlFor="knowledge-query-input"
          className="block text-sm font-semibold text-slate-200 mb-2"
        >
          Ask TrackFlow Sales &amp; Operations Knowledge Base
        </label>
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            id="knowledge-query-input"
            data-testid="knowledge-query-input"
            type="text"
            value={queryText}
            onChange={handleInputChange}
            disabled={isLoading}
            placeholder="e.g. What is our standard return window and who covers return shipping?"
            aria-invalid={validationError !== null}
            aria-describedby={validationError !== null ? 'knowledge-query-error' : undefined}
            className={`flex-1 rounded-lg bg-slate-950 px-4 py-3 text-sm text-slate-100 placeholder-slate-500 border ${
              validationError !== null
                ? 'border-rose-500 focus:ring-rose-500'
                : 'border-slate-700 focus:border-emerald-500 focus:ring-emerald-500'
            } focus:outline-none focus:ring-1 disabled:opacity-60`}
          />
          <button
            type="submit"
            data-testid="knowledge-submit-btn"
            disabled={isLoading}
            className="inline-flex items-center justify-center rounded-lg bg-emerald-600 px-6 py-3 text-sm font-semibold text-white shadow-sm hover:bg-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isLoading ? 'Searching Policy...' : 'Ask Assistant'}
          </button>
        </div>

        {validationError !== null ? (
          <p
            id="knowledge-query-error"
            data-testid="knowledge-validation-error"
            role="alert"
            className="mt-2 text-xs font-medium text-rose-400"
          >
            {validationError}
          </p>
        ) : null}
      </form>

      <div className="mt-4 pt-4 border-t border-slate-800/80">
        <span className="block text-xs font-medium text-slate-400 mb-2">
          Common commercial inquiries:
        </span>
        <div className="flex flex-wrap gap-2">
          {QUICK_SAMPLE_QUERIES.map((sample) => (
            <button
              key={sample}
              type="button"
              disabled={isLoading}
              onClick={(): void => handleSampleClick(sample)}
              className="text-left text-xs bg-slate-800/70 hover:bg-slate-800 text-slate-300 hover:text-emerald-300 border border-slate-700/70 rounded-full px-3 py-1.5 transition-colors disabled:opacity-50"
            >
              {sample}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
