'use client';

import React, { useState } from 'react';
import type { DepartmentSectionDTO } from '@repo/shared-types';

/**
 * Props for the DepartmentKeyAspectsCard component.
 */
export interface DepartmentKeyAspectsCardProps {
  /** List of evaluated department sections. */
  sections: DepartmentSectionDTO[];
}

/**
 * Tabbed or card viewer displaying operational domain findings from department workers.
 *
 * Shows responsible lead, extracted key aspects, zero-hallucination open questions, and policy warnings.
 *
 * @param props - Component props containing department sections.
 * @returns JSX Element rendering department findings.
 */
export function DepartmentKeyAspectsCard({ sections }: DepartmentKeyAspectsCardProps): React.ReactElement {
  const [activeTab, setActiveTab] = useState<string>(
    sections.length > 0 ? (sections[0]?.department_id ?? 'warehouse') : 'warehouse'
  );

  if (sections.length === 0) {
    return (
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 text-center text-slate-400 text-sm">
        No se han registrado evaluaciones departamentales para esta propuesta.
      </div>
    );
  }

  const currentSection = sections.find((s) => s.department_id === activeTab) || sections[0];

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
      {/* Department Tabs */}
      <div className="flex border-b border-slate-800 bg-slate-950/50 px-4 pt-3 space-x-2">
        {sections.map((sec) => (
          <button
            key={sec.department_id}
            onClick={() => setActiveTab(sec.department_id)}
            className={`px-4 py-2 text-xs font-semibold rounded-t-lg transition-colors border-b-2 ${
              activeTab === sec.department_id
                ? 'border-emerald-500 text-emerald-400 bg-slate-900'
                : 'border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/50'
            }`}
          >
            {sec.department_name}
          </button>
        ))}
      </div>

      {currentSection && (
        <div className="p-6 space-y-6">
          {/* Header Info */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 border-b border-slate-800">
            <div>
              <h4 className="text-base font-semibold text-slate-100">{currentSection.department_name}</h4>
              <p className="text-xs text-slate-400 mt-0.5">
                Responsable del Área: <span className="text-slate-200 font-medium">{currentSection.responsible_person}</span>
              </p>
            </div>
          </div>

          {/* Key Aspects Grid */}
          <div>
            <h5 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">
              Aspectos Operativos Clave
            </h5>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {Object.entries(currentSection.key_aspects).map(([key, val]) => (
                <div key={key} className="bg-slate-800/40 rounded-lg p-3 border border-slate-800">
                  <p className="text-[11px] text-slate-400 capitalize">
                    {key.replace(/_/g, ' ')}
                  </p>
                  <p className="text-sm font-semibold text-slate-100 mt-1">
                    {val === null || val === undefined
                      ? 'No especificado'
                      : typeof val === 'object'
                      ? Array.isArray(val)
                        ? val.join(', ') || 'Ninguno'
                        : JSON.stringify(val)
                      : String(val)}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Open Questions (Zero Hallucination Guardrail) */}
          {currentSection.open_questions.length > 0 && (
            <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/20">
              <div className="flex items-center space-x-2 mb-2">
                <svg className="w-4 h-4 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <h5 className="text-xs font-semibold text-amber-400 uppercase tracking-wider">
                  Preguntas Abiertas y Datos No Especificados ({currentSection.open_questions.length})
                </h5>
              </div>
              <ul className="list-disc list-inside space-y-1 text-xs text-slate-300">
                {currentSection.open_questions.map((q, idx) => (
                  <li key={idx} className="leading-relaxed">{q}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Policy Warnings */}
          {currentSection.policy_warnings.length > 0 && (
            <div className="p-4 rounded-xl bg-rose-500/5 border border-rose-500/20">
              <h5 className="text-xs font-semibold text-rose-400 uppercase tracking-wider mb-2">
                Advertencias de Política ({currentSection.policy_warnings.length})
              </h5>
              <ul className="list-disc list-inside space-y-1 text-xs text-rose-300">
                {currentSection.policy_warnings.map((w, idx) => (
                  <li key={idx}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
