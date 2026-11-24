'use client';

import React from 'react';
import type { ReadabilityScoresDTO } from '@repo/shared-types';

/**
 * Props for the ReadabilityMetricCard component.
 */
export interface ReadabilityMetricCardProps {
  /** Embedded readability metrics. */
  scores: ReadabilityScoresDTO;
}

/**
 * Displays Flesch Reading Ease score, Grade Level, and document statistics with visual gauges.
 *
 * @param props - Component props containing readability scores.
 * @returns JSX Element rendering the metrics card.
 */
export function ReadabilityMetricCard({ scores }: ReadabilityMetricCardProps): React.ReactElement {
  // Determine badge color for reading ease
  let easeBadgeColor = 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
  if (scores.flesch_reading_ease < 30) {
    easeBadgeColor = 'bg-rose-500/10 text-rose-400 border-rose-500/20';
  } else if (scores.flesch_reading_ease < 60) {
    easeBadgeColor = 'bg-amber-500/10 text-amber-400 border-amber-500/20';
  }

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200">Métricas de Complejidad y Legibilidad</h3>
        <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${easeBadgeColor}`}>
          {scores.reading_level_label}
        </span>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-800">
          <p className="text-xs text-slate-400">Flesch Reading Ease</p>
          <p className="text-xl font-bold text-slate-100 mt-1">{scores.flesch_reading_ease}</p>
          <p className="text-[10px] text-slate-500 mt-0.5">0-100 (mayor = más legible)</p>
        </div>

        <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-800">
          <p className="text-xs text-slate-400">Nivel de Grado (FK)</p>
          <p className="text-xl font-bold text-slate-100 mt-1">{scores.flesch_kincaid_grade}</p>
          <p className="text-[10px] text-slate-500 mt-0.5">Grado escolar US equivalente</p>
        </div>

        <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-800">
          <p className="text-xs text-slate-400">Palabras</p>
          <p className="text-xl font-bold text-slate-100 mt-1">{scores.word_count.toLocaleString()}</p>
          <p className="text-[10px] text-slate-500 mt-0.5">Total de tokens léxicos</p>
        </div>

        <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-800">
          <p className="text-xs text-slate-400">Oraciones</p>
          <p className="text-xl font-bold text-slate-100 mt-1">{scores.sentence_count.toLocaleString()}</p>
          <p className="text-[10px] text-slate-500 mt-0.5">Estructura sintáctica</p>
        </div>
      </div>
    </div>
  );
}
