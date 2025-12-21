'use client';

import { useEffect } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import Link from 'next/link';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log the error to an error reporting service in production
    console.error('Application error:', error);
  }, [error]);

  return (
    <div className="min-h-screen bg-slate-deep flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-slate-card border border-slate-border rounded-xl p-8 text-center">
        <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-coral-alert/10 border border-coral-alert/30 flex items-center justify-center">
          <AlertTriangle className="w-8 h-8 text-coral-alert" />
        </div>

        <h1 className="text-2xl font-bold text-foreground mb-2">Something went wrong</h1>
        <p className="text-slate-muted mb-6">
          An unexpected error occurred. Please try again or return to the dashboard.
        </p>

        {process.env.NODE_ENV === 'development' && error.message && (
          <div className="mb-6 p-4 bg-slate-elevated rounded-lg text-left">
            <p className="text-xs text-slate-muted mb-1">Error details:</p>
            <p className="text-sm text-coral-alert font-mono break-all">{error.message}</p>
            {error.digest && (
              <p className="text-xs text-slate-muted mt-2">Digest: {error.digest}</p>
            )}
          </div>
        )}

        <div className="flex gap-3 justify-center">
          <button
            onClick={reset}
            className="inline-flex items-center gap-2 px-4 py-2 bg-teal-electric text-foreground rounded-lg font-medium hover:bg-teal-glow transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Try again
          </button>
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-4 py-2 bg-slate-elevated text-foreground rounded-lg font-medium hover:bg-slate-border transition-colors"
          >
            <Home className="w-4 h-4" />
            Dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}
