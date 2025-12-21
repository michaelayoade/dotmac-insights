'use client';

import { ArrowLeft } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';

export interface BackButtonProps {
  /**
   * The destination URL. If not provided, uses router.back()
   */
  href?: string;
  /**
   * Label to show after "Back to". E.g., "invoices" renders "Back to invoices"
   * If not provided, just shows "Back"
   */
  label?: string;
  /**
   * Optional className for custom styling
   */
  className?: string;
  /**
   * Size variant
   */
  size?: 'sm' | 'md';
}

/**
 * Standardized back button component for consistent navigation across the app.
 *
 * Usage:
 * ```tsx
 * // With explicit href (preferred)
 * <BackButton href="/sales/invoices" label="invoices" />
 *
 * // Fallback to router.back()
 * <BackButton label="invoices" />
 *
 * // Simple back button
 * <BackButton />
 * ```
 */
export function BackButton({
  href,
  label,
  className,
  size = 'md',
}: BackButtonProps) {
  const router = useRouter();

  const sizeClasses = {
    sm: 'px-2 py-1 text-xs gap-1',
    md: 'px-3 py-2 text-sm gap-2',
  };

  const iconSizes = {
    sm: 'w-3 h-3',
    md: 'w-4 h-4',
  };

  const buttonClasses = cn(
    'inline-flex items-center rounded-md border border-slate-border',
    'text-slate-muted hover:text-foreground hover:border-slate-muted/50',
    'transition-colors focus-visible:outline-none focus-visible:ring-2',
    'focus-visible:ring-teal-electric focus-visible:ring-offset-2',
    'focus-visible:ring-offset-slate-deep',
    sizeClasses[size],
    className
  );

  const content = (
    <>
      <ArrowLeft className={iconSizes[size]} />
      {label ? `Back to ${label}` : 'Back'}
    </>
  );

  // Prefer Link for explicit hrefs (better for SEO and browser history)
  if (href) {
    return (
      <Link href={href} className={buttonClasses}>
        {content}
      </Link>
    );
  }

  // Fallback to router.back() when no href provided
  return (
    <button onClick={() => router.back()} className={buttonClasses}>
      {content}
    </button>
  );
}
