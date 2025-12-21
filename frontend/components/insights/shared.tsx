'use client';

import React from 'react';
import { AlertTriangle, ShieldAlert, ServerCrash, Inbox, RefreshCw } from 'lucide-react';

// Re-export DashboardShell components for convenience
export { DashboardShell, DashboardLoadingState, DashboardErrorState, DashboardEmptyState } from '@/components/ui/DashboardShell';

export function LoadingSpinner() {
  return (
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-electric"></div>
  );
}

export function InsightCard({ title, children, className = '' }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-slate-card rounded-lg border border-slate-border ${className}`}>
      <div className="px-4 py-3 border-b border-slate-border">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

export function ProgressBar({ value, max, color = 'teal' }: { value: number; max: number; color?: string }) {
  const percent = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  const colorClasses: Record<string, string> = {
    teal: 'bg-teal-electric',
    green: 'bg-green-500',
    yellow: 'bg-amber-warn',
    red: 'bg-coral-alert',
    purple: 'bg-purple-500',
    blue: 'bg-blue-500',
  };
  return (
    <div className="w-full bg-slate-elevated rounded-full h-2">
      <div
        className={`${colorClasses[color] || colorClasses.teal} h-2 rounded-full transition-all`}
        style={{ width: `${percent}%` }}
      />
    </div>
  );
}

export function InsightBadge({ children, color = 'gray' }: { children: React.ReactNode; color?: string }) {
  const colorClasses: Record<string, string> = {
    gray: 'bg-slate-elevated text-slate-muted',
    green: 'bg-green-500/20 text-green-400',
    yellow: 'bg-amber-warn/20 text-amber-warn',
    red: 'bg-coral-alert/20 text-coral-alert',
    blue: 'bg-blue-500/20 text-blue-400',
    purple: 'bg-purple-500/20 text-purple-400',
    teal: 'bg-teal-electric/20 text-teal-electric',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${colorClasses[color] || colorClasses.gray}`}>
      {children}
    </span>
  );
}

export function SummaryCard({
  title,
  value,
  subtitle,
  gradient = 'from-teal-electric to-teal-glow'
}: {
  title: string;
  value: string | number;
  subtitle?: string;
  gradient?: string;
}) {
  return (
    <div className={`bg-gradient-to-br ${gradient} rounded-lg p-4 text-foreground`}>
      <div className="text-sm opacity-80">{title}</div>
      <div className="text-3xl font-bold">{value}</div>
      {subtitle && <div className="text-sm opacity-80 mt-1">{subtitle}</div>}
    </div>
  );
}

interface ErrorDisplayProps {
  message: string;
  error?: Error | { status?: number; message?: string } | null;
  onRetry?: () => void;
}

export function ErrorDisplay({ message, error, onRetry }: ErrorDisplayProps) {
  // Detect auth errors (401, 403)
  const status = error && typeof error === 'object' && 'status' in error ? error.status : undefined;
  const isAuthError = status === 401 || status === 403;
  const isServerError = status && status >= 500;

  const Icon = isAuthError ? ShieldAlert : isServerError ? ServerCrash : AlertTriangle;
  const title = isAuthError
    ? 'Authentication Required'
    : isServerError
    ? 'Server Error'
    : 'Error Loading Data';
  const description = isAuthError
    ? 'Your session may have expired or you lack permission to view this data.'
    : message;

  return (
    <div className={`rounded-lg border p-6 ${
      isAuthError
        ? 'bg-amber-warn/10 border-amber-warn/30'
        : 'bg-coral-alert/10 border-coral-alert/30'
    }`}>
      <div className="flex items-start gap-4">
        <div className={`p-2 rounded-lg ${isAuthError ? 'bg-amber-warn/20' : 'bg-coral-alert/20'}`}>
          <Icon className={`w-5 h-5 ${isAuthError ? 'text-amber-warn' : 'text-coral-alert'}`} />
        </div>
        <div className="flex-1">
          <h3 className={`font-medium ${isAuthError ? 'text-amber-warn' : 'text-coral-alert'}`}>
            {title}
          </h3>
          <p className="text-sm text-slate-muted mt-1">{description}</p>
          {status && (
            <p className="text-xs text-slate-muted mt-2">Error code: {status}</p>
          )}
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-3 flex items-center gap-2 text-sm text-teal-electric hover:text-teal-glow transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Try again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function LoadingState() {
  return (
    <div className="flex justify-center items-center h-64">
      <LoadingSpinner />
    </div>
  );
}

interface EmptyStateProps {
  title?: string;
  message: string;
  icon?: React.ReactNode;
}

export function EmptyState({ title, message, icon }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="p-3 rounded-full bg-slate-elevated mb-4">
        {icon || <Inbox className="w-8 h-8 text-slate-muted" />}
      </div>
      {title && <h3 className="text-lg font-medium text-foreground mb-1">{title}</h3>}
      <p className="text-sm text-slate-muted max-w-sm">{message}</p>
    </div>
  );
}
