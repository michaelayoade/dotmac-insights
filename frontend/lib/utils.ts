import { clsx, type ClassValue } from 'clsx';
import { getStatusVariant } from '@/lib/design-tokens';
import {
  formatCompactNumber,
  formatDate,
  formatDateTime,
  formatNumber,
  formatPercent,
  formatRelativeTime,
} from '@/lib/formatters/common';

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatCurrency(
  amount: number,
  currency = 'NGN',
  options?: Intl.NumberFormatOptions
): string {
  return new Intl.NumberFormat('en-NG', {
    style: 'currency',
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
    ...options,
  }).format(amount);
}

export {
  formatCompactNumber,
  formatDate,
  formatDateTime,
  formatNumber,
  formatPercent,
  formatRelativeTime,
};

/**
 * Maps status strings to variant names.
 * Uses the standard vocabulary: default | success | warning | danger | info
 *
 * @see lib/design-tokens.ts for the canonical STATUS_VARIANT_MAP
 */
export function getStatusColor(status: string): string {
  return getStatusVariant(status);
}

export function getInitials(name: string): string {
  return name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return `${str.slice(0, length)}...`;
}

export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;

  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout);
    timeout = setTimeout(() => func(...args), wait);
  };
}
