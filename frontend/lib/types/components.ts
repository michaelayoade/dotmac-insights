/**
 * Shared UI component prop types
 *
 * This file centralizes commonly used prop interfaces to prevent
 * duplicate type definitions across page files.
 *
 * Usage:
 *   import type { StatCardProps, ChartCardProps } from '@/lib/types/components';
 */

import type { LucideIcon } from 'lucide-react';

// =============================================================================
// COMMON PROPS
// =============================================================================

/** Standard loading state prop */
export interface LoadingProps {
  loading?: boolean;
  isLoading?: boolean;
}

/** Standard error state prop */
export interface ErrorProps {
  error?: Error | { status?: number; message?: string } | null;
  onRetry?: () => void;
}

/** Standard empty state configuration */
export interface EmptyStateConfig {
  title: string;
  description?: string;
  icon?: LucideIcon;
  action?: {
    label: string;
    href?: string;
    onClick?: () => void;
  };
}

// =============================================================================
// METRIC & STAT CARDS
// =============================================================================

export type StatCardVariant = 'default' | 'success' | 'warning' | 'danger' | 'info';

export interface StatCardProps {
  title: string;
  value: React.ReactNode;
  subtitle?: string;
  icon?: LucideIcon;
  trend?: {
    value: number;
    label?: string;
  };
  variant?: StatCardVariant;
  colorClass?: string;
  loading?: boolean;
  className?: string;
  animateValue?: boolean;
  href?: string;
  onClick?: () => void;
}

export interface MiniStatCardProps {
  label: string;
  value: string | number;
  icon?: LucideIcon;
  colorClass?: string;
  className?: string;
}

export interface RatioCardProps {
  title: string;
  value: string | number;
  description?: string;
  status?: 'good' | 'warning' | 'bad' | 'neutral';
  className?: string;
}

// =============================================================================
// CHART CARDS
// =============================================================================

export interface ChartCardProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  loading?: boolean;
  error?: Error | null;
  onRetry?: () => void;
  className?: string;
  action?: React.ReactNode;
}

export interface AnalyticsCardProps {
  title: string;
  children: React.ReactNode;
  className?: string;
  action?: React.ReactNode;
}

// =============================================================================
// COLLAPSIBLE SECTIONS
// =============================================================================

export interface CollapsibleSectionProps {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
  className?: string;
  badge?: string | number;
  icon?: LucideIcon;
}

// =============================================================================
// FORM COMPONENTS
// =============================================================================

export interface FormFieldProps {
  label: string;
  name: string;
  error?: string;
  required?: boolean;
  helpText?: string;
  children: React.ReactNode;
}

export interface FormErrorProps {
  error?: string;
  className?: string;
}

export interface FormErrors {
  [field: string]: string | undefined;
}

// =============================================================================
// TABLE & LIST COMPONENTS
// =============================================================================

export interface TableColumn<T = unknown> {
  key: string;
  header: string;
  render?: (item: T) => React.ReactNode;
  sortable?: boolean;
  align?: 'left' | 'center' | 'right';
  width?: string;
}

export interface PaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  pageSize?: number;
  totalItems?: number;
  className?: string;
}

export interface SortState<T extends string = string> {
  field: T;
  order: 'asc' | 'desc';
}

// =============================================================================
// SELECTION STATE
// =============================================================================

export interface SelectionState {
  selected: Set<string> | Record<string, boolean>;
  isSelected: (id: string) => boolean;
  toggle: (id: string) => void;
  selectAll: (ids: string[]) => void;
  clearAll: () => void;
  selectedCount: number;
}

// =============================================================================
// FILTER COMPONENTS
// =============================================================================

export interface FilterOption {
  value: string;
  label: string;
}

export interface DateRangeValue {
  from: Date | null;
  to: Date | null;
}

// =============================================================================
// STATUS & BADGES
// =============================================================================

export type StatusVariant = 'success' | 'warning' | 'danger' | 'info' | 'neutral';

export interface StatusBadgeProps {
  status: string;
  label?: string;
  pulse?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

// =============================================================================
// MODAL & DIALOG
// =============================================================================

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}

export interface ConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'warning' | 'default';
  loading?: boolean;
}
