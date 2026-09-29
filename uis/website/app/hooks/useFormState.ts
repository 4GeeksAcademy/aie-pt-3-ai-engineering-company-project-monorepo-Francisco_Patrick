'use client';

import { useState, useCallback } from 'react';

export type ValidationFn<T> = (data: T) => Partial<Record<keyof T, string>>;

export interface UseFormStateReturn<T> {
  /** Current form state values */
  readonly formData: T;
  /** Current field validation error messages */
  readonly errors: Partial<Record<keyof T, string>>;
  /** General status message banner text */
  readonly statusMessage: string;
  /** Flag indicating successful form submission */
  readonly isSuccess: boolean;
  /** Flag indicating ongoing async form submission */
  readonly isLoading: boolean;
  /** Handler for generic input, select, textarea, and checkbox change events */
  readonly handleChange: (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => void;
  /** Function to update a specific field directly */
  readonly setFieldValue: <K extends keyof T>(field: K, value: T[K]) => void;
  /** Function to update all form values */
  readonly setFormData: React.Dispatch<React.SetStateAction<T>>;
  /** Function to validate form data and update error state */
  readonly validateForm: (validateFn: ValidationFn<T>) => boolean;
  /** Set custom status banner state */
  readonly setStatus: (message: string, success: boolean) => void;
  /** Set loading state */
  readonly setIsLoading: (loading: boolean) => void;
  /** Reset form to initial state and clear errors */
  readonly resetForm: () => void;
}

/**
 * Reusable custom hook to manage interactive form state, field inputs, validation errors, and submission status across application forms.
 *
 * @param initialValues - Initial state object for form data fields.
 * @returns Object providing form state values, input change handlers, validation trigger, and reset functions.
 */
export function useFormState<T extends Record<string, unknown>>(
  initialValues: T
): UseFormStateReturn<T> {
  const [formData, setFormData] = useState<T>(initialValues);
  const [errors, setErrors] = useState<Partial<Record<keyof T, string>>>({});
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [isSuccess, setIsSuccess] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>): void => {
      const { name, value, type } = e.target;
      const key = name as keyof T;

      if (type === 'checkbox') {
        const target = e.target as HTMLInputElement;
        if (Array.isArray(formData[key])) {
          const selected = target.value;
          const currentArr = (formData[key] as unknown as readonly string[]) ?? [];
          const nextArr = target.checked
            ? [...currentArr, selected]
            : currentArr.filter((s) => s !== selected);
          setFormData((prev) => ({
            ...prev,
            [key]: nextArr as unknown as T[keyof T],
          }));
        } else {
          setFormData((prev) => ({
            ...prev,
            [key]: target.checked as unknown as T[keyof T],
          }));
        }
      } else if (type === 'number') {
        setFormData((prev) => ({
          ...prev,
          [key]: (value === '' ? '' : Number(value)) as unknown as T[keyof T],
        }));
      } else {
        setFormData((prev) => ({
          ...prev,
          [key]: value as unknown as T[keyof T],
        }));
      }

      setErrors((prev) => {
        if (prev[key] !== undefined) {
          const nextErrors = { ...prev };
          delete nextErrors[key];
          return nextErrors;
        }
        return prev;
      });
    },
    [formData]
  );

  const setFieldValue = useCallback(<K extends keyof T>(field: K, value: T[K]): void => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));
  }, []);

  const validateForm = useCallback(
    (validateFn: ValidationFn<T>): boolean => {
      const validationErrors = validateFn(formData);
      setErrors(validationErrors);
      return Object.keys(validationErrors).length === 0;
    },
    [formData]
  );

  const setStatus = useCallback((message: string, success: boolean): void => {
    setStatusMessage(message);
    setIsSuccess(success);
  }, []);

  const resetForm = useCallback((): void => {
    setFormData(initialValues);
    setErrors({});
    setStatusMessage('');
    setIsSuccess(false);
    setIsLoading(false);
  }, [initialValues]);

  return {
    formData,
    errors,
    statusMessage,
    isSuccess,
    isLoading,
    handleChange,
    setFieldValue,
    setFormData,
    validateForm,
    setStatus,
    setIsLoading,
    resetForm,
  };
}
