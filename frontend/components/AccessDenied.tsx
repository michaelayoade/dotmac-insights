'use client';

import Link from 'next/link';
import { Lock } from 'lucide-react';
import { cn } from '@/lib/utils';

interface AccessDeniedProps {
  message?: string;
  className?: string;
}

export function AccessDenied({ message, className }: AccessDeniedProps) {
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
        <h2 className="text-white text-lg font-semibold">Access denied</h2>
        <p className="text-slate-muted text-sm">
          {message || "You don't have permission to view this page."}
        </p>
      </div>
      <div className="flex gap-3 mt-2">
        <Link
          href="/"
          className="rounded-lg bg-slate-elevated px-4 py-2 text-sm text-white hover:bg-slate-elevated/80 transition-colors"
        >
          Go home
        </Link>
        <button
          type="button"
          onClick={() => {
            // Hint to set token via sidebar CTA
            const el = document.querySelector('[data-auth-token-cta]') as HTMLButtonElement | null;
            el?.click();
          }}
          className="rounded-lg border border-slate-border px-4 py-2 text-sm text-slate-muted hover:text-white hover:border-teal-electric transition-colors"
          data-testid="set-token-cta"
        >
          Set token
        </button>
      </div>
    </div>
  );
}
