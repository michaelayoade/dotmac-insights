export function formatNumber(
  num: number | null | undefined,
  options?: Intl.NumberFormatOptions
): string {
  if (num === null || num === undefined) return '0';
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 1,
    ...options,
  }).format(num);
}

export function formatCompactNumber(num: number | null | undefined): string {
  if (num === null || num === undefined) return '0';
  const abs = Math.abs(num);
  const sign = num < 0 ? '-' : '';
  if (abs >= 1_000_000_000) return `${sign}${(abs / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${sign}${(abs / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${sign}${(abs / 1_000).toFixed(1)}K`;
  return `${sign}${abs.toString()}`;
}

/**
 * Format currency with compact notation (K, M, B suffixes).
 * @param value - The numeric value
 * @param currency - Currency code (default: NGN)
 * @param symbol - Currency symbol (default: ₦)
 */
export function formatCompactCurrency(
  value: number | null | undefined,
  currency = 'NGN',
  symbol = '₦'
): string {
  if (value === null || value === undefined) return `${symbol}0`;
  const abs = Math.abs(value);
  const formatter = new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    notation: 'compact',
    maximumFractionDigits: 1,
  });
  const formatted = formatter.formatToParts(abs).map((part) => {
    if (part.type === 'currency' && symbol) return symbol;
    return part.value;
  }).join('');
  return value < 0 ? `-${formatted}` : formatted;
}

export function formatPercent(
  value: number | null | undefined,
  decimals = 1
): string {
  if (value === null || value === undefined) return '0%';
  return `${value.toFixed(decimals)}%`;
}

/**
 * Format a ratio value (e.g., 1.5, 2.0).
 */
export function formatRatio(
  value: number | null | undefined,
  decimals = 2
): string {
  if (value === null || value === undefined) return '0.00';
  return value.toFixed(decimals);
}

/**
 * Format a percentage change with + prefix for positive values.
 */
export function formatPercentChange(
  value: number | null | undefined,
  decimals = 1
): string {
  if (value === null || value === undefined) return '0%';
  const prefix = value > 0 ? '+' : '';
  return `${prefix}${value.toFixed(decimals)}%`;
}

export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return '—';
  const date = new Date(dateString);
  return date.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export function formatDateTime(dateString: string | null | undefined): string {
  if (!dateString) return '—';
  const date = new Date(dateString);
  return date.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatRelativeTime(dateString: string | null | undefined): string {
  if (!dateString) return '—';

  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`;
  return formatDate(dateString);
}
