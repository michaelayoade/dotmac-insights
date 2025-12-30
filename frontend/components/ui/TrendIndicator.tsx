'use client';

import { cn } from '@/lib/utils';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

// =============================================================================
// TREND INDICATOR
// =============================================================================

export interface TrendIndicatorProps {
  /** The change value (can be positive, negative, or zero) */
  value: number;
  /** Override automatic direction detection */
  direction?: 'up' | 'down' | 'neutral';
  /** Display format */
  format?: 'percent' | 'number' | 'currency';
  /** Currency code for currency format */
  currency?: string;
  /** Locale for number formatting */
  locale?: string;
  /** Invert colors (green for down, red for up) - useful for costs, errors */
  invertColors?: boolean;
  /** Size preset */
  size?: 'sm' | 'md' | 'lg';
  /** Show the direction icon */
  showIcon?: boolean;
  /** Show the value */
  showValue?: boolean;
  /** Custom prefix text */
  prefix?: string;
  /** Custom suffix text */
  suffix?: string;
  /** Custom class name */
  className?: string;
}

const SIZES = {
  sm: { text: 'text-xs', icon: 'w-3 h-3', gap: 'gap-0.5' },
  md: { text: 'text-sm', icon: 'w-4 h-4', gap: 'gap-1' },
  lg: { text: 'text-base', icon: 'w-5 h-5', gap: 'gap-1.5' },
};

export function TrendIndicator({
  value,
  direction: directionProp,
  format = 'percent',
  currency = 'KES',
  locale = 'en-KE',
  invertColors = false,
  size = 'md',
  showIcon = true,
  showValue = true,
  prefix,
  suffix,
  className,
}: TrendIndicatorProps) {
  // Determine direction
  const direction = directionProp ?? (value > 0 ? 'up' : value < 0 ? 'down' : 'neutral');

  // Get colors based on direction and invert setting
  const getColorClass = () => {
    if (direction === 'neutral') return 'text-slate-muted';
    const isPositive = direction === 'up';
    const isGood = invertColors ? !isPositive : isPositive;
    return isGood ? 'text-teal-electric' : 'text-coral-alert';
  };

  // Get icon based on direction
  const getIcon = () => {
    switch (direction) {
      case 'up':
        return TrendingUp;
      case 'down':
        return TrendingDown;
      default:
        return Minus;
    }
  };

  // Format the value
  const formatValue = () => {
    const absValue = Math.abs(value);
    const sign = value > 0 ? '+' : value < 0 ? '-' : '';

    switch (format) {
      case 'percent':
        return `${sign}${absValue.toFixed(1)}%`;
      case 'currency':
        return `${sign}${new Intl.NumberFormat(locale, {
          style: 'currency',
          currency,
          minimumFractionDigits: 0,
          maximumFractionDigits: 0,
        }).format(absValue)}`;
      case 'number':
      default:
        return `${sign}${new Intl.NumberFormat(locale, {
          minimumFractionDigits: 0,
          maximumFractionDigits: 1,
        }).format(absValue)}`;
    }
  };

  const Icon = getIcon();
  const sizeConfig = SIZES[size];

  return (
    <span
      className={cn(
        'inline-flex items-center font-medium',
        sizeConfig.gap,
        sizeConfig.text,
        getColorClass(),
        className
      )}
    >
      {showIcon && <Icon className={sizeConfig.icon} />}
      {prefix && <span>{prefix}</span>}
      {showValue && <span>{formatValue()}</span>}
      {suffix && <span>{suffix}</span>}
    </span>
  );
}

// =============================================================================
// TREND BADGE (Pill-style variant)
// =============================================================================

export interface TrendBadgeProps extends Omit<TrendIndicatorProps, 'showIcon'> {
  /** Show background pill */
  showBackground?: boolean;
}

