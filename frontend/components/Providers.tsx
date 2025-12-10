'use client';

import { useEffect, useState } from 'react';
import { ToastProvider } from '@dotmac/core';
import { ThemeProvider } from '@dotmac/design-tokens';
import { onAuthError, clearAuthToken } from '@/lib/api';
import { AuthProvider } from '@/lib/auth-context';

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

  return (
    <ThemeProvider defaultVariant="admin" defaultColorScheme="dark">
      <AuthProvider>
        <ToastProvider>
          <AuthErrorBanner
            show={authError.show}
            message={authError.message}
            onDismiss={dismissAuthError}
          />
          <div className={authError.show ? 'pt-12' : ''}>{children}</div>
        </ToastProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}
