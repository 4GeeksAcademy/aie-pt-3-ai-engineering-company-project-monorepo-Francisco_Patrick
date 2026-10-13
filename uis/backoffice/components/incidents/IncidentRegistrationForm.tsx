'use client';

import React, { useState } from 'react';
import type {
  Incident,
  IncidentCategory,
  IncidentCreateInput,
  IncidentOrigin,
  IncidentStatus,
} from '@repo/shared-types';
import { validateIncidentInput, type IncidentValidationErrors } from '@repo/shared-types';
import { createIncident, IncidentApiError } from '../../lib/api/incidents';
import { BranchSelect } from './BranchSelect';

export interface IncidentRegistrationFormProps {
  onSuccess?: ((created: Incident) => void) | undefined;
  className?: string | undefined;
}

const CATEGORY_OPTIONS: Array<{ value: IncidentCategory; label: string }> = [
  { value: 'warehouse', label: 'Warehouse & Storage' },
  { value: 'reverse_logistics', label: 'Reverse Logistics & Returns' },
  { value: 'last_mile', label: 'Last Mile Delivery' },
  { value: 'customer_experience', label: 'Customer Experience' },
];

const STATUS_OPTIONS: Array<{ value: IncidentStatus; label: string }> = [
  { value: 'open', label: 'Open' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'resolved', label: 'Resolved' },
  { value: 'discarded', label: 'Discarded' },
];

const ORIGIN_OPTIONS: Array<{ value: IncidentOrigin; label: string }> = [
  { value: 'customer', label: 'Customer Origin' },
  { value: 'branch', label: 'Branch Location Origin' },
  { value: 'internal', label: 'Internal Tool / System' },
];

const INITIAL_FORM_STATE: IncidentCreateInput = {
  title: '',
  description: '',
  category: 'warehouse',
  status: 'open',
  origin: 'internal',
  branch: 'central',
};

/**
 * Incident Registration Form component with client-side validation, visual origin highlighting,
 * submit loading states, and user-friendly error messages.
 *
 * @param props - Form props including optional completion callback.
 * @returns JSX Element rendering the registration form card.
 */
