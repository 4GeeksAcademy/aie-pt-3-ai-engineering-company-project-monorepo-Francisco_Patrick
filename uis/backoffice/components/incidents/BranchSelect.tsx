'use client';

import React from 'react';
import { BRANCH_OPTIONS } from '@repo/shared-types';

export interface BranchSelectProps {
  id?: string | undefined;
  name?: string | undefined;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void;
  highlighted?: boolean | undefined;
  required?: boolean | undefined;
  disabled?: boolean | undefined;
  error?: string | undefined;
  label?: string | undefined;
  className?: string | undefined;
}

/**
 * Reusable Branch selection dropdown component supporting visual location highlighting.
 *
 * @param props - Component options including value, change handler, highlight flag, and error state.
 * @returns JSX Element rendering the branch select input with optional highlight badge.
 */
export const BranchSelect: React.FC<BranchSelectProps> = ({
  id = 'branch-select',
  name = 'branch',
  value,
  onChange,
  highlighted = false,
  required = true,
  disabled = false,
  error,
  label = 'Branch Location',
  className = '',
}): React.ReactElement => {
  return (
    <div className={`flex flex-col gap-1.5 ${className}`}>
      <div className="flex items-center justify-between">
        <label htmlFor={id} className="text-sm font-medium text-slate-200">
          {label} {required && <span className="text-rose-400">*</span>}
        </label>
        {highlighted && (
          <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse">
            <svg
              className="w-3.5 h-3.5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"

            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
              />
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
              />
            </svg>
            Branch Origin Selected
          </span>
        )}
      </div>

      <select
        id={id}
        name={name}
        value={value}
        onChange={onChange}
        required={required}
        disabled={disabled}
        className={`w-full px-3.5 py-2.5 rounded-lg text-sm bg-slate-900 text-slate-100 border transition-all duration-200 focus:outline-none focus:ring-2 disabled:opacity-50 disabled:cursor-not-allowed ${
          error
            ? 'border-rose-500 focus:ring-rose-500/50'
            : highlighted
              ? 'border-amber-400 bg-amber-950/20 text-amber-100 focus:ring-amber-500/50 ring-2 ring-amber-500/30'
              : 'border-slate-700 focus:ring-emerald-500/50 focus:border-emerald-500'
        }`}
      >
        <option value="" disabled>
          -- Select a Branch Location --
        </option>
        {BRANCH_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value} className="bg-slate-900 text-slate-100">
            {opt.label}
          </option>
        ))}
      </select>

      {error && <p className="text-xs text-rose-400 font-medium">{error}</p>}
    </div>
  );
};
