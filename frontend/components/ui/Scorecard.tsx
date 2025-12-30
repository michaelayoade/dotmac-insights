'use client';

import { cn } from '@/lib/utils';
import { TrendingUp, TrendingDown, Minus, Info, Target } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

// =============================================================================
// TYPES
// =============================================================================

export type ScorecardVariant = 'default' | 'success' | 'warning' | 'danger' | 'info';

export interface ScorecardMetric {
  id: string;
  /** Metric label */
  label: string;
  /** Current value */
  value: number | string;
  /** Formatted value (e.g., "$1,234") */
  displayValue?: string;
  /** Target value */
  target?: number;
  /** Previous period value (for comparison) */
  previousValue?: number;
  /** Change percentage */
  changePercent?: number;
  /** Change direction */
  changeDirection?: 'up' | 'down' | 'neutral';
  /** Whether higher is better */
  higherIsBetter?: boolean;
  /** Unit (e.g., "%", "days", "hrs") */
  unit?: string;
  /** Description or tooltip */
  description?: string;
  /** Variant override */
  variant?: ScorecardVariant;
  /** Custom icon */
  icon?: LucideIcon;
}

// =============================================================================
// SCORECARD
// =============================================================================

export interface ScorecardProps {
  /** Title of the scorecard */
  title?: string;
  /** Description */
  description?: string;
  /** Metrics to display */
  metrics: ScorecardMetric[];
  /** Number of columns */
  columns?: 2 | 3 | 4;
  /** Compact mode */
  compact?: boolean;
  /** Show target indicator */
  showTargets?: boolean;
  /** Show change indicators */
  showChanges?: boolean;
  /** Default variant */
  defaultVariant?: ScorecardVariant;
  /** Custom class name */
  className?: string;
}

