'use client';

import React from 'react';
import type { DepartmentId, FinalDocumentDTO, FinalDocumentSectionEntryDTO } from '@repo/shared-types';
import { MarkdownPreview } from './MarkdownPreview';

/**
 * Props for the FinalDocumentViewer component.
 */
export interface FinalDocumentViewerProps {
  /** Consolidated final commercial proposal document synthesized upon 100% department approval. */
  document: FinalDocumentDTO | null | undefined;
}

/**
 * Renders the consolidated, client-ready commercial proposal document (`FinalDocument`)
 * once all active operational departments have approved their respective sections.
 *
 * @param props - Component props containing the final synthesized proposal document.
 * @returns JSX Element rendering the final commercial proposal or null if not yet generated.
 */
export function FinalDocumentViewer({ document }: FinalDocumentViewerProps): React.ReactElement | null {
  if (!document) {
    return null;
  }

  const sectionEntries = Object.entries(document.sections) as Array<
    [DepartmentId, FinalDocumentSectionEntryDTO | undefined]
  >;

  return (
    <div
      data-testid="final-document-viewer"
      className="bg-slate-900 border border-emerald-500/30 rounded-2xl p-6 space-y-6 shadow-md"
    >
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 mb-2">
            Propuesta Comercial Consolidada (100% Aprobada)
          </span>
          <h2 className="text-lg font-extrabold text-slate-100">{document.title}</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Cliente: <span className="text-slate-200 font-semibold">{document.client_name}</span> ·
            Moneda Canónica:{' '}
            <span className="text-emerald-400 font-bold">{document.currency}</span>
          </p>
        </div>
        <div className="text-right text-xs text-slate-400">
          <p>Generado automáticamente</p>
          <p className="font-mono text-slate-300">{document.generated_at}</p>
        </div>
      </div>

      {/* Executive Summary */}
      <div className="bg-slate-950/70 border border-slate-800 rounded-xl p-4 space-y-2">
        <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-400">
          Resumen Ejecutivo Consolidado (Miguel Torres)
        </h3>
        <div className="bg-slate-900/60 rounded-lg p-3 border border-slate-800/80">
          <MarkdownPreview content={document.executive_summary} />
        </div>
      </div>

      {/* Approved Department Sections */}
      <div className="space-y-4">
        {sectionEntries.map(([deptId, sec]) => {
          if (!sec) return null;
          return (
            <div
              key={deptId}
              data-testid={`final-doc-section-${deptId}`}
              className="bg-slate-950/50 border border-slate-800 rounded-xl p-4 space-y-2"
            >
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-bold text-slate-100">{sec.department_name}</h4>
                <span className="text-xs text-emerald-400 font-medium">
                  Aprobado por {sec.responsible_person}
                </span>
              </div>
              <div className="bg-slate-900/70 p-3.5 rounded-lg border border-slate-800">
                <MarkdownPreview content={sec.approved_content} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