export const IncidentRegistrationForm: React.FC<IncidentRegistrationFormProps> = ({
  onSuccess,
  className = '',
}): React.ReactElement => {
  const [formData, setFormData] = useState<IncidentCreateInput>(INITIAL_FORM_STATE);
  const [errors, setErrors] = useState<IncidentValidationErrors>({});
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [generalError, setGeneralError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ): void => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));

    // Clear specific field error when edited
    if (errors[name as keyof IncidentValidationErrors]) {
      setErrors((prev) => ({ ...prev, [name]: undefined }));
    }
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>): Promise<void> => {
    e.preventDefault();
    setGeneralError(null);
    setSuccessMessage(null);

    // Client-side validation check
    const validation = validateIncidentInput(formData);
    if (!validation.isValid) {
      setErrors(validation.errors);
      return;
    }

    setErrors({});
    setIsSubmitting(true);

    try {
      const created = await createIncident(formData);
      setSuccessMessage(`Incident "${created.title}" successfully registered (ID: ${created.id}).`);
      setFormData(INITIAL_FORM_STATE);
      if (onSuccess) {
        onSuccess(created);
      }
    } catch (err: unknown) {
      if (err instanceof IncidentApiError) {
        if (err.fieldErrors) {
          setErrors(err.fieldErrors);
        }
        setGeneralError(err.message);
      } else {
        setGeneralError(
          'An unexpected error occurred while saving the incident. Please try again.'
        );
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const isBranchHighlighted = formData.origin === 'branch';

  return (
    <div
      className={`bg-slate-900 border border-slate-800 rounded-xl p-6 sm:p-8 shadow-xl max-w-2xl mx-auto ${className}`}
    >
      <div className="mb-6">
        <h2 className="text-xl font-bold text-white tracking-tight">Register New Incident</h2>
        <p className="text-sm text-slate-400 mt-1">
          Record operational issues, logistics delays, or customer complaints directly into the
          incident management system.
        </p>
      </div>

      {successMessage && (
        <div className="mb-6 p-4 rounded-lg bg-emerald-950/40 border border-emerald-500/40 text-emerald-300 text-sm flex items-start gap-3">
          <svg className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <div>
            <p className="font-semibold">{successMessage}</p>
          </div>
        </div>
      )}

      {generalError && (
        <div className="mb-6 p-4 rounded-lg bg-rose-950/40 border border-rose-500/40 text-rose-300 text-sm flex items-start gap-3">
          <svg className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <p className="font-semibold">{generalError}</p>
          </div>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-5" noValidate>
        {/* Title */}
        <div>
          <label htmlFor="title" className="block text-sm font-medium text-slate-200 mb-1.5">
            Incident Title <span className="text-rose-400">*</span>
          </label>
          <input
            type="text"
            id="title"
            name="title"
            value={formData.title}
            onChange={handleChange}
            placeholder="e.g. Broken barcode scanner in warehouse aisle 4"
            disabled={isSubmitting}
            className={`w-full px-3.5 py-2.5 rounded-lg text-sm bg-slate-950 text-slate-100 border transition-all duration-200 focus:outline-none focus:ring-2 ${
              errors.title
                ? 'border-rose-500 focus:ring-rose-500/50'
                : 'border-slate-700 focus:ring-emerald-500/50 focus:border-emerald-500'
            }`}
          />
          {errors.title && <p className="mt-1 text-xs text-rose-400 font-medium">{errors.title}</p>}
        </div>

        {/* Category & Status */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="category" className="block text-sm font-medium text-slate-200 mb-1.5">
              Category <span className="text-rose-400">*</span>
            </label>
            <select
              id="category"
              name="category"
              value={formData.category}
              onChange={handleChange}
              disabled={isSubmitting}
              className={`w-full px-3.5 py-2.5 rounded-lg text-sm bg-slate-950 text-slate-100 border transition-all duration-200 focus:outline-none focus:ring-2 ${
                errors.category
                  ? 'border-rose-500 focus:ring-rose-500/50'
                  : 'border-slate-700 focus:ring-emerald-500/50 focus:border-emerald-500'
              }`}
            >
              {CATEGORY_OPTIONS.map((cat) => (
                <option key={cat.value} value={cat.value}>
                  {cat.label}
                </option>
              ))}
            </select>
            {errors.category && (
              <p className="mt-1 text-xs text-rose-400 font-medium">{errors.category}</p>
            )}
          </div>

          <div>
            <label htmlFor="status" className="block text-sm font-medium text-slate-200 mb-1.5">
              Initial Status
            </label>
            <select
              id="status"
              name="status"
              value={formData.status}
              onChange={handleChange}
              disabled={isSubmitting}
              className="w-full px-3.5 py-2.5 rounded-lg text-sm bg-slate-950 text-slate-100 border border-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500"
            >
              {STATUS_OPTIONS.map((st) => (
                <option key={st.value} value={st.value}>
                  {st.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Origin & Branch */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label htmlFor="origin" className="block text-sm font-medium text-slate-200 mb-1.5">
              Origin
            </label>
            <select
              id="origin"
              name="origin"
              value={formData.origin}
              onChange={handleChange}
              disabled={isSubmitting}
              className="w-full px-3.5 py-2.5 rounded-lg text-sm bg-slate-950 text-slate-100 border border-slate-700 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500"
            >
              {ORIGIN_OPTIONS.map((orig) => (
                <option key={orig.value} value={orig.value}>
                  {orig.label}
                </option>
              ))}
            </select>
          </div>

          <BranchSelect
            id="branch"
            name="branch"
            value={formData.branch}
            onChange={handleChange}
            highlighted={isBranchHighlighted}
            error={errors.branch}
            disabled={isSubmitting}
          />
        </div>

        {/* Description */}
        <div>
          <label htmlFor="description" className="block text-sm font-medium text-slate-200 mb-1.5">
            Detailed Description <span className="text-rose-400">*</span>
          </label>
          <textarea
            id="description"
            name="description"
            rows={4}
            value={formData.description}
            onChange={handleChange}
            placeholder="Describe what happened, equipment involved, impacts, or corrective actions needed..."
            disabled={isSubmitting}
            className={`w-full px-3.5 py-2.5 rounded-lg text-sm bg-slate-950 text-slate-100 border transition-all duration-200 focus:outline-none focus:ring-2 ${
              errors.description
                ? 'border-rose-500 focus:ring-rose-500/50'
                : 'border-slate-700 focus:ring-emerald-500/50 focus:border-emerald-500'
            }`}
          />
          {errors.description && (
            <p className="mt-1 text-xs text-rose-400 font-medium">{errors.description}</p>
          )}
        </div>

        {/* Form Actions */}
        <div className="pt-2 flex justify-end">
          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex items-center justify-center px-5 py-2.5 rounded-lg text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-150 shadow-lg shadow-emerald-950/30"
          >
            {isSubmitting ? (
              <>
                <svg
                  className="animate-spin -ml-1 mr-2 h-4 w-4 text-white"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
                Registering Incident...
              </>
            ) : (
              'Submit Incident'
            )}
          </button>
        </div>
      </form>
    </div>
  );
};
