/**
 * Filter Presets - Common filter option configurations
 *
 * Centralizes reusable filter options for consistency across pages.
 *
 * Usage:
 *   import { BOOLEAN_OPTIONS, SORT_ORDER_OPTIONS } from '@/lib/config/filter-presets';
 *
 *   <FilterSelect>
 *     {BOOLEAN_OPTIONS.map(opt => (
 *       <option key={opt.value} value={opt.value}>{opt.label}</option>
 *     ))}
 *   </FilterSelect>
 */

import type { LucideIcon } from 'lucide-react';

// =============================================================================
// TYPES
// =============================================================================

export interface FilterOption<T = string> {
  /** Option value */
  value: T;
  /** Display label */
  label: string;
  /** Optional icon */
  icon?: LucideIcon;
  /** Optional description */
  description?: string;
}

// =============================================================================
// BOOLEAN OPTIONS
// =============================================================================

/**
 * Boolean filter with All/Yes/No options
 */
export const BOOLEAN_OPTIONS: FilterOption<string>[] = [
  { value: '', label: 'All' },
  { value: 'true', label: 'Yes' },
  { value: 'false', label: 'No' },
];

/**
 * Boolean filter with Active/Inactive options
 */
export const ACTIVE_OPTIONS: FilterOption<string>[] = [
  { value: '', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'inactive', label: 'Inactive' },
];

/**
 * Boolean filter with Enabled/Disabled options
 */
export const ENABLED_OPTIONS: FilterOption<string>[] = [
  { value: '', label: 'All' },
  { value: 'true', label: 'Enabled' },
  { value: 'false', label: 'Disabled' },
];

// =============================================================================
// SORT OPTIONS
// =============================================================================

/**
 * Sort order options
 */
export const SORT_ORDER_OPTIONS: FilterOption<string>[] = [
  { value: 'desc', label: 'Newest First' },
  { value: 'asc', label: 'Oldest First' },
];

/**
 * Alphabetical sort options
 */
export const ALPHA_SORT_OPTIONS: FilterOption<string>[] = [
  { value: 'asc', label: 'A to Z' },
  { value: 'desc', label: 'Z to A' },
];

/**
 * Amount sort options
 */
export const AMOUNT_SORT_OPTIONS: FilterOption<string>[] = [
  { value: 'desc', label: 'Highest First' },
  { value: 'asc', label: 'Lowest First' },
];

// =============================================================================
// DATE RANGE OPTIONS
// =============================================================================

/**
 * Date range preset options
 */
export const DATE_RANGE_OPTIONS: FilterOption<string>[] = [
  { value: '', label: 'All Time' },
  { value: 'today', label: 'Today' },
  { value: 'yesterday', label: 'Yesterday' },
  { value: 'this_week', label: 'This Week' },
  { value: 'last_week', label: 'Last Week' },
  { value: 'this_month', label: 'This Month' },
  { value: 'last_month', label: 'Last Month' },
  { value: 'this_quarter', label: 'This Quarter' },
  { value: 'last_quarter', label: 'Last Quarter' },
  { value: 'this_year', label: 'This Year' },
  { value: 'last_year', label: 'Last Year' },
  { value: 'custom', label: 'Custom Range' },
];

/**
 * Compact date range options
 */
export const DATE_RANGE_OPTIONS_COMPACT: FilterOption<string>[] = [
  { value: '', label: 'All Time' },
  { value: 'today', label: 'Today' },
  { value: 'this_week', label: 'This Week' },
  { value: 'this_month', label: 'This Month' },
  { value: 'custom', label: 'Custom' },
];

// =============================================================================
// LIMIT/PAGE SIZE OPTIONS
// =============================================================================

/**
 * Standard page size options
 */
export const PAGE_SIZE_OPTIONS: FilterOption<number>[] = [
  { value: 10, label: '10 per page' },
  { value: 20, label: '20 per page' },
  { value: 50, label: '50 per page' },
  { value: 100, label: '100 per page' },
];

/**
 * Compact page size options
 */
export const PAGE_SIZE_OPTIONS_COMPACT: FilterOption<number>[] = [
  { value: 20, label: '20' },
  { value: 50, label: '50' },
  { value: 100, label: '100' },
];

// =============================================================================
// VIEW OPTIONS
// =============================================================================

/**
 * View mode options (list/grid/table)
 */
export const VIEW_MODE_OPTIONS: FilterOption<string>[] = [
  { value: 'table', label: 'Table View' },
  { value: 'list', label: 'List View' },
  { value: 'grid', label: 'Grid View' },
];

/**
 * Grouping options
 */
export const GROUP_BY_OPTIONS: FilterOption<string>[] = [
  { value: '', label: 'No Grouping' },
  { value: 'status', label: 'By Status' },
  { value: 'date', label: 'By Date' },
  { value: 'category', label: 'By Category' },
];

// =============================================================================
// PRIORITY OPTIONS
// =============================================================================

/**
 * Priority filter options
 */
export const PRIORITY_OPTIONS: FilterOption<string>[] = [
  { value: '', label: 'All Priorities' },
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'urgent', label: 'Urgent' },
];

/**
 * Compact priority options
 */
export const PRIORITY_OPTIONS_COMPACT: FilterOption<string>[] = [
  { value: '', label: 'All' },
  { value: 'low', label: 'Low' },
  { value: 'high', label: 'High' },
  { value: 'urgent', label: 'Urgent' },
];

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Create select options from a string array
 */
export function createOptions(
  values: readonly string[],
  opts?: { allLabel?: string; formatLabel?: (v: string) => string }
): FilterOption<string>[] {
  const formatLabel =
    opts?.formatLabel ??
    ((v: string) =>
      v
        .replace(/[_-]/g, ' ')
        .replace(/\b\w/g, (c) => c.toUpperCase()));

  const options: FilterOption<string>[] = values.map((v) => ({
    value: v,
    label: formatLabel(v),
  }));

  if (opts?.allLabel !== undefined) {
    return [{ value: '', label: opts.allLabel }, ...options];
  }

  return options;
}

/**
 * Create numeric options (e.g., for quantity filters)
 */
export function createNumericOptions(
  values: number[],
  opts?: { allLabel?: string; suffix?: string }
): FilterOption<number | string>[] {
  const options: FilterOption<number | string>[] = values.map((v) => ({
    value: v,
    label: opts?.suffix ? `${v} ${opts.suffix}` : String(v),
  }));

  if (opts?.allLabel !== undefined) {
    return [{ value: '', label: opts.allLabel }, ...options];
  }

  return options;
}
