'use client';

import { cn } from '@/lib/utils';
import { getStatusColor } from '@/lib/utils';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
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
  const variants = {
    default: 'bg-slate-elevated text-slate-muted border-slate-border',
    success: 'bg-teal-electric/15 text-teal-electric border-teal-electric/30',
    warning: 'bg-amber-warn/15 text-amber-warn border-amber-warn/30',
    danger: 'bg-coral-alert/15 text-coral-alert border-coral-alert/30',
    info: 'bg-blue-info/15 text-blue-info border-blue-info/30',
  };

  const sizes = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-2.5 py-1 text-xs',
  };

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 font-medium rounded-full border',
        variants[variant],
        sizes[size],
        className
      )}
    >
      {pulse && (
        <span className="relative flex h-2 w-2">
          <span
            className={cn(
              'animate-ping absolute inline-flex h-full w-full rounded-full opacity-75',
              variant === 'success' && 'bg-teal-electric',
              variant === 'warning' && 'bg-amber-warn',
              variant === 'danger' && 'bg-coral-alert',
              variant === 'info' && 'bg-blue-info',
              variant === 'default' && 'bg-slate-muted'
            )}
          />
          <span
            className={cn(
              'relative inline-flex rounded-full h-2 w-2',
              variant === 'success' && 'bg-teal-electric',
              variant === 'warning' && 'bg-amber-warn',
              variant === 'danger' && 'bg-coral-alert',
              variant === 'info' && 'bg-blue-info',
              variant === 'default' && 'bg-slate-muted'
            )}
          />
        </span>
      )}
      {children}
    </span>
  );
}

// Auto-variant badge based on status string
export function StatusBadge({
  status,
  pulse,
  size = 'md',
}: {
  status: string;
  pulse?: boolean;
  size?: 'sm' | 'md';
}) {
  const variant = getStatusColor(status) as 'success' | 'warning' | 'danger' | 'info' | 'default';

  return (
    <Badge variant={variant} pulse={pulse} size={size}>
      {status.replace(/_/g, ' ')}
    </Badge>
  );
}
