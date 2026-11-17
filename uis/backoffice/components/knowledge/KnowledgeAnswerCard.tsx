'use client';

import React from 'react';
import type {
  KnowledgeQueryResponseDTO,
  KnowledgeSourceCitationDTO,
} from '@repo/shared-types';

/**
 * Props for the KnowledgeAnswerCard component.
 */
export interface KnowledgeAnswerCardProps {
  /** Synthesized response payload returned from the knowledge base API. */
  readonly response: KnowledgeQueryResponseDTO;
}

const DOCUMENT_LABELS: Readonly<Record<string, string>> = {
  'sla-delivery': 'Delivery SLA Policy',
  'returns-policy': 'Returns & Reverse Logistics Policy',
  'carrier-coverage': 'Carrier Coverage & Routing Policy',
  'storage-pricing': 'Warehouse Storage Pricing Policy',
};

/**
 * Displays a grounded policy response with status badge, execution latency,
 * and verifiable source document citations.
 *
 * @param props - Component properties containing the KnowledgeQueryResponseDTO.
 * @returns Rendered JSX card displaying the answer and source citations.
 */
export default function KnowledgeAnswerCard({
  response,
}: KnowledgeAnswerCardProps): React.ReactElement {
  const isRefusal = response.is_refusal;

  return (
    <article
      data-testid="knowledge-answer-card"
      aria-label="Knowledge Base Answer"
      className="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-lg space-y-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-4">
        <div className="flex items-center gap-2.5">
          <span
            data-testid="knowledge-confidence-badge"
            className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${
              isRefusal
                ? 'bg-amber-950/80 text-amber-300 border border-amber-700/60'
                : 'bg-emerald-950/80 text-emerald-300 border border-emerald-700/60'
            }`}
          >
            {isRefusal ? 'Unverified / Out of Scope' : 'Verified Policy Grounded'}
          </span>
          <span className="text-xs text-slate-400">
            Persona: <strong className="text-slate-300">TrackFlow Account Manager</strong>
          </span>
        </div>

        <span
          data-testid="knowledge-latency-badge"
          className="text-xs font-mono text-slate-400"
        >
          {response.execution_time_ms.toFixed(1)} ms
        </span>
      </div>

      <div>
        <h2 className="text-xs uppercase tracking-wider font-semibold text-slate-400 mb-1">
          Inquiry
        </h2>
        <p className="text-sm font-medium text-slate-200 italic">
          &ldquo;{response.query}&rdquo;
        </p>
      </div>

      <div className="bg-slate-950/70 border border-slate-800/90 rounded-lg p-4">
        <h3 className="text-xs uppercase tracking-wider font-semibold text-emerald-400 mb-2">
          Response
        </h3>
        <p
          data-testid="knowledge-answer-text"
          className="text-sm leading-relaxed text-slate-100 whitespace-pre-line"
        >
          {response.answer}
        </p>
      </div>

      <div className="pt-2">
        <h3 className="text-xs uppercase tracking-wider font-semibold text-slate-400 mb-2.5">
          Verified Source Citations ({response.sources.length})
        </h3>
        {response.sources.length === 0 ? (
          <p
            data-testid="knowledge-no-sources"
            className="text-xs text-slate-400 italic"
          >
            No corporate policy chunks met the calibrated 0.62 minimum similarity threshold.
          </p>
        ) : (
          <ul
            data-testid="knowledge-sources-list"
            className="grid grid-cols-1 sm:grid-cols-2 gap-3"
          >
            {response.sources.map((src: KnowledgeSourceCitationDTO, index: number) => {
              const friendlyDoc =
                DOCUMENT_LABELS[src.source_document] ?? src.source_document;
              const scorePct = `${(src.similarity_score * 100).toFixed(0)}% match`;
              return (
                <li
                  key={`${src.source_document}-${src.section}-${index}`}
                  data-testid="knowledge-citation-badge"
                  className="flex flex-col justify-between rounded-lg bg-slate-950 border border-slate-800 p-3"
                >
                  <div>
                    <span className="inline-block text-xs font-bold text-emerald-400">
                      {friendlyDoc}
                    </span>
                    <span className="block text-xs text-slate-300 mt-0.5">
                      {src.section}
                    </span>
                  </div>
                  <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400 font-mono">
                    <span>slug: {src.source_document}</span>
                    <span className="text-emerald-300/90">{scorePct}</span>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </article>
  );
}