export function TrendBadge({
  value,
  direction: directionProp,
  format = 'percent',
  currency = 'KES',
  locale = 'en-KE',
  invertColors = false,
  size = 'sm',
  showValue = true,
  showBackground = true,
  prefix,
  suffix,
  className,
}: TrendBadgeProps) {
  // Determine direction
  const direction = directionProp ?? (value > 0 ? 'up' : value < 0 ? 'down' : 'neutral');

  // Get colors based on direction and invert setting
  const getColors = () => {
    if (direction === 'neutral') {
      return {
        text: 'text-slate-muted',
        bg: 'bg-slate-elevated',
      };
    }
    const isPositive = direction === 'up';
    const isGood = invertColors ? !isPositive : isPositive;
    return isGood
      ? { text: 'text-teal-electric', bg: 'bg-teal-electric/15' }
      : { text: 'text-coral-alert', bg: 'bg-coral-alert/15' };
  };

  // Get icon based on direction
  const getIcon = () => {
    switch (direction) {
      case 'up':
        return TrendingUp;
      case 'down':
        return TrendingDown;
      default:
        return Minus;
    }
  };

  // Format the value
  const formatValue = () => {
    const absValue = Math.abs(value);
    const sign = value > 0 ? '+' : value < 0 ? '-' : '';

    switch (format) {
      case 'percent':
        return `${sign}${absValue.toFixed(1)}%`;
      case 'currency':
        return `${sign}${new Intl.NumberFormat(locale, {
          style: 'currency',
          currency,
          minimumFractionDigits: 0,
          maximumFractionDigits: 0,
        }).format(absValue)}`;
      case 'number':
      default:
        return `${sign}${new Intl.NumberFormat(locale, {
          minimumFractionDigits: 0,
          maximumFractionDigits: 1,
        }).format(absValue)}`;
    }
  };

  const Icon = getIcon();
  const colors = getColors();
  const sizeConfig = SIZES[size];

  return (
    <span
      className={cn(
        'inline-flex items-center font-medium rounded-full',
        sizeConfig.gap,
        sizeConfig.text,
        colors.text,
        showBackground && colors.bg,
        showBackground && 'px-2 py-0.5',
        className
      )}
    >
      <Icon className={sizeConfig.icon} />
      {prefix && <span>{prefix}</span>}
      {showValue && <span>{formatValue()}</span>}
      {suffix && <span>{suffix}</span>}
    </span>
  );
}

// =============================================================================
// COMPARISON INDICATOR (Shows current vs previous with trend)
// =============================================================================

export interface ComparisonIndicatorProps {
  /** Current value */
  current: number;
  /** Previous value for comparison */
  previous: number;
  /** Format for displaying values */
  format?: 'percent' | 'number' | 'currency';
  /** Currency code */
  currency?: string;
  /** Locale for formatting */
  locale?: string;
  /** Invert colors */
  invertColors?: boolean;
  /** Size preset */
  size?: 'sm' | 'md';
  /** Custom class name */
  className?: string;
}

export function ComparisonIndicator({
  current,
  previous,
  format = 'number',
  currency = 'KES',
  locale = 'en-KE',
  invertColors = false,
  size = 'sm',
  className,
}: ComparisonIndicatorProps) {
  // Calculate percentage change
  const percentChange = previous !== 0 ? ((current - previous) / Math.abs(previous)) * 100 : 0;

  // Format a value for display
  const formatVal = (val: number) => {
    switch (format) {
      case 'currency':
        return new Intl.NumberFormat(locale, {
          style: 'currency',
          currency,
          minimumFractionDigits: 0,
          maximumFractionDigits: 0,
        }).format(val);
      case 'percent':
        return `${val.toFixed(1)}%`;
      case 'number':
      default:
        return new Intl.NumberFormat(locale).format(val);
    }
  };

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <span className={cn('font-semibold text-foreground', size === 'sm' ? 'text-sm' : 'text-base')}>
        {formatVal(current)}
      </span>
      <TrendBadge value={percentChange} invertColors={invertColors} size={size} />
      <span className={cn('text-slate-muted', size === 'sm' ? 'text-xs' : 'text-sm')}>
        vs {formatVal(previous)}
      </span>
    </div>
  );
}

export default TrendIndicator;
