'use client';

import { useState, useEffect, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { Clock, AlertTriangle } from 'lucide-react';
import { VARIANT_COLORS, type Variant } from '@/lib/design-tokens';

// =============================================================================
// COUNTDOWN TIMER
// =============================================================================

export interface CountdownTimerProps {
  /** Target date/time to count down to */
  targetDate: Date | string;
  /** Callback when timer expires */
  onExpire?: () => void;
  /** Show days in the countdown */
  showDays?: boolean;
  /** Show seconds in the countdown */
  showSeconds?: boolean;
  /** Urgency thresholds in minutes - changes color based on time remaining */
  urgencyThresholds?: {
    warning: number; // Minutes until warning color
    danger: number; // Minutes until danger color
  };
  /** Override automatic variant based on urgency */
  variant?: Variant;
  /** Size preset */
  size?: 'sm' | 'md' | 'lg';
  /** Show icon */
  showIcon?: boolean;
  /** Label to show before the time */
  label?: string;
  /** Show "Expired" text when timer ends */
  showExpiredText?: boolean;
  /** Custom expired text */
  expiredText?: string;
  /** Custom class name */
  className?: string;
}

interface TimeRemaining {
  days: number;
  hours: number;
  minutes: number;
  seconds: number;
  totalMinutes: number;
  isExpired: boolean;
}

function calculateTimeRemaining(targetDate: Date | string): TimeRemaining {
  const target = typeof targetDate === 'string' ? new Date(targetDate) : targetDate;
  const now = new Date();
  const diff = target.getTime() - now.getTime();

  if (diff <= 0) {
    return { days: 0, hours: 0, minutes: 0, seconds: 0, totalMinutes: 0, isExpired: true };
  }

  const totalSeconds = Math.floor(diff / 1000);
  const totalMinutes = Math.floor(totalSeconds / 60);
  const days = Math.floor(totalMinutes / 1440);
  const hours = Math.floor((totalMinutes % 1440) / 60);
  const minutes = totalMinutes % 60;
  const seconds = totalSeconds % 60;

  return { days, hours, minutes, seconds, totalMinutes, isExpired: false };
}

const SIZES = {
  sm: { text: 'text-xs', icon: 'w-3 h-3', gap: 'gap-1' },
  md: { text: 'text-sm', icon: 'w-4 h-4', gap: 'gap-1.5' },
  lg: { text: 'text-base', icon: 'w-5 h-5', gap: 'gap-2' },
};

export function CountdownTimer({
  targetDate,
  onExpire,
  showDays = true,
  showSeconds = true,
  urgencyThresholds = { warning: 60, danger: 15 },
  variant: variantProp,
  size = 'md',
  showIcon = true,
  label,
  showExpiredText = true,
  expiredText = 'Expired',
  className,
}: CountdownTimerProps) {
  const [timeRemaining, setTimeRemaining] = useState<TimeRemaining>(() =>
    calculateTimeRemaining(targetDate)
  );

  useEffect(() => {
    const interval = setInterval(() => {
      const remaining = calculateTimeRemaining(targetDate);
      setTimeRemaining(remaining);

      if (remaining.isExpired) {
        clearInterval(interval);
        onExpire?.();
      }
    }, 1000);

    return () => clearInterval(interval);
  }, [targetDate, onExpire]);

  // Determine variant based on urgency
  const variant = useMemo<Variant>(() => {
    if (variantProp) return variantProp;
    if (timeRemaining.isExpired) return 'danger';
    if (timeRemaining.totalMinutes <= urgencyThresholds.danger) return 'danger';
    if (timeRemaining.totalMinutes <= urgencyThresholds.warning) return 'warning';
    return 'default';
  }, [variantProp, timeRemaining, urgencyThresholds]);

  const colors = VARIANT_COLORS[variant];
  const sizeConfig = SIZES[size];

  // Format time parts with leading zeros
  const pad = (n: number) => n.toString().padStart(2, '0');

  // Build time string
  const formatTime = (): string => {
    if (timeRemaining.isExpired) {
      return showExpiredText ? expiredText : '00:00';
    }

    const parts: string[] = [];

    if (showDays && timeRemaining.days > 0) {
      parts.push(`${timeRemaining.days}d`);
    }

    parts.push(`${pad(timeRemaining.hours)}:${pad(timeRemaining.minutes)}`);

    if (showSeconds) {
      parts[parts.length - 1] += `:${pad(timeRemaining.seconds)}`;
    }

    return parts.join(' ');
  };

  const Icon = timeRemaining.isExpired || variant === 'danger' ? AlertTriangle : Clock;

  return (
    <span
      className={cn(
        'inline-flex items-center font-medium',
        sizeConfig.gap,
        sizeConfig.text,
        colors.text,
        className
      )}
    >
      {showIcon && <Icon className={sizeConfig.icon} />}
      {label && <span>{label}</span>}
      <span className="font-mono">{formatTime()}</span>
    </span>
  );
}

// =============================================================================
// SLA TIMER (Pre-configured for SLA use cases)
// =============================================================================

export interface SLATimerProps extends Omit<CountdownTimerProps, 'urgencyThresholds' | 'showDays'> {
  /** Type of SLA timer */
  type?: 'response' | 'resolution';
  /** Show badge style */
  badge?: boolean;
}

export function SLATimer({
  type = 'resolution',
  badge = false,
  ...props
}: SLATimerProps) {
  const urgencyThresholds = type === 'response'
    ? { warning: 30, danger: 10 }
    : { warning: 60, danger: 15 };

  const timer = (
    <CountdownTimer
      {...props}
      urgencyThresholds={urgencyThresholds}
      showDays={false}
      label={type === 'response' ? 'Response:' : 'Resolution:'}
    />
  );

  if (badge) {
    return (
      <span className="inline-flex items-center px-2 py-1 rounded-full bg-slate-elevated">
        {timer}
      </span>
    );
  }

  return timer;
}

// =============================================================================
// DEADLINE BADGE (Shows time remaining as a badge)
// =============================================================================

export interface DeadlineBadgeProps {
  /** Target deadline */
  deadline: Date | string;
  /** Show full date if more than this many days away */
  fullDateThreshold?: number;
  /** Date formatter for full date display */
  formatDate?: (date: Date) => string;
  /** Custom class name */
  className?: string;
}

export function DeadlineBadge({
  deadline,
  fullDateThreshold = 7,
  formatDate = (d) => d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
  className,
}: DeadlineBadgeProps) {
  const timeRemaining = calculateTimeRemaining(deadline);
  const targetDate = typeof deadline === 'string' ? new Date(deadline) : deadline;

  // Determine display and variant
  let display: string;
  let variant: Variant;

  if (timeRemaining.isExpired) {
    display = 'Overdue';
    variant = 'danger';
  } else if (timeRemaining.days > fullDateThreshold) {
    display = formatDate(targetDate);
    variant = 'default';
  } else if (timeRemaining.days > 0) {
    display = `${timeRemaining.days}d left`;
    variant = timeRemaining.days <= 2 ? 'warning' : 'default';
  } else if (timeRemaining.hours > 0) {
    display = `${timeRemaining.hours}h left`;
    variant = 'warning';
  } else {
    display = `${timeRemaining.minutes}m left`;
    variant = 'danger';
  }

  const colors = VARIANT_COLORS[variant];

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium',
        colors.bg,
        colors.text,
        className
      )}
    >
      <Clock className="w-3 h-3" />
      {display}
    </span>
  );
}

export default CountdownTimer;
