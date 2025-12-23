/**
 * Period Options - Shared time period configurations
 *
 * Centralizes period/date range options used across analytics pages.
 *
 * Usage:
 *   import { PERIOD_OPTIONS_SHORT, getPeriodDays } from '@/lib/config/period-options';
 */

export type PeriodValue = '7' | '14' | '30' | '60' | '90' | '180' | '365';

export interface PeriodOption {
  /** String value for select inputs */
  value: PeriodValue;
  /** Display label */
  label: string;
  /** Number of days */
  days: number;
}

// =============================================================================
// PERIOD OPTION PRESETS
// =============================================================================

/**
 * Short period options (7-90 days)
 * Use for dashboards and quick analytics views
 */
export const PERIOD_OPTIONS_SHORT: PeriodOption[] = [
  { value: '7', label: 'Last 7 days', days: 7 },
  { value: '14', label: 'Last 14 days', days: 14 },
  { value: '30', label: 'Last 30 days', days: 30 },
  { value: '60', label: 'Last 60 days', days: 60 },
  { value: '90', label: 'Last 90 days', days: 90 },
];

/**
 * Extended period options (includes 6 months and 1 year)
 * Use for reports and comprehensive analytics
 */
export const PERIOD_OPTIONS_EXTENDED: PeriodOption[] = [
  ...PERIOD_OPTIONS_SHORT,
  { value: '180', label: 'Last 6 months', days: 180 },
  { value: '365', label: 'Last year', days: 365 },
];

/**
 * Compact period options (7, 30, 90 days only)
 * Use for space-constrained UIs
 */
export const PERIOD_OPTIONS_COMPACT: PeriodOption[] = [
  { value: '7', label: '7 days', days: 7 },
  { value: '30', label: '30 days', days: 30 },
  { value: '90', label: '90 days', days: 90 },
];

// =============================================================================
// BACKWARDS COMPATIBILITY ALIASES
// =============================================================================

/**
 * @deprecated Use PERIOD_OPTIONS_SHORT instead
 */
export const INBOX_PERIOD_OPTIONS = PERIOD_OPTIONS_COMPACT;

/**
 * @deprecated Use PERIOD_OPTIONS_SHORT instead
 */
export const DAY_OPTIONS = PERIOD_OPTIONS_SHORT;

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

/**
 * Get the number of days from a period value
 */
export function getPeriodDays(value: PeriodValue | string): number {
  const option = PERIOD_OPTIONS_EXTENDED.find((o) => o.value === value);
  return option?.days ?? 30;
}

/**
 * Get a period option by value
 */
export function getPeriodOption(value: PeriodValue | string): PeriodOption | undefined {
  return PERIOD_OPTIONS_EXTENDED.find((o) => o.value === value);
}

/**
 * Calculate start date from period value
 */
export function getStartDateFromPeriod(value: PeriodValue | string): Date {
  const days = getPeriodDays(value);
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date;
}

/**
 * Format period options for select components
 */
export function formatPeriodOptions(options: PeriodOption[]): Array<{ value: string; label: string }> {
  return options.map((o) => ({ value: o.value, label: o.label }));
}
