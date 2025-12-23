'use client';

import { cn } from '@/lib/utils';
import { AlertTriangle, ArrowUpDown, Loader2, RefreshCw, TrendingDown, TrendingUp } from 'lucide-react';
import { Button } from '@/components/ui';
import type { SortOrder } from '@/hooks/useTableSort';

interface MetricCardProps {
  label: string;
  value: string | number;
  icon: React.ElementType;
  colorClass?: string;
  isLoading?: boolean;
  change?: number;
  changeLabel?: string;
  iconWrapperClassName?: string;
}

export function MetricCard({
  label,
  value,
  change,
  changeLabel,
  icon: Icon,
  colorClass = 'text-blue-400',
  isLoading = false,
  iconWrapperClassName = 'bg-slate-elevated',
}: MetricCardProps) {
  const isPositive = change !== undefined && change > 0;
  const isNegative = change !== undefined && change < 0;
  const displayValue = typeof value === 'number' ? value.toLocaleString() : value;

  return (
    <div className="bg-slate-card border border-slate-border rounded-xl p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-muted text-sm">{label}</p>
          {isLoading ? (
            <div className="h-9 w-20 bg-slate-elevated rounded mt-1 animate-pulse" />
          ) : (
            <p className={cn('text-3xl font-bold mt-1', colorClass)}>{displayValue}</p>
          )}
          {change !== undefined && !isLoading && (
            <div className="flex items-center gap-1 mt-2">
              {isPositive && <TrendingUp className="w-3 h-3 text-emerald-400" />}
              {isNegative && <TrendingDown className="w-3 h-3 text-rose-400" />}
              <span
                className={cn(
                  'text-xs',
                  isPositive ? 'text-emerald-400' : isNegative ? 'text-rose-400' : 'text-slate-muted'
                )}
              >
                {isPositive ? '+' : ''}{change}% {changeLabel}
              </span>
            </div>
          )}
        </div>
        <div className={cn('p-3 rounded-xl', iconWrapperClassName)}>
          <Icon className={cn('w-6 h-6', colorClass)} />
        </div>
      </div>
    </div>
  );
}

export function ChartSkeleton({ height = 250 }: { height?: number }) {
  return (
    <div className="flex items-center justify-center" style={{ height }}>
      <Loader2 className="w-8 h-8 animate-spin text-slate-muted" />
    </div>
  );
}

export function ChartErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-48 text-slate-muted">
      <AlertTriangle className="w-8 h-8 mb-2 text-rose-400" />
      <p className="text-sm text-rose-400 mb-3">{message}</p>
      {onRetry && (
        <Button
          onClick={onRetry}
          className="flex items-center gap-2 px-3 py-1.5 bg-slate-elevated hover:bg-slate-border rounded-lg text-xs text-foreground transition-colors"
        >
          <RefreshCw className="w-3 h-3" />
          Retry
        </Button>
      )}
    </div>
  );
}

// =============================================================================
// ANALYTICS CARD
// =============================================================================

interface AnalyticsCardProps {
  title: string;
  children: React.ReactNode;
  className?: string;
  /** Optional action button in header */
  action?: React.ReactNode;
}

/**
 * Standard card wrapper for analytics content (charts, tables, etc.)
 */
export function AnalyticsCard({ title, children, className, action }: AnalyticsCardProps) {
  return (
    <div className={cn('bg-slate-card border border-slate-border rounded-xl', className)}>
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-border">
        <h3 className="text-foreground font-semibold">{title}</h3>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

// =============================================================================
// NO DATA FALLBACK
// =============================================================================

interface NoDataFallbackProps {
  message?: string;
  height?: number;
  icon?: React.ElementType;
}

/**
 * Empty state for when no data is available.
 */
export function NoDataFallback({
  message = 'No data available',
  height = 250,
  icon: Icon,
}: NoDataFallbackProps) {
  return (
    <div
      className="flex flex-col items-center justify-center text-slate-muted"
      style={{ height }}
    >
      {Icon && <Icon className="w-8 h-8 mb-2 opacity-50" />}
      <p className="text-sm">{message}</p>
    </div>
  );
}

// =============================================================================
// SORTABLE TABLE HEADER
// =============================================================================

interface SortHeaderProps<T extends string> {
  field: T;
  currentField: T;
  sortOrder: SortOrder;
  onSort: (field: T) => void;
  children: React.ReactNode;
  className?: string;
}

/**
 * Clickable table header cell with sort indicator.
 */
export function SortHeader<T extends string>({
  field,
  currentField,
  sortOrder,
  onSort,
  children,
  className,
}: SortHeaderProps<T>) {
  const isActive = field === currentField;

  return (
    <th
      onClick={() => onSort(field)}
      className={cn(
        'py-3 px-4 text-left text-sm font-medium text-slate-muted cursor-pointer hover:text-foreground transition-colors',
        className
      )}
    >
      <div className="flex items-center gap-1">
        {children}
        <ArrowUpDown
          className={cn(
            'w-3.5 h-3.5 transition-colors',
            isActive ? 'text-blue-400' : 'opacity-50'
          )}
        />
        {isActive && (
          <span className="sr-only">
            {sortOrder === 'asc' ? 'sorted ascending' : 'sorted descending'}
          </span>
        )}
      </div>
    </th>
  );
}

// =============================================================================
// RANKING BADGE
// =============================================================================

interface RankingBadgeProps {
  rank: number;
  className?: string;
}

/**
 * Circular badge showing rank position (1st = gold, 2nd = silver, 3rd = bronze).
 */
export function RankingBadge({ rank, className }: RankingBadgeProps) {
  return (
    <div
      className={cn(
        'w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold',
        rank === 1 && 'bg-amber-500/20 text-amber-400',
        rank === 2 && 'bg-slate-400/20 text-slate-300',
        rank === 3 && 'bg-amber-700/20 text-amber-600',
        rank > 3 && 'bg-slate-elevated text-slate-muted',
        className
      )}
    >
      {rank}
    </div>
  );
}

// =============================================================================
// PROGRESS BAR
// =============================================================================

interface ProgressBarProps {
  value: number;
  max?: number;
  colorClass?: string;
  className?: string;
}

/**
 * Simple horizontal progress bar.
 */
export function ProgressBar({
  value,
  max = 100,
  colorClass = 'bg-blue-500',
  className,
}: ProgressBarProps) {
  const percentage = Math.min((value / max) * 100, 100);

  return (
    <div className={cn('h-2 bg-slate-elevated rounded-full overflow-hidden', className)}>
      <div
        className={cn('h-full rounded-full transition-all', colorClass)}
        style={{ width: `${percentage}%` }}
      />
    </div>
  );
}
