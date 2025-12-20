'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ToastProvider, useToast } from '@dotmac/core';
import { ThemeProvider } from '@dotmac/design-tokens';
import { SWRConfig, type Key } from 'swr';
import { ApiError, onAuthError, clearAuthToken } from '@/lib/api';
import { AuthProvider } from '@/lib/auth-context';
import { useTheme } from '@dotmac/design-tokens';
import { applyColorScheme, getSavedColorScheme } from '@/lib/theme';
import { FeatureGateProvider } from '@/hooks/useFeatureGate';
import { validateEnv } from '@/lib/env';
import { CommandPaletteProvider } from '@/components/CommandPaletteProvider';

function ThemePersistence({ children }: { children: React.ReactNode }) {
  const { setColorScheme, config, resolvedColorScheme } = useTheme() as any;
  const colorScheme = (config as any)?.colorScheme;

  // Hydrate theme from localStorage on mount (avoids losing the user's choice across app sections)
  useEffect(() => {
    const saved = getSavedColorScheme();
    if (saved && saved !== colorScheme) {
      setColorScheme(saved);
    }
    applyColorScheme(saved || colorScheme || 'dark');
  }, [colorScheme, setColorScheme]);

  // Persist and enforce the class on the document root whenever scheme resolves
  useEffect(() => {
    applyColorScheme((colorScheme as any) || (resolvedColorScheme as any) || 'light');
  }, [colorScheme, resolvedColorScheme]);

  return <>{children}</>;
}

function SwrErrorBoundary({ children }: { children: React.ReactNode }) {
  const { toast } = useToast();
  const lastShownRef = useRef<Record<string, number>>({});

  const formatKey = useCallback((key: Key) => {
    if (!key) return '';
    if (typeof key === 'string' || typeof key === 'number') return String(key);
    if (Array.isArray(key)) {
      return key
        .filter(Boolean)
        .map((part) => {
          if (typeof part === 'string' || typeof part === 'number') return String(part);
          if (typeof part === 'object' && part !== null) return 'params';
          return '';
        })
        .filter(Boolean)
        .join(' / ');
    }
    return '';
  }, []);

  const handleError = useCallback(
    (error: unknown, key: Key) => {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        return; // Auth errors handled globally already
      }

      const keyLabel = formatKey(key) || 'data';
      const description =
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : 'An unexpected error occurred while loading data.';

      const now = Date.now();
      const lastShown = lastShownRef.current[keyLabel] || 0;
      if (now - lastShown < 8000) {
        return; // De-dupe repeated errors
      }
      lastShownRef.current[keyLabel] = now;

      toast({
        title: 'Failed to load data',
        description: `${keyLabel ? `${keyLabel}: ` : ''}${description}`,
        variant: 'error',
      });
    },
    [formatKey, toast]
  );

  // Disable SWR's built-in retry - core.ts fetchApi handles retry with exponential backoff
  // This avoids double retry amplification (core retries + SWR retries = 9 total attempts)
  // Core layer handles retry for GET/idempotent methods with proper timeout + backoff

  return (
    <SWRConfig
      value={{
        onError: handleError,
        shouldRetryOnError: false, // Disabled - core.ts handles retry
        dedupingInterval: 5000,
        revalidateOnFocus: false,
      }}
    >
      {children}
    </SWRConfig>
  );
}

function AuthErrorBanner({ show, message, onDismiss }: { show: boolean; message: string; onDismiss: () => void }) {
  if (!show) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-50 bg-red-600 text-white px-4 py-3 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <span>{message}</span>
      </div>
      <button onClick={onDismiss} className="text-white hover:text-gray-200">
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [authError, setAuthError] = useState<{ show: boolean; message: string }>({
    show: false,
    message: '',
  });

  useEffect(() => {
    const result = validateEnv();
    if (!result.valid) {
      console.error('Environment validation failed:', result.errors.join(', '));
    }
  }, []);

  useEffect(() => {
    const unsubscribe = onAuthError((event, message) => {
      if (event === 'unauthorized') {
        clearAuthToken();
        setAuthError({
          show: true,
          message: message || 'Your session has expired. Please sign in again.',
        });
      } else if (event === 'forbidden') {
        setAuthError({
          show: true,
          message: message || 'You do not have permission to access this resource.',
        });
      }
    });

    return unsubscribe;
  }, []);

  const dismissAuthError = () => {
    setAuthError({ show: false, message: '' });
  };

  // Read any scheme the boot script placed on the root to reduce flicker
  const initialScheme =
    typeof document !== 'undefined' && document.documentElement?.dataset?.colorScheme
      ? (document.documentElement.dataset.colorScheme as 'light' | 'dark' | 'system')
      : 'dark';

  return (
    <ThemeProvider defaultVariant="admin" defaultColorScheme={initialScheme}>
      <ThemePersistence>
        <AuthProvider>
          <FeatureGateProvider>
            <ToastProvider>
              <SwrErrorBoundary>
                <CommandPaletteProvider>
                  <AuthErrorBanner
                    show={authError.show}
                    message={authError.message}
                    onDismiss={dismissAuthError}
                  />
                  <div className={authError.show ? 'pt-12' : ''}>{children}</div>
                </CommandPaletteProvider>
              </SwrErrorBoundary>
            </ToastProvider>
          </FeatureGateProvider>
        </AuthProvider>
      </ThemePersistence>
    </ThemeProvider>
  );
}
