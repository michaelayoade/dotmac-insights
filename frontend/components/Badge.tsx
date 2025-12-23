'use client';

import { cn } from '@/lib/utils';
import {
  VARIANT_COLORS,
  getStatusVariant,
  formatStatusLabel,
  type Variant,
} from '@/lib/design-tokens';

interface BadgeProps {
  children: React.ReactNode;
  variant?: Variant;
  size?: 'sm' | 'md';
  pulse?: boolean;
  className?: string;
}

export function Badge({
  children,
  variant = 'default',
  size = 'md',
  pulse = false,
  className,
}: BadgeProps) {
  const colors = VARIANT_COLORS[variant];
  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-xs',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 font-medium rounded-full border',
        colors.bg,
        colors.text,
        colors.border,
        sizes[size],
        className
      )}
    >
      {pulse && (
        <span className="relative flex h-2 w-2">
          <span
            className={cn(
              'animate-ping absolute inline-flex h-full w-full rounded-full opacity-75',
              colors.pulse
            )}
          />
          <span
            className={cn(
              'relative inline-flex rounded-full h-2 w-2',
              colors.pulse
            )}
          />
        </span>
      )}
      {children}
    </span>
  );
}

interface StatusBadgeProps {
  status: string | null | undefined;
  pulse?: boolean;
  size?: 'sm' | 'md';
  /** Override the displayed label */
  label?: string;
  className?: string;
}

/**
 * Auto-variant badge based on status string.
 * Automatically determines color variant and formats the label.
 */
export function StatusBadge({
  status,
  pulse,
  size = 'md',
  label,
  className,
}: StatusBadgeProps) {
  const variant = getStatusVariant(status || '');
  const displayLabel = label ?? formatStatusLabel(status);

  return (
    <Badge variant={variant} pulse={pulse} size={size} className={className}>
      {displayLabel}
    </Badge>
  );
}
