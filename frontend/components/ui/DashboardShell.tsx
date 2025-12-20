'use client';

import React from 'react';
import { AlertTriangle, ShieldAlert, ServerCrash, WifiOff, Inbox, RefreshCw, LucideIcon } from 'lucide-react';
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
  /** All errors (when multiple requests fail) */
  errors?: Error[];
  /** Number of failed requests */
  errorCount?: number;
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
  /** Custom error message (overrides auto-detected message) */
  errorMessage?: string;
  /** Render children even when there is an error (shows inline error banner) */
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
  errors,
  errorCount,
  onRetry,
  isEmpty,
  emptyState,
  loadingMessage = 'Loading dashboard data...',
  errorMessage,
  softError = false,
  children,
  className,
}: DashboardShellProps) {
  if (isLoading) {
    return <DashboardLoadingState message={loadingMessage} className={className} />;
  }

  // Full-page error (blocks content)
  if (error && !softError) {
    return (
      <DashboardErrorState
        error={error}
        errors={errors}
        errorCount={errorCount}
        customMessage={errorMessage}
        onRetry={onRetry}
        className={className}
      />
    );
  }

  // Soft error mode - show inline banner + content
  if (error && softError) {
    return (
      <div className={className}>
        <DashboardErrorBanner
          error={error}
          errors={errors}
          errorCount={errorCount}
          onRetry={onRetry}
        />
        {children}
      </div>
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
// ERROR STATE - With smart detection for auth/server/network errors
// =============================================================================

interface DashboardErrorStateProps {
  error?: Error | { status?: number; message?: string } | null;
  errors?: Error[];
  errorCount?: number;
  customMessage?: string;
  onRetry?: () => void;
  className?: string;
}

type ErrorType = 'auth' | 'server' | 'network' | 'generic';

function detectErrorType(error: unknown): { type: ErrorType; status?: number } {
  if (!error || typeof error !== 'object') {
    return { type: 'generic' };
  }
  const status = 'status' in error ? (error as { status: number }).status : undefined;

  if (status === 401 || status === 403) {
    return { type: 'auth', status };
  }
  if (status === 0 || status === undefined) {
    // Network error or timeout - case-insensitive check
    const message = 'message' in error ? String((error as { message: string }).message).toLowerCase() : '';
    if (message.includes('timeout') || message.includes('network') || message.includes('fetch') || message.includes('failed to fetch')) {
      return { type: 'network', status: 0 };
    }
  }
  if (status && status >= 500) {
    return { type: 'server', status };
  }
  return { type: 'generic', status };
}

function getErrorConfig(type: ErrorType, status?: number) {
  switch (type) {
    case 'auth':
      return {
        Icon: ShieldAlert,
        title: status === 403 ? 'Access Denied' : 'Authentication Required',
        textColorClass: 'text-amber-warn',
        bgClass: 'bg-amber-warn/10 border-amber-warn/30',
        iconBgClass: 'bg-amber-warn/20',
      };
    case 'network':
      return {
        Icon: WifiOff,
        title: 'Connection Error',
        textColorClass: 'text-slate-muted',
        bgClass: 'bg-slate-elevated border-slate-border',
        iconBgClass: 'bg-slate-border',
      };
    case 'server':
      return {
        Icon: ServerCrash,
        title: 'Server Error',
        textColorClass: 'text-coral-alert',
        bgClass: 'bg-coral-alert/10 border-coral-alert/30',
        iconBgClass: 'bg-coral-alert/20',
      };
    default:
      return {
        Icon: AlertTriangle,
        title: 'Error Loading Data',
        textColorClass: 'text-coral-alert',
        bgClass: 'bg-coral-alert/10 border-coral-alert/30',
        iconBgClass: 'bg-coral-alert/20',
      };
  }
}

function getErrorMessage(error: unknown, type: ErrorType): string {
  // Get actual error message from error object
  const message = error && typeof error === 'object' && 'message' in error
    ? String((error as { message: string }).message)
    : '';

  switch (type) {
    case 'auth':
      return 'Your session may have expired or you lack permission to view this data.';
    case 'network':
      if (message.toLowerCase().includes('timeout')) {
        return 'The request took too long. Please check your connection and try again.';
      }
      return 'Unable to connect to the server. Please check your internet connection.';
    case 'server':
      return message || 'The server encountered an error. Our team has been notified.';
    default:
      return message || 'An unexpected error occurred while loading data.';
  }
}

function DashboardErrorState({
  error,
  errors,
  errorCount,
  customMessage,
  onRetry,
  className,
}: DashboardErrorStateProps) {
  const { type, status } = detectErrorType(error);
  const config = getErrorConfig(type, status);
  const { Icon, title, textColorClass, bgClass, iconBgClass } = config;

  const description = customMessage ?? getErrorMessage(error, type);
  const failedCount = errorCount || (errors?.length ?? (error ? 1 : 0));

  return (
    <div
      className={cn(
        'flex items-center justify-center min-h-[400px]',
        className
      )}
    >
      <div className={cn('max-w-md w-full rounded-xl border p-6', bgClass)}>
        <div className="flex items-start gap-4">
          <div className={cn('p-3 rounded-lg', iconBgClass)}>
            <Icon className={cn('w-6 h-6', textColorClass)} />
          </div>
          <div className="flex-1">
            <h3 className={cn('font-semibold text-lg', textColorClass)}>
              {title}
            </h3>
            <p className="text-sm text-slate-muted mt-1">{description}</p>
            {status !== undefined && status > 0 && (
              <p className="text-xs text-slate-muted mt-2">
                Error code: {status}
              </p>
            )}
            {failedCount > 1 && (
              <p className="text-xs text-slate-muted mt-1">
                {failedCount} requests failed
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
// ERROR BANNER - Inline error for soft error mode
// =============================================================================

interface DashboardErrorBannerProps {
  error?: Error | { status?: number; message?: string } | null;
  errors?: Error[];
  errorCount?: number;
  onRetry?: () => void;
}

function DashboardErrorBanner({
  error,
  errors,
  errorCount,
  onRetry,
}: DashboardErrorBannerProps) {
  const { type, status } = detectErrorType(error);
  const config = getErrorConfig(type, status);
  const { Icon, title, textColorClass } = config;

  const message = getErrorMessage(error, type);
  const failedCount = errorCount || (errors?.length ?? (error ? 1 : 0));

  return (
    <div className="mb-4 rounded-lg border bg-coral-alert/10 border-coral-alert/30 p-4">
      <div className="flex items-center gap-3">
        <Icon className={cn('w-5 h-5 flex-shrink-0', textColorClass)} />
        <div className="flex-1 min-w-0">
          <p className={cn('text-sm font-medium', textColorClass)}>
            {title}
            {failedCount > 1 && (
              <span className="text-slate-muted font-normal ml-2">
                ({failedCount} requests failed)
              </span>
            )}
          </p>
          <p className="text-xs text-slate-muted mt-0.5 truncate">{message}</p>
        </div>
        {onRetry && (
          <button
            onClick={onRetry}
            className="flex-shrink-0 flex items-center gap-1.5 px-3 py-1.5 bg-slate-elevated hover:bg-slate-border rounded text-xs text-white transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            Retry
          </button>
        )}
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
  DashboardErrorBanner,
  DashboardEmptyState,
  detectErrorType,
  getErrorMessage,
};
