/**
 * Central type exports
 *
 * Usage:
 *   import type { StatCardProps, FormErrors, TableColumn } from '@/lib/types';
 */

export type {
  // Common props
  LoadingProps,
  ErrorProps,
  EmptyStateConfig,
  // Stat/Metric cards
  StatCardVariant,
  StatCardProps,
  MiniStatCardProps,
  RatioCardProps,
  // Chart cards
  ChartCardProps,
  AnalyticsCardProps,
  // Collapsible sections
  CollapsibleSectionProps,
  // Form components
  FormFieldProps,
  FormErrorProps,
  FormErrors,
  // Table/List components
  TableColumn,
  PaginationProps,
  SortState,
  // Selection state
  SelectionState,
  // Filter components
  FilterOption,
  DateRangeValue,
  // Status & Badges
  StatusVariant,
  StatusBadgeProps,
  // Modal & Dialog
  ModalProps,
  ConfirmDialogProps,
} from './components';
