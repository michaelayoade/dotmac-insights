import { formatCurrency } from '@/lib/utils';

export function formatAccountingCurrency(
  value: number | null | undefined,
  currency = 'NGN'
): string {
  if (value === null || value === undefined) return '₦0';
  return formatCurrency(value, currency);
}

export function formatAccountingCurrencyOrDash(
  value: number | null | undefined,
  currency = 'NGN'
): string {
  if (value === null || value === undefined) return '-';
  return formatCurrency(value, currency);
}

export function formatAccountingDate(date: string | null | undefined): string {
  if (!date) return '-';
  return new Date(date).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}
