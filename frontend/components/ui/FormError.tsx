'use client';

import React from 'react';
import { AlertTriangle, XCircle, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

export type FormErrorVariant = 'error' | 'warning' | 'info';

interface FormErrorProps {
  /** Error message to display */
  message: string | null | undefined;
  /** Additional details or error object */
  details?: string | { message?: string; detail?: string } | null;
  /** Visual variant */
  variant?: FormErrorVariant;
  /** Optional callback to dismiss the error */
  onDismiss?: () => void;
  /** Additional CSS classes */
  className?: string;
}

const variantStyles: Record<FormErrorVariant, { bg: string; border: string; text: string; icon: string }> = {
  error: {
    bg: 'bg-coral-alert/10',
    border: 'border-coral-alert/30',
    text: 'text-coral-alert',
    icon: 'text-coral-alert',
  },
  warning: {
    bg: 'bg-amber-warn/10',
    border: 'border-amber-warn/30',
    text: 'text-amber-warn',
    icon: 'text-amber-warn',
  },
  info: {
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    text: 'text-blue-400',
    icon: 'text-blue-400',
  },
};

const variantIcons: Record<FormErrorVariant, typeof AlertTriangle> = {
  error: XCircle,
  warning: AlertTriangle,
  info: AlertCircle,
};

/**
 * FormError displays error/warning/info messages in forms.
 * Use at the top of forms to show submission errors.
 *
 * @example
 * const [error, setError] = useState<string | null>(null);
 *
 * const handleSubmit = async () => {
 *   try {
 *     await api.create(data);
 *   } catch (err) {
 *     setError(err.message || 'Failed to save');
 *   }
 * };
 *
 * return (
 *   <form onSubmit={handleSubmit}>
 *     <FormError message={error} onDismiss={() => setError(null)} />
 *     ...
 *   </form>
 * );
 */
export function FormError({
  message,
  details,
  variant = 'error',
  onDismiss,
  className,
}: FormErrorProps) {
  if (!message) return null;

  const styles = variantStyles[variant];
  const Icon = variantIcons[variant];

  // Extract details message if it's an object
  let detailsText = '';
  if (details) {
    if (typeof details === 'string') {
      detailsText = details;
    } else if (typeof details === 'object') {
      detailsText = details.detail || details.message || '';
    }
  }

  return (
    <div
      className={cn(
        'rounded-lg border p-4 mb-4',
        styles.bg,
        styles.border,
        className
      )}
      role="alert"
    >
      <div className="flex items-start gap-3">
        <Icon className={cn('w-5 h-5 mt-0.5 flex-shrink-0', styles.icon)} />
        <div className="flex-1 min-w-0">
          <p className={cn('text-sm font-medium', styles.text)}>{message}</p>
          {detailsText && (
            <p className="text-xs text-slate-muted mt-1">{detailsText}</p>
          )}
        </div>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            className={cn(
              'flex-shrink-0 p-1 rounded hover:bg-white/10 transition-colors',
              styles.text
            )}
            aria-label="Dismiss"
          >
            <XCircle className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
}

/**
 * InlineError displays a small inline error message for form fields.
 *
 * @example
 * <input {...} />
 * <InlineError message={errors.email} />
 */
export function InlineError({
  message,
  className,
}: {
  message: string | null | undefined;
  className?: string;
}) {
  if (!message) return null;

  return (
    <p className={cn('text-xs text-coral-alert mt-1', className)}>
      {message}
    </p>
  );
}

export default FormError;
