'use client';

import { useEffect } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';
import { Button, LinkButton } from '@/components/ui';

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
          <Button onClick={reset} icon={RefreshCw}>
            Try again
          </Button>
          <LinkButton href="/" variant="secondary" icon={Home}>
            Dashboard
          </LinkButton>
        </div>
      </div>
    </div>
  );
}
