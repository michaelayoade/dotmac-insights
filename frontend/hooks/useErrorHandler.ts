'use client';

import { useCallback } from 'react';
import { useToast } from '@dotmac/core';

/**
 * Centralized error handler hook for consistent error handling across the app.
 *
 * @example
 * const { handleError, handleSuccess } = useErrorHandler();
 *
 * try {
 *   await api.createInvoice(data);
 *   handleSuccess('Invoice created successfully');
 * } catch (err) {
 *   handleError(err, 'Failed to create invoice');
 * }
 */
export function useErrorHandler() {
  const { toast } = useToast();

  /**
   * Handle an error by showing a toast notification.
   * Extracts message from various error formats.
   */
  const handleError = useCallback(
    (error: unknown, fallbackMessage = 'An error occurred') => {
      let message = fallbackMessage;

      const formatDetails = (detail: unknown): string => {
        if (Array.isArray(detail)) {
          return detail
            .map((item) => {
              if (typeof item === 'string') return item;
              if (item && typeof item === 'object') {
                const errItem = item as { loc?: (string | number)[]; msg?: string };
                const loc = errItem.loc?.join('.') || 'field';
                const msg = errItem.msg || 'invalid';
                return `${loc}: ${msg}`;
              }
              return String(item);
            })
            .join('; ');
        }
        if (typeof detail === 'string') return detail;
        if (detail && typeof detail === 'object') {
          const detailObj = detail as { message?: string; detail?: string };
          return detailObj.message || detailObj.detail || fallbackMessage;
        }
        return fallbackMessage;
      };

      if (error instanceof Error) {
        message = error.message || fallbackMessage;
      } else if (typeof error === 'object' && error !== null) {
        const err = error as { message?: string; detail?: unknown };
        message = err.message || formatDetails(err.detail) || fallbackMessage;
      } else if (typeof error === 'string') {
        message = error;
      }

      toast({
        title: 'Error',
        description: message,
        variant: 'error',
      });

      // Log to console for debugging
      console.error('[Error]', fallbackMessage, error);
    },
    [toast]
  );

  /**
   * Show a success toast notification.
   */
  const handleSuccess = useCallback(
    (message: string, title = 'Success') => {
      toast({
        title,
        description: message,
        variant: 'success',
      });
    },
    [toast]
  );

  /**
   * Show a warning toast notification.
   */
  const handleWarning = useCallback(
    (message: string, title = 'Warning') => {
      toast({
        title,
        description: message,
        variant: 'warning',
      });
    },
    [toast]
  );

  /**
   * Show an info toast notification.
   */
  const handleInfo = useCallback(
    (message: string, title = 'Info') => {
      toast({
        title,
        description: message,
        variant: 'info',
      });
    },
    [toast]
  );

  return {
    handleError,
    handleSuccess,
    handleWarning,
    handleInfo,
  };
}

export default useErrorHandler;
