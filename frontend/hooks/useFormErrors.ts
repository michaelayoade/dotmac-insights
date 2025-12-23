import { useState, useCallback, useMemo } from 'react';

/**
 * Form field error state
 */
export type FieldErrors = Record<string, string | undefined>;

export interface UseFormErrorsOptions {
  /** Initial errors */
  initialErrors?: FieldErrors;
}

export interface UseFormErrorsReturn {
  /** Current field errors */
  errors: FieldErrors;
  /** Set error for a specific field */
  setError: (field: string, message: string) => void;
  /** Clear error for a specific field */
  clearError: (field: string) => void;
  /** Set multiple errors at once */
  setErrors: (errors: FieldErrors) => void;
  /** Clear all errors */
  clearAll: () => void;
  /** Check if a field has an error */
  hasError: (field: string) => boolean;
  /** Get error message for a field */
  getError: (field: string) => string | undefined;
  /** Check if form has any errors */
  hasAnyErrors: boolean;
  /** Get count of fields with errors */
  errorCount: number;
}

/**
 * Hook for managing form field errors.
 *
 * Replaces the common pattern of:
 *   const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
 *
 * @example
 * const { errors, setError, clearError, hasAnyErrors } = useFormErrors();
 *
 * const handleSubmit = async () => {
 *   clearAll();
 *   if (!name) setError('name', 'Name is required');
 *   if (!email) setError('email', 'Email is required');
 *   if (hasAnyErrors) return;
 *   // ... submit
 * };
 *
 * <input className={errors.name ? 'border-red-500' : ''} />
 * {errors.name && <span className="text-red-500">{errors.name}</span>}
 */
export function useFormErrors(opts: UseFormErrorsOptions = {}): UseFormErrorsReturn {
  const { initialErrors = {} } = opts;
  const [errors, setErrorsState] = useState<FieldErrors>(initialErrors);

  const setError = useCallback((field: string, message: string) => {
    setErrorsState((prev) => ({ ...prev, [field]: message }));
  }, []);

  const clearError = useCallback((field: string) => {
    setErrorsState((prev) => {
      const next = { ...prev };
      delete next[field];
      return next;
    });
  }, []);

  const setErrors = useCallback((newErrors: FieldErrors) => {
    setErrorsState(newErrors);
  }, []);

  const clearAll = useCallback(() => {
    setErrorsState({});
  }, []);

  const hasError = useCallback((field: string) => Boolean(errors[field]), [errors]);

  const getError = useCallback((field: string) => errors[field], [errors]);

  const hasAnyErrors = useMemo(
    () => Object.values(errors).some((e) => Boolean(e)),
    [errors]
  );

  const errorCount = useMemo(
    () => Object.values(errors).filter((e) => Boolean(e)).length,
    [errors]
  );

  return {
    errors,
    setError,
    clearError,
    setErrors,
    clearAll,
    hasError,
    getError,
    hasAnyErrors,
    errorCount,
  };
}

// =============================================================================
// FORM VALIDATION HELPERS
// =============================================================================

export interface ValidationRule {
  test: (value: unknown) => boolean;
  message: string;
}

export type ValidationRules = Record<string, ValidationRule[]>;

/**
 * Validate form data against rules.
 *
 * @example
 * const rules: ValidationRules = {
 *   name: [{ test: (v) => Boolean(v), message: 'Name is required' }],
 *   email: [
 *     { test: (v) => Boolean(v), message: 'Email is required' },
 *     { test: (v) => /\S+@\S+\.\S+/.test(String(v)), message: 'Invalid email' },
 *   ],
 * };
 *
 * const errors = validateForm(formData, rules);
 * if (Object.keys(errors).length > 0) {
 *   setErrors(errors);
 *   return;
 * }
 */
export function validateForm(
  data: Record<string, unknown>,
  rules: ValidationRules
): FieldErrors {
  const errors: FieldErrors = {};

  for (const [field, fieldRules] of Object.entries(rules)) {
    const value = data[field];
    for (const rule of fieldRules) {
      if (!rule.test(value)) {
        errors[field] = rule.message;
        break; // Stop at first failing rule for this field
      }
    }
  }

  return errors;
}

/**
 * Common validation rules for reuse.
 */
export const commonRules = {
  required: (message = 'This field is required'): ValidationRule => ({
    test: (v) => v !== undefined && v !== null && v !== '',
    message,
  }),

  email: (message = 'Invalid email address'): ValidationRule => ({
    test: (v) => !v || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(v)),
    message,
  }),

  minLength: (min: number, message?: string): ValidationRule => ({
    test: (v) => !v || String(v).length >= min,
    message: message || `Must be at least ${min} characters`,
  }),

  maxLength: (max: number, message?: string): ValidationRule => ({
    test: (v) => !v || String(v).length <= max,
    message: message || `Must be at most ${max} characters`,
  }),

  pattern: (regex: RegExp, message: string): ValidationRule => ({
    test: (v) => !v || regex.test(String(v)),
    message,
  }),

  number: (message = 'Must be a number'): ValidationRule => ({
    test: (v) => v === undefined || v === null || v === '' || !isNaN(Number(v)),
    message,
  }),

  positiveNumber: (message = 'Must be a positive number'): ValidationRule => ({
    test: (v) => v === undefined || v === null || v === '' || (Number(v) > 0),
    message,
  }),
};
