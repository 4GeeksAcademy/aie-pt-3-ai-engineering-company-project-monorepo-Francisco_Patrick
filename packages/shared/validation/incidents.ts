import type { IncidentCreateInput, IncidentCategory } from '../types/incidents';

export interface IncidentValidationErrors {
  title?: string;
  description?: string;
  category?: string;
  status?: string;
  origin?: string;
  branch?: string;
  general?: string;
}

export interface IncidentValidationResult {
  isValid: boolean;
  errors: IncidentValidationErrors;
}

const VALID_CATEGORIES: readonly IncidentCategory[] = [
  'warehouse',
  'reverse_logistics',
  'last_mile',
  'customer_experience',
] as const;

/**
 * Validates incident creation payload on client or shared modules.
 *
 * @param input - Partial or complete incident creation form values.
 * @returns Object containing boolean isValid flag and map of field-specific error messages.
 */
export function validateIncidentInput(
  input: Partial<IncidentCreateInput>
): IncidentValidationResult {
  const errors: IncidentValidationErrors = {};

  if (!input.title || !input.title.trim()) {
    errors.title = 'Title is required and cannot be blank whitespace.';
  }

  if (!input.description || !input.description.trim()) {
    errors.description = 'Description is required and cannot be blank whitespace.';
  }

  if (!input.category) {
    errors.category = 'Category selection is required.';
  } else if (!VALID_CATEGORIES.includes(input.category as IncidentCategory)) {
    errors.category = 'Invalid category selected.';
  }

  if (!input.branch || !input.branch.trim()) {
    errors.branch = 'Branch location selection is required.';
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  };
}
