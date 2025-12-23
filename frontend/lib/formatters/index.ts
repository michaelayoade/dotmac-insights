/**
 * Centralized formatters for consistent data display across the app.
 *
 * Usage:
 *   import { formatCurrency, formatDate, formatPercent } from '@/lib/formatters';
 */

// Re-export all common formatters
export {
  formatNumber,
  formatCompactNumber,
  formatCompactCurrency,
  formatPercent,
  formatPercentChange,
  formatRatio,
  formatDate,
  formatDateTime,
  formatRelativeTime,
} from './common';

// Re-export accounting-specific formatters
export {
  formatAccountingCurrency,
  formatAccountingCurrencyOrDash,
  formatAccountingDate,
} from './accounting';

// Re-export from utils for backwards compatibility
export { formatCurrency } from '@/lib/utils';
