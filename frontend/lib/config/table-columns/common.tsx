'use client';

import { cn } from '@/lib/utils';
import { formatCurrency, formatDate, formatNumber } from '@/lib/formatters';
import { getStatusVariant, formatStatusLabel } from '@/lib/design-tokens';
import { StatusPill } from '@/components/ui';
import type { TableColumn } from '@/lib/types/components';

// =============================================================================
// COLUMN OPTIONS
// =============================================================================

export interface ColumnOptions<T = unknown> {
  /** Include only these columns by key */
  include?: string[];
  /** Exclude these columns by key */
  exclude?: string[];
  /** Override specific column properties */
  overrides?: Record<string, Partial<TableColumn<T>>>;
}

/**
 * Apply column options to a column array
 */
export function applyColumnOptions<T>(
  columns: TableColumn<T>[],
  options?: ColumnOptions<T>
): TableColumn<T>[] {
  if (!options) return columns;

  let result = [...columns];

  // Filter by include
  if (options.include && options.include.length > 0) {
    result = result.filter((c) => options.include!.includes(c.key));
  }

  // Filter by exclude
  if (options.exclude && options.exclude.length > 0) {
    result = result.filter((c) => !options.exclude!.includes(c.key));
  }

  // Apply overrides
  if (options.overrides) {
    result = result.map((c) => {
      const override = options.overrides![c.key];
      if (override) {
        return { ...c, ...override } as TableColumn<T>;
      }
      return c;
    });
  }

  return result;
}

// =============================================================================
// COMMON COLUMN BUILDERS
// =============================================================================

/**
 * Common column factory functions for consistent rendering across tables.
 */
export const commonColumns = {
  /**
   * Date column with consistent formatting
   */
  date: <T extends Record<string, unknown>>(
    key: string,
    header: string,
    opts?: { sortable?: boolean }
  ): TableColumn<T> => ({
    key,
    header,
    sortable: opts?.sortable ?? true,
    render: (item) => (
      <span className="text-slate-muted">
        {formatDate(item[key] as string | null | undefined)}
      </span>
    ),
  }),

  /**
   * Currency column with right alignment
   */
  currency: <T extends Record<string, unknown>>(
    key: string,
    header: string,
    opts?: {
      sortable?: boolean;
      colorClass?: string;
      showPositiveGreen?: boolean;
      showNegativeRed?: boolean;
    }
  ): TableColumn<T> => ({
    key,
    header,
    align: 'right',
    sortable: opts?.sortable ?? true,
    render: (item) => {
      const value = item[key] as number | null | undefined;
      let colorClass = opts?.colorClass || 'text-foreground';

      if (opts?.showPositiveGreen && value && value > 0) {
        colorClass = 'text-green-400';
      } else if (opts?.showNegativeRed && value && value < 0) {
        colorClass = 'text-red-400';
      }

      return (
        <span className={cn('font-mono', colorClass)}>
          {formatCurrency(value ?? 0)}
        </span>
      );
    },
  }),

  /**
   * Number column with optional formatting
   */
  number: <T extends Record<string, unknown>>(
    key: string,
    header: string,
    opts?: { sortable?: boolean; colorClass?: string }
  ): TableColumn<T> => ({
    key,
    header,
    align: 'right',
    sortable: opts?.sortable ?? true,
    render: (item) => (
      <span className={cn('font-mono', opts?.colorClass || 'text-foreground')}>
        {formatNumber(item[key] as number | null | undefined)}
      </span>
    ),
  }),

  /**
   * Status pill column with automatic variant detection
   */
  status: <T extends Record<string, unknown>>(
    key = 'status',
    header = 'Status'
  ): TableColumn<T> => ({
    key,
    header,
    render: (item) => {
      const status = item[key] as string;
      if (!status) return <span className="text-slate-muted">-</span>;
      return (
        <StatusPill
          label={formatStatusLabel(status)}
          tone={getStatusVariant(status)}
        />
      );
    },
  }),

  /**
   * Text column with optional truncation
   */
  text: <T extends Record<string, unknown>>(
    key: string,
    header: string,
    opts?: { sortable?: boolean; maxWidth?: string; className?: string }
  ): TableColumn<T> => ({
    key,
    header,
    sortable: opts?.sortable ?? false,
    render: (item) => (
      <span
        className={cn(
          'text-foreground',
          opts?.maxWidth && 'truncate block',
          opts?.className
        )}
        style={opts?.maxWidth ? { maxWidth: opts.maxWidth } : undefined}
      >
        {(item[key] as string) || '-'}
      </span>
    ),
  }),

  /**
   * Code/ID column with monospace font
   */
  code: <T extends Record<string, unknown>>(
    key: string,
    header: string,
    opts?: { sortable?: boolean; colorClass?: string }
  ): TableColumn<T> => ({
    key,
    header,
    sortable: opts?.sortable ?? true,
    render: (item) => (
      <span className={cn('font-mono', opts?.colorClass || 'text-teal-electric')}>
        {(item[key] as string) || '-'}
      </span>
    ),
  }),

  /**
   * Boolean column with yes/no display
   */
  boolean: <T extends Record<string, unknown>>(
    key: string,
    header: string,
    opts?: { yesLabel?: string; noLabel?: string }
  ): TableColumn<T> => ({
    key,
    header,
    render: (item) => {
      const value = item[key] as boolean;
      return (
        <span className={value ? 'text-green-400' : 'text-slate-muted'}>
          {value ? (opts?.yesLabel || 'Yes') : (opts?.noLabel || 'No')}
        </span>
      );
    },
  }),

  /**
   * Actions column placeholder (for custom actions)
   */
  actions: <T extends Record<string, unknown>>(
    render: (item: T) => React.ReactNode
  ): TableColumn<T> => ({
    key: 'actions',
    header: '',
    align: 'right',
    width: '100px',
    render,
  }),
};

// =============================================================================
// COLOR HELPERS
// =============================================================================

/**
 * Get account type color class for accounting tables
 */
export const getAccountTypeColor = (type: string | null | undefined): string => {
  const colors: Record<string, string> = {
    asset: 'text-blue-400',
    liability: 'text-red-400',
    equity: 'text-green-400',
    income: 'text-teal-400',
    revenue: 'text-teal-400',
    expense: 'text-orange-400',
  };
  return colors[type?.toLowerCase() || ''] || 'text-slate-muted';
};

/**
 * Get account type badge color classes for accounting tables
 */
export const getAccountTypeBadgeColor = (type: string | null | undefined): string => {
  const colors: Record<string, string> = {
    asset: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    liability: 'bg-red-500/20 text-red-400 border-red-500/30',
    equity: 'bg-green-500/20 text-green-400 border-green-500/30',
    income: 'bg-teal-500/20 text-teal-400 border-teal-500/30',
    revenue: 'bg-teal-500/20 text-teal-400 border-teal-500/30',
    expense: 'bg-orange-500/20 text-orange-400 border-orange-500/30',
  };
  return colors[type?.toLowerCase() || ''] || 'bg-slate-500/20 text-slate-400 border-slate-500/30';
};