export function Scorecard({
  title,
  description,
  metrics,
  columns = 3,
  compact = false,
  showTargets = true,
  showChanges = true,
  defaultVariant = 'default',
  className,
}: ScorecardProps) {
  const gridCols = {
    2: 'grid-cols-2',
    3: 'grid-cols-1 md:grid-cols-3',
    4: 'grid-cols-2 md:grid-cols-4',
  };

  return (
    <div className={cn('bg-slate-card border border-slate-border rounded-xl', className)}>
      {/* Header */}
      {(title || description) && (
        <div className="px-5 py-4 border-b border-slate-border">
          {title && <h3 className="text-lg font-semibold text-foreground">{title}</h3>}
          {description && <p className="text-sm text-slate-muted mt-0.5">{description}</p>}
        </div>
      )}

      {/* Metrics Grid */}
      <div className={cn('grid gap-px bg-slate-border', gridCols[columns])}>
        {metrics.map((metric) => (
          <ScorecardMetricCard
            key={metric.id}
            metric={metric}
            compact={compact}
            showTarget={showTargets}
            showChange={showChanges}
            defaultVariant={defaultVariant}
          />
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// SCORECARD METRIC CARD
// =============================================================================

interface ScorecardMetricCardProps {
  metric: ScorecardMetric;
  compact?: boolean;
  showTarget?: boolean;
  showChange?: boolean;
  defaultVariant?: ScorecardVariant;
}

function ScorecardMetricCard({
  metric,
  compact,
  showTarget,
  showChange,
  defaultVariant = 'default',
}: ScorecardMetricCardProps) {
  const variantColors: Record<ScorecardVariant, { text: string; bg: string }> = {
    default: { text: 'text-teal-electric', bg: 'bg-teal-electric/10' },
    success: { text: 'text-emerald-500', bg: 'bg-emerald-500/10' },
    warning: { text: 'text-amber-500', bg: 'bg-amber-500/10' },
    danger: { text: 'text-coral-alert', bg: 'bg-coral-alert/10' },
    info: { text: 'text-blue-500', bg: 'bg-blue-500/10' },
  };

  // Determine variant based on target or manual override
  const determineVariant = (): ScorecardVariant => {
    if (metric.variant) return metric.variant;
    if (metric.target !== undefined && typeof metric.value === 'number') {
      const ratio = metric.value / metric.target;
      if (metric.higherIsBetter !== false) {
        if (ratio >= 1) return 'success';
        if (ratio >= 0.8) return 'warning';
        return 'danger';
      } else {
        if (ratio <= 1) return 'success';
        if (ratio <= 1.2) return 'warning';
        return 'danger';
      }
    }
    return defaultVariant;
  };

  const variant = determineVariant();
  const colors = variantColors[variant];
  const Icon = metric.icon;

  // Format display value
  const displayValue = metric.displayValue ?? String(metric.value);

  // Calculate target percentage
  const targetPercent =
    metric.target !== undefined && typeof metric.value === 'number'
      ? Math.round((metric.value / metric.target) * 100)
      : null;

  // Change indicator
  const changeDirection = metric.changeDirection ?? (
    metric.changePercent !== undefined
      ? metric.changePercent > 0 ? 'up' : metric.changePercent < 0 ? 'down' : 'neutral'
      : undefined
  );

  const isPositiveChange = metric.higherIsBetter !== false
    ? changeDirection === 'up'
    : changeDirection === 'down';

  return (
    <div className={cn('bg-background p-4', compact && 'p-3')}>
      {/* Header Row */}
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          {Icon && (
            <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center', colors.bg)}>
              <Icon className={cn('w-4 h-4', colors.text)} />
            </div>
          )}
          <span className="text-sm text-slate-muted">{metric.label}</span>
        </div>
        {metric.description && (
          <button className="p-1 text-slate-muted hover:text-foreground" title={metric.description}>
            <Info className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Value */}
      <div className="flex items-baseline gap-1">
        <span className={cn('text-2xl font-bold', colors.text, compact && 'text-xl')}>
          {displayValue}
        </span>
        {metric.unit && <span className="text-sm text-slate-muted">{metric.unit}</span>}
      </div>

      {/* Target */}
      {showTarget && metric.target !== undefined && (
        <div className="mt-2">
          <div className="flex items-center justify-between text-xs text-slate-muted mb-1">
            <span className="flex items-center gap-1">
              <Target className="w-3 h-3" />
              Target: {metric.target}
              {metric.unit}
            </span>
            <span>{targetPercent}%</span>
          </div>
          <div className="h-1.5 bg-slate-elevated rounded-full overflow-hidden">
            <div
              className={cn(
                'h-full rounded-full transition-all',
                variant === 'success' && 'bg-emerald-500',
                variant === 'warning' && 'bg-amber-500',
                variant === 'danger' && 'bg-coral-alert',
                variant === 'default' && 'bg-teal-electric',
                variant === 'info' && 'bg-blue-500'
              )}
              style={{ width: `${Math.min(100, targetPercent || 0)}%` }}
            />
          </div>
        </div>
      )}

      {/* Change */}
      {showChange && metric.changePercent !== undefined && (
        <div className="mt-2 flex items-center gap-2">
          <div
            className={cn(
              'flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs font-medium',
              isPositiveChange
                ? 'bg-emerald-500/20 text-emerald-500'
                : changeDirection === 'neutral'
                ? 'bg-slate-elevated text-slate-muted'
                : 'bg-coral-alert/20 text-coral-alert'
            )}
          >
            {changeDirection === 'up' && <TrendingUp className="w-3 h-3" />}
            {changeDirection === 'down' && <TrendingDown className="w-3 h-3" />}
            {changeDirection === 'neutral' && <Minus className="w-3 h-3" />}
            {Math.abs(metric.changePercent).toFixed(1)}%
          </div>
          {metric.previousValue !== undefined && (
            <span className="text-xs text-slate-muted">
              vs {metric.previousValue}
              {metric.unit}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

// =============================================================================
// MINI SCORECARD
// =============================================================================

export interface MiniScorecardProps {
  label: string;
  value: string | number;
  change?: number;
  changeDirection?: 'up' | 'down' | 'neutral';
  higherIsBetter?: boolean;
  icon?: LucideIcon;
  variant?: ScorecardVariant;
  className?: string;
}

export function MiniScorecard({
  label,
  value,
  change,
  changeDirection,
  higherIsBetter = true,
  icon: Icon,
  variant = 'default',
  className,
}: MiniScorecardProps) {
  const variantColors: Record<ScorecardVariant, { text: string; bg: string }> = {
    default: { text: 'text-teal-electric', bg: 'bg-teal-electric/10' },
    success: { text: 'text-emerald-500', bg: 'bg-emerald-500/10' },
    warning: { text: 'text-amber-500', bg: 'bg-amber-500/10' },
    danger: { text: 'text-coral-alert', bg: 'bg-coral-alert/10' },
    info: { text: 'text-blue-500', bg: 'bg-blue-500/10' },
  };

  const colors = variantColors[variant];
  const direction = changeDirection ?? (change !== undefined ? (change > 0 ? 'up' : change < 0 ? 'down' : 'neutral') : undefined);
  const isPositive = higherIsBetter ? direction === 'up' : direction === 'down';

  return (
    <div className={cn('flex items-center gap-3', className)}>
      {Icon && (
        <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', colors.bg)}>
          <Icon className={cn('w-5 h-5', colors.text)} />
        </div>
      )}
      <div>
        <p className="text-xs text-slate-muted">{label}</p>
        <div className="flex items-baseline gap-2">
          <span className={cn('text-lg font-bold', colors.text)}>{value}</span>
          {change !== undefined && (
            <span
              className={cn(
                'flex items-center text-xs font-medium',
                isPositive ? 'text-emerald-500' : direction === 'neutral' ? 'text-slate-muted' : 'text-coral-alert'
              )}
            >
              {direction === 'up' && <TrendingUp className="w-3 h-3 mr-0.5" />}
              {direction === 'down' && <TrendingDown className="w-3 h-3 mr-0.5" />}
              {Math.abs(change).toFixed(1)}%
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export default Scorecard;
