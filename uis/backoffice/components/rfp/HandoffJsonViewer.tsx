'use client';

import React, { useState } from 'react';
import type { IntakeHandoffPayloadDTO } from '@repo/shared-types';

/**
 * Props for the HandoffJsonViewer component.
 */
export interface HandoffJsonViewerProps {
  /** Canonical Part 2 handoff payload if completed. */
  handoff: IntakeHandoffPayloadDTO | null;
}

/**
 * Interactive preview viewer for the Part 2 Proposal Generation handoff payload.
 *
 * Displays executive summary, contradictions, internal contacts, and collapsible raw JSON.
 *
 * @param props - Component props containing the handoff payload.
 * @returns JSX Element rendering the handoff preview.
 */
export function HandoffJsonViewer({ handoff }: HandoffJsonViewerProps): React.ReactElement {
  const [isCopied, setIsCopied] = useState<boolean>(false);
  const [showRawJson, setShowRawJson] = useState<boolean>(false);

  if (!handoff) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 text-center text-slate-400 text-sm">
        El paquete de entrega (handoff) para la Parte 2 estará disponible una vez finalizado el análisis.
      </div>
    );
  }

  const handleCopyJson = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(handoff.full_handoff_json, null, 2));
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch {
      // Clipboard copy fallback
    }
  };

  const contacts = handoff.internal_contacts;

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-6 shadow-sm">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 border-b border-slate-800 gap-3">
        <div>
          <div className="flex items-center space-x-2">
            <h3 className="text-base font-semibold text-slate-100">Paquete de Entrega a Parte 2 (Propuesta)</h3>
            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              v{handoff.schema_version}
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Emitido el {new Date(handoff.created_at || handoff.emitted_at || new Date().toISOString()).toLocaleString()}
          </p>
        </div>

        <button
          onClick={handleCopyJson}
          className="inline-flex items-center px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-colors"
        >
          {isCopied ? '¡Copiado!' : 'Copiar JSON Handoff'}
        </button>
      </div>

      {/* Internal Contacts */}
      <div>
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Contactos Internos Recomendados
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {contacts.map((contact, idx) => (
            <div key={idx} className="bg-slate-800/50 rounded-lg p-3 border border-slate-800">
              <p className="text-sm font-semibold text-slate-100">{contact.name}</p>
              <p className="text-xs text-emerald-400 mt-0.5">{contact.role}</p>
              <p className="text-[11px] text-slate-400 mt-0.5">{contact.department}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Collapsible Raw JSON Viewer */}
      <div className="border border-slate-800 rounded-lg overflow-hidden">
        <button
          onClick={() => setShowRawJson(!showRawJson)}
          className="w-full flex items-center justify-between p-3 bg-slate-950/60 text-xs font-semibold text-slate-300 hover:text-white transition-colors"
        >
          <span>{showRawJson ? 'Ocultar JSON Estructurado' : 'Ver JSON Estructurado para Generación de Propuesta'}</span>
          <span>{showRawJson ? '▲' : '▼'}</span>
        </button>

        {showRawJson && (
          <div className="p-4 bg-slate-950 overflow-x-auto max-h-96 text-xs font-mono text-slate-300">
            <pre>{JSON.stringify(handoff.full_handoff_json, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  );
}
