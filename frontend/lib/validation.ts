/**
 * Form and input validation utilities
 * Provides composable validators for common use cases
 */

// Validation result type
export interface ValidationResult {
  valid: boolean;
  error?: string;
}

// Validator function type
export type Validator<T = string> = (value: T) => ValidationResult;

// Helper to create successful result
const valid = (): ValidationResult => ({ valid: true });

// Helper to create error result
const invalid = (error: string): ValidationResult => ({ valid: false, error });

/**
 * Check if value is not empty
 */
export const required = (message = 'This field is required'): Validator<string | null | undefined> => {
  return (value) => {
    if (value === null || value === undefined || value.trim() === '') {
      return invalid(message);
    }
    return valid();
  };
};

/**
 * Check minimum length
 */
export const minLength = (min: number, message?: string): Validator => {
  return (value) => {
    if (value.length < min) {
      return invalid(message || `Must be at least ${min} characters`);
    }
    return valid();
  };
};

/**
 * Check maximum length
 */
export const maxLength = (max: number, message?: string): Validator => {
  return (value) => {
    if (value.length > max) {
      return invalid(message || `Must be no more than ${max} characters`);
    }
    return valid();
  };
};

/**
 * Validate email format
 */
export const email = (message = 'Please enter a valid email address'): Validator => {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return (value) => {
    if (!emailRegex.test(value)) {
      return invalid(message);
    }
    return valid();
  };
};

/**
 * Validate phone number format (flexible)
 */
export const phone = (message = 'Please enter a valid phone number'): Validator => {
  // Accepts various formats: +234..., 0..., with or without spaces/dashes
  const phoneRegex = /^[+]?[(]?[0-9]{1,4}[)]?[-\s./0-9]*$/;
  return (value) => {
    const cleaned = value.replace(/\s/g, '');
    if (cleaned.length < 7 || cleaned.length > 20 || !phoneRegex.test(value)) {
      return invalid(message);
    }
    return valid();
  };
};

/**
 * Validate URL format
 */
export const url = (message = 'Please enter a valid URL'): Validator => {
  return (value) => {
    try {
      new URL(value);
      return valid();
    } catch {
      return invalid(message);
    }
  };
};

/**
 * Validate against regex pattern
 */
export const pattern = (regex: RegExp, message = 'Invalid format'): Validator => {
  return (value) => {
    if (!regex.test(value)) {
      return invalid(message);
    }
    return valid();
  };
};

/**
 * Validate number is within range
 */
export const numberRange = (
  min: number,
  max: number,
  message?: string
): Validator<number> => {
  return (value) => {
    if (value < min || value > max) {
      return invalid(message || `Must be between ${min} and ${max}`);
    }
    return valid();
  };
};

/**
 * Validate positive number
 */
export const positiveNumber = (message = 'Must be a positive number'): Validator<number> => {
  return (value) => {
    if (value <= 0) {
      return invalid(message);
    }
    return valid();
  };
};

/**
 * Validate non-negative number
 */
export const nonNegative = (message = 'Cannot be negative'): Validator<number> => {
  return (value) => {
    if (value < 0) {
      return invalid(message);
    }
    return valid();
  };
};

/**
 * Validate date is in the future
 */
export const futureDate = (message = 'Date must be in the future'): Validator<Date | string> => {
  return (value) => {
    const date = value instanceof Date ? value : new Date(value);
    if (date <= new Date()) {
      return invalid(message);
    }
    return valid();
  };
};

/**
 * Validate date is in the past
 */
export const pastDate = (message = 'Date must be in the past'): Validator<Date | string> => {
  return (value) => {
    const date = value instanceof Date ? value : new Date(value);
    if (date >= new Date()) {
      return invalid(message);
    }
    return valid();
  };
};

/**
 * Compose multiple validators - all must pass
 */
export const compose = <T>(...validators: Validator<T>[]): Validator<T> => {
  return (value) => {
    for (const validator of validators) {
      const result = validator(value);
      if (!result.valid) {
        return result;
      }
    }
    return valid();
  };
};

/**
 * Make a validator optional - passes if value is empty
 */
export const optional = <T extends string | null | undefined>(
  validator: Validator<NonNullable<T>>
): Validator<T> => {
  return (value) => {
    if (value === null || value === undefined || value === '') {
      return valid();
    }
    return validator(value as NonNullable<T>);
  };
};

/**
 * Validate a form object with field validators
 */
export interface FormValidation<T> {
  [K: string]: Validator<T[keyof T]>;
}

export interface FormErrors {
  [field: string]: string | undefined;
}

export function validateForm<T extends Record<string, unknown>>(
  values: T,
  validators: Partial<{ [K in keyof T]: Validator<T[K]> }>
): { valid: boolean; errors: FormErrors } {
  const errors: FormErrors = {};
  let isValid = true;

  for (const [field, validator] of Object.entries(validators)) {
    if (validator) {
      const result = (validator as Validator<unknown>)(values[field]);
      if (!result.valid) {
        errors[field] = result.error;
        isValid = false;
      }
    }
  }

  return { valid: isValid, errors };
}

/**
 * Common field validators ready to use
 */
export const validators = {
  required,
  email: email(),
  phone: phone(),
  url: url(),
  requiredEmail: compose(required(), email()),
  requiredPhone: compose(required(), phone()),
  password: compose(
    required('Password is required'),
    minLength(8, 'Password must be at least 8 characters')
  ),
  username: compose(
    required('Username is required'),
    minLength(3, 'Username must be at least 3 characters'),
    maxLength(30, 'Username must be no more than 30 characters'),
    pattern(/^[a-zA-Z0-9_]+$/, 'Username can only contain letters, numbers, and underscores')
  ),
};

export default validators;
