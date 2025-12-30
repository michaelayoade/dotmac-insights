'use client';

import { cn } from '@/lib/utils';
import { VARIANT_COLORS, type Variant } from '@/lib/design-tokens';

// =============================================================================
// PROGRESS RING
// =============================================================================

export interface ProgressRingProps {
  /** Progress value (0-100) */
  value: number;
  /** Size preset */
  size?: 'sm' | 'md' | 'lg' | 'xl';
  /** Stroke width in pixels */
  strokeWidth?: number;
  /** Color variant */
  variant?: Variant;
  /** Show percentage label in center */
  showLabel?: boolean;
  /** Custom label to show instead of percentage */
  label?: string;
  /** Show animation on mount */
  animate?: boolean;
  /** Track background color class */
  trackColor?: string;
  /** Custom class name */
  className?: string;
}

const SIZES = {
  sm: { size: 32, fontSize: 'text-xs', strokeDefault: 3 },
  md: { size: 48, fontSize: 'text-sm', strokeDefault: 4 },
  lg: { size: 64, fontSize: 'text-base', strokeDefault: 5 },
  xl: { size: 96, fontSize: 'text-xl', strokeDefault: 6 },
};

// Map variants to stroke colors
const STROKE_COLORS: Record<Variant, string> = {
  default: 'stroke-slate-muted',
  success: 'stroke-teal-electric',
  warning: 'stroke-amber-warn',
  danger: 'stroke-coral-alert',
  info: 'stroke-blue-info',
};

export function ProgressRing({
  value,
  size = 'md',
  strokeWidth,
  variant = 'success',
  showLabel = true,
  label,
  animate = true,
  trackColor = 'stroke-slate-border',
  className,
}: ProgressRingProps) {
  const { size: diameter, fontSize, strokeDefault } = SIZES[size];
  const stroke = strokeWidth ?? strokeDefault;
  const radius = (diameter - stroke) / 2;
  const circumference = radius * 2 * Math.PI;
  const clampedValue = Math.min(100, Math.max(0, value));
  const offset = circumference - (clampedValue / 100) * circumference;

  const displayLabel = label ?? `${Math.round(clampedValue)}%`;

  return (
    <div className={cn('relative inline-flex items-center justify-center', className)}>
      <svg
        width={diameter}
        height={diameter}
        className="transform -rotate-90"
        aria-hidden="true"
      >
        {/* Track */}
        <circle
          cx={diameter / 2}
          cy={diameter / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          className={trackColor}
        />
        {/* Progress */}
        <circle
          cx={diameter / 2}
          cy={diameter / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          className={cn(STROKE_COLORS[variant], animate && 'transition-all duration-500 ease-out')}
          style={{
            strokeDasharray: circumference,
            strokeDashoffset: offset,
          }}
        />
      </svg>
      {showLabel && (
        <span
          className={cn(
            'absolute font-semibold',
            fontSize,
            VARIANT_COLORS[variant].text
          )}
        >
          {displayLabel}
        </span>
      )}
    </div>
  );
}

// =============================================================================
// PROGRESS BAR (Linear variant)
// =============================================================================

export interface ProgressBarProps {
  /** Progress value (0-100) */
  value: number;
  /** Height preset */
  size?: 'sm' | 'md' | 'lg';
  /** Color variant */
  variant?: Variant;
  /** Show percentage label */
  showLabel?: boolean;
  /** Label position */
  labelPosition?: 'inside' | 'right';
  /** Show animation */
  animate?: boolean;
  /** Custom class name */
  className?: string;
}

const BAR_SIZES = {
  sm: 'h-1.5',
  md: 'h-2.5',
  lg: 'h-4',
};

const BAR_COLORS: Record<Variant, string> = {
  default: 'bg-slate-muted',
  success: 'bg-teal-electric',
  warning: 'bg-amber-warn',
  danger: 'bg-coral-alert',
  info: 'bg-blue-info',
};

export function ProgressBar({
  value,
  size = 'md',
  variant = 'success',
  showLabel = false,
  labelPosition = 'right',
  animate = true,
  className,
}: ProgressBarProps) {
  const clampedValue = Math.min(100, Math.max(0, value));

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <div className={cn('flex-1 bg-slate-elevated rounded-full overflow-hidden', BAR_SIZES[size])}>
        <div
          className={cn(
            'h-full rounded-full',
            BAR_COLORS[variant],
            animate && 'transition-all duration-500 ease-out'
          )}
          style={{ width: `${clampedValue}%` }}
          role="progressbar"
          aria-valuenow={clampedValue}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          {showLabel && labelPosition === 'inside' && size === 'lg' && (
            <span className="px-2 text-xs font-medium text-foreground">
              {Math.round(clampedValue)}%
            </span>
          )}
        </div>
      </div>
      {showLabel && labelPosition === 'right' && (
        <span className={cn('text-sm font-medium', VARIANT_COLORS[variant].text)}>
          {Math.round(clampedValue)}%
        </span>
      )}
    </div>
  );
}

export default ProgressRing;
