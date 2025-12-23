'use client';

import { FileQuestion, Home, ArrowLeft } from 'lucide-react';
import { Button, LinkButton } from '@/components/ui';

export default function NotFound() {
  return (
    <div className="min-h-screen bg-slate-deep flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-slate-card border border-slate-border rounded-xl p-8 text-center">
        <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-blue-500/10 border border-blue-500/30 flex items-center justify-center">
          <FileQuestion className="w-8 h-8 text-blue-400" />
        </div>

        <h1 className="text-6xl font-bold text-foreground mb-2">404</h1>
        <h2 className="text-xl font-semibold text-foreground mb-2">Page not found</h2>
        <p className="text-slate-muted mb-6">
          The page you're looking for doesn't exist or has been moved.
        </p>

        <div className="flex gap-3 justify-center">
          <LinkButton href="/" icon={Home}>
            Dashboard
          </LinkButton>
          <Button
            variant="secondary"
            icon={ArrowLeft}
            onClick={() => typeof window !== 'undefined' && window.history.back()}
          >
            Go back
          </Button>
        </div>
      </div>
    </div>
  );
}
