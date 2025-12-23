'use client';

import Link from 'next/link';
import { Lock } from 'lucide-react';
import { cn } from '@/lib/utils';

interface AccessDeniedProps {
  message?: string;
  backHref?: string;
  backLabel?: string;
  className?: string;
}

export function AccessDenied({ message, backHref, backLabel, className }: AccessDeniedProps) {
  const authUrl = process.env.NEXT_PUBLIC_AUTH_URL || '/auth/login';
  const isExternalAuthUrl = authUrl.startsWith('http');

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-xl border border-slate-border bg-slate-card px-6 py-8 text-center',
        className
      )}
    >
      <div className="w-12 h-12 rounded-full bg-coral-alert/10 text-coral-alert flex items-center justify-center">
        <Lock className="w-6 h-6" />
      </div>
      <div className="space-y-1">
        <h2 className="text-foreground text-lg font-semibold">Access denied</h2>
        <p className="text-slate-muted text-sm">
          {message || "You don't have permission to view this page."}
        </p>
      </div>
      <div className="flex gap-3 mt-2">
        {backHref ? (
          <Link
            href={backHref}
            className="rounded-lg bg-slate-elevated px-4 py-2 text-sm text-foreground hover:bg-slate-elevated/80 transition-colors"
          >
            {backLabel || 'Back'}
          </Link>
        ) : null}
        <Link
          href="/"
          className="rounded-lg bg-slate-elevated px-4 py-2 text-sm text-foreground hover:bg-slate-elevated/80 transition-colors"
        >
          Go home
        </Link>
        {isExternalAuthUrl ? (
          <a
            href={authUrl}
            className="rounded-lg border border-slate-border px-4 py-2 text-sm text-slate-muted hover:text-foreground hover:border-teal-electric transition-colors"
            data-testid="auth-login-cta"
          >
            Sign in
          </a>
        ) : (
          <Link
            href={authUrl}
            className="rounded-lg border border-slate-border px-4 py-2 text-sm text-slate-muted hover:text-foreground hover:border-teal-electric transition-colors"
            data-testid="auth-login-cta"
          >
            Sign in
          </Link>
        )}
      </div>
    </div>
  );
}
