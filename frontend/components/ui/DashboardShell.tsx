'use client';

import React from 'react';
import { AlertTriangle, ShieldAlert, ServerCrash, Inbox, RefreshCw, LucideIcon } from 'lucide-react';
import Link from 'next/link';
import { cn } from '@/lib/utils';

// =============================================================================
// DASHBOARD SHELL - Unified loading/error/empty state wrapper
// =============================================================================

export interface DashboardShellProps {
  /** Whether data is currently loading */
  isLoading: boolean;
  /** Error object if there was an error */
  error?: Error | { status?: number; message?: string } | null;
  /** Callback to retry fetching data */
  onRetry?: () => void;
  /** Whether the data is empty */
  isEmpty?: boolean;
  /** Empty state configuration */
  emptyState?: {
    title: string;
    description?: string;
    icon?: LucideIcon;
    action?: {
      label: string;
      href?: string;
      onClick?: () => void;
    };
  };
  /** Custom loading message */
  loadingMessage?: string;
  /** Custom error message */
  errorMessage?: string;
  /** Render children even when there is an error */
  softError?: boolean;
  /** Children to render when loaded */
  children: React.ReactNode;
  /** Additional CSS classes */
  className?: string;
}

/**
 * DashboardShell handles loading, error, and empty states for dashboard pages.
 * It provides a consistent UX across all dashboards with smart error detection.
 *
 * @example
 * const { isLoading, error, retry } = useSWRStatus(customers, orders);
 *
 * return (
 *   <DashboardShell
 *     isLoading={isLoading}
 *     error={error}
 *     onRetry={retry}
 *     isEmpty={customers.data?.length === 0}
 *     emptyState={{
 *       title: 'No customers yet',
 *       description: 'Add your first customer to get started.',
 *       action: { label: 'Add Customer', href: '/customers/new' }
 *     }}
 *   >
 *     <CustomerDashboard data={customers.data} />
 *   </DashboardShell>
 * );
 */
export function DashboardShell({
  isLoading,
  error,
  onRetry,
  isEmpty,
  emptyState,
  loadingMessage = 'Loading dashboard data...',
  errorMessage = 'Failed to load dashboard data',
  softError = false,
  children,
  className,
}: DashboardShellProps) {
  if (isLoading) {
    return <DashboardLoadingState message={loadingMessage} className={className} />;
  }

  if (error && !softError) {
    return (
      <DashboardErrorState
        message={errorMessage}
        error={error}
        onRetry={onRetry}
        className={className}
      />
    );
  }

  if (isEmpty && emptyState) {
    return <DashboardEmptyState {...emptyState} className={className} />;
  }

  return <>{children}</>;
}

// =============================================================================
// LOADING STATE
// =============================================================================

interface DashboardLoadingStateProps {
  message?: string;
  className?: string;
}

function DashboardLoadingState({
  message = 'Loading...',
  className,
}: DashboardLoadingStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center min-h-[400px]',
        className
      )}
    >
      <div className="w-10 h-10 border-2 border-teal-electric border-t-transparent rounded-full animate-spin mb-4" />
      <p className="text-sm text-slate-muted">{message}</p>
    </div>
  );
}

// =============================================================================
// ERROR STATE - With smart detection for auth/server errors
// =============================================================================

interface DashboardErrorStateProps {
  message: string;
  error?: Error | { status?: number; message?: string } | null;
  onRetry?: () => void;
  className?: string;
}

function DashboardErrorState({
  message,
  error,
  onRetry,
  className,
}: DashboardErrorStateProps) {
  // Detect error type from status code
  const status =
    error && typeof error === 'object' && 'status' in error
      ? error.status
      : undefined;
  const isAuthError = status === 401 || status === 403;
  const isServerError = status && status >= 500;

  const Icon = isAuthError
    ? ShieldAlert
    : isServerError
    ? ServerCrash
    : AlertTriangle;

  const title = isAuthError
    ? 'Authentication Required'
    : isServerError
    ? 'Server Error'
    : 'Error Loading Data';

  const description = isAuthError
    ? 'Your session may have expired or you lack permission to view this data.'
    : message;

  return (
    <div
      className={cn(
        'flex items-center justify-center min-h-[400px]',
        className
      )}
    >
      <div
        className={cn(
          'max-w-md w-full rounded-xl border p-6',
          isAuthError
            ? 'bg-amber-warn/10 border-amber-warn/30'
            : 'bg-coral-alert/10 border-coral-alert/30'
        )}
      >
        <div className="flex items-start gap-4">
          <div
            className={cn(
              'p-3 rounded-lg',
              isAuthError ? 'bg-amber-warn/20' : 'bg-coral-alert/20'
            )}
          >
            <Icon
              className={cn(
                'w-6 h-6',
                isAuthError ? 'text-amber-warn' : 'text-coral-alert'
              )}
            />
          </div>
          <div className="flex-1">
            <h3
              className={cn(
                'font-semibold text-lg',
                isAuthError ? 'text-amber-warn' : 'text-coral-alert'
              )}
            >
              {title}
            </h3>
            <p className="text-sm text-slate-muted mt-1">{description}</p>
            {status && (
              <p className="text-xs text-slate-muted mt-2">
                Error code: {status}
              </p>
            )}
            {onRetry && (
              <button
                onClick={onRetry}
                className="mt-4 flex items-center gap-2 px-4 py-2 bg-slate-elevated hover:bg-slate-border rounded-lg text-sm text-white transition-colors"
              >
                <RefreshCw className="w-4 h-4" />
                Try again
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// EMPTY STATE
// =============================================================================

interface DashboardEmptyStateProps {
  title: string;
  description?: string;
  icon?: LucideIcon;
  action?: {
    label: string;
    href?: string;
    onClick?: () => void;
  };
  className?: string;
}

function DashboardEmptyState({
  title,
  description,
  icon: Icon = Inbox,
  action,
  className,
}: DashboardEmptyStateProps) {
  return (
    <div
      className={cn(
        'flex items-center justify-center min-h-[400px]',
        className
      )}
    >
      <div className="bg-slate-card border border-slate-border rounded-xl p-8 max-w-md w-full text-center">
        <div className="w-16 h-16 rounded-full bg-slate-elevated flex items-center justify-center mx-auto mb-4">
          <Icon className="w-8 h-8 text-slate-muted" />
        </div>
        <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
        {description && (
          <p className="text-sm text-slate-muted mb-6">{description}</p>
        )}
        {action && (
          action.href ? (
            <Link
              href={action.href}
              className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-teal-electric to-teal-glow text-white font-medium rounded-lg hover:shadow-lg hover:shadow-teal-electric/25 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-electric"
            >
              {action.label}
            </Link>
          ) : (
            <button
              onClick={action.onClick}
              className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-teal-electric to-teal-glow text-white font-medium rounded-lg hover:shadow-lg hover:shadow-teal-electric/25 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-electric"
            >
              {action.label}
            </button>
          )
        )}
      </div>
    </div>
  );
}

export {
  DashboardLoadingState,
  DashboardErrorState,
  DashboardEmptyState,
};
