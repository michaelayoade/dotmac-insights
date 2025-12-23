'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { cn } from '@/lib/utils';
import { TrendingUp, TrendingDown, Minus, ChevronRight, LucideIcon } from 'lucide-react';

// =============================================================================
// TYPES
// =============================================================================

/**
 * Variant type matches the standard vocabulary from lib/design-tokens.ts
 */
type StatCardVariant = 'default' | 'success' | 'warning' | 'danger' | 'info';

/**
 * Size variants for the stat card
 */
type StatCardSize = 'sm' | 'md' | 'lg';

/**
 * Accent colors for gradient/accent styling
 */
type AccentColor = 'teal' | 'rose' | 'indigo' | 'emerald' | 'amber' | 'coral' | 'purple' | 'blue';

interface StatCardProps {
  title: string;
  value: React.ReactNode;
  subtitle?: string;
  icon?: LucideIcon;
  trend?: {
    value: number;
    label?: string;
  };
  variant?: StatCardVariant;
  /** Custom color class (overrides variant-based colors) */
  colorClass?: string;
  loading?: boolean;
  className?: string;
  animateValue?: boolean;
  /** URL to navigate to when clicked */
  href?: string;
  /** Click handler for custom actions */
  onClick?: () => void;

  // ===== NEW PROPS (Phase 2 consolidation) =====

  /** Card size - sm (compact), md (default), lg (large) */
  size?: StatCardSize;

  /** Accent color for gradient styling (replaces AccentStatCard) */
  accent?: AccentColor;

  /** Use gradient background for icon (requires accent) */
  gradientIcon?: boolean;

  /** Percentage value to display (replaces PercentStatCard) */
  pct?: number;

  /** Label for percentage (e.g., "of revenue") */
  pctLabel?: string;
}

// =============================================================================
// STYLE MAPPINGS
// =============================================================================

const variantStyles: Record<StatCardVariant, { iconBg: string; iconColor: string; valueBorder: string }> = {
  default: {
    iconBg: 'bg-slate-elevated',
    iconColor: 'text-teal-electric',
    valueBorder: 'border-slate-border',
  },
  success: {
    iconBg: 'bg-teal-electric/10',
    iconColor: 'text-teal-electric',
    valueBorder: 'border-teal-electric/30',
  },
  warning: {
    iconBg: 'bg-amber-warn/10',
    iconColor: 'text-amber-warn',
    valueBorder: 'border-amber-warn/30',
  },
  danger: {
    iconBg: 'bg-coral-alert/10',
    iconColor: 'text-coral-alert',
    valueBorder: 'border-coral-alert/30',
  },
  info: {
    iconBg: 'bg-blue-info/10',
    iconColor: 'text-blue-info',
    valueBorder: 'border-blue-info/30',
  },
};

const accentColorStyles: Record<AccentColor, { bg: string; text: string; gradient: string }> = {
  teal: {
    bg: 'bg-teal-500/10',
    text: 'text-teal-300',
    gradient: 'from-teal-500 to-emerald-400',
  },
  rose: {
    bg: 'bg-rose-500/10',
    text: 'text-rose-300',
    gradient: 'from-rose-500 to-pink-400',
  },
  indigo: {
    bg: 'bg-indigo-500/10',
    text: 'text-indigo-300',
    gradient: 'from-indigo-500 to-purple-400',
  },
  emerald: {
    bg: 'bg-emerald-500/10',
    text: 'text-emerald-300',
    gradient: 'from-emerald-500 to-teal-400',
  },
  amber: {
    bg: 'bg-amber-500/10',
    text: 'text-amber-300',
    gradient: 'from-amber-500 to-orange-400',
  },
  coral: {
    bg: 'bg-coral-alert/10',
    text: 'text-coral-alert',
    gradient: 'from-coral-alert to-red-400',
  },
  purple: {
    bg: 'bg-purple-500/10',
    text: 'text-purple-300',
    gradient: 'from-purple-500 to-pink-400',
  },
  blue: {
    bg: 'bg-blue-500/10',
    text: 'text-blue-300',
    gradient: 'from-blue-500 to-cyan-400',
  },
};

const sizeStyles: Record<StatCardSize, { card: string; icon: string; iconSize: string; value: string; title: string }> = {
  sm: {
    card: 'p-4',
    icon: 'w-8 h-8',
    iconSize: 'w-4 h-4',
    value: 'text-xl md:text-2xl',
    title: 'text-xs',
  },
  md: {
    card: 'p-6',
    icon: 'w-10 h-10',
    iconSize: 'w-5 h-5',
    value: 'text-2xl md:text-3xl',
    title: 'text-sm',
  },
  lg: {
    card: 'p-8',
    icon: 'w-12 h-12',
    iconSize: 'w-6 h-6',
    value: 'text-3xl md:text-4xl',
    title: 'text-base',
  },
};

// =============================================================================
// ANIMATED NUMBER
// =============================================================================

function AnimatedNumber({ value, duration = 1500 }: { value: number; duration?: number }) {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    const startTime = Date.now();
    const startValue = displayValue;
    const diff = value - startValue;

    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Easing function (ease-out cubic)
      const eased = 1 - Math.pow(1 - progress, 3);

      setDisplayValue(Math.round(startValue + diff * eased));

      if (progress < 1) {
        requestAnimationFrame(animate);
      }
    };

    requestAnimationFrame(animate);
  }, [value, duration, displayValue]);

  return <>{displayValue.toLocaleString()}</>;
}

// =============================================================================
// MAIN STAT CARD COMPONENT
// =============================================================================

/**
 * Unified StatCard component with multiple display modes.
 *
 * @example
 * // Basic usage
 * <StatCard title="Revenue" value="₦1.2M" icon={DollarSign} />
 *
 * @example
 * // With trend
 * <StatCard title="Revenue" value="₦1.2M" trend={{ value: 5, label: "vs last month" }} />
 *
 * @example
 * // Compact size (replaces MiniStatCard)
 * <StatCard title="Pending" value={12} icon={Clock} size="sm" colorClass="text-amber-400" />
 *
 * @example
 * // With accent gradient (replaces AccentStatCard)
 * <StatCard title="Total Assets" value={42} icon={Box} accent="indigo" gradientIcon />
 *
 * @example
 * // With percentage (replaces PercentStatCard)
 * <StatCard title="Cost of Sales" value="₦500K" pct={35.2} pctLabel="of revenue" />
 */
export function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  variant = 'default',
  colorClass,
  loading = false,
  className,
  animateValue = true,
  href,
  onClick,
  size = 'md',
  accent,
  gradientIcon = false,
  pct,
  pctLabel = 'of total',
}: StatCardProps) {
  const isClickable = Boolean(href || onClick);
  const styles = variantStyles[variant];
  const sizeStyle = sizeStyles[size];
  const accentStyle = accent ? accentColorStyles[accent] : null;

  // Determine icon styling
  const getIconStyles = () => {
    if (accent) {
      if (gradientIcon) {
        return {
          bg: `bg-gradient-to-br ${accentStyle!.gradient}`,
          color: 'text-white',
        };
      }
      return {
        bg: accentStyle!.bg,
        color: accentStyle!.text,
      };
    }
    return {
      bg: colorClass ? 'bg-slate-elevated' : styles.iconBg,
      color: colorClass || styles.iconColor,
    };
  };

  const iconStyles = getIconStyles();

  // Determine value color
  const valueColor = accent ? accentStyle!.text : (colorClass || 'text-foreground');

  const TrendIcon = trend
    ? trend.value > 0
      ? TrendingUp
      : trend.value < 0
        ? TrendingDown
        : Minus
    : null;

  const trendColor = trend
    ? trend.value > 0
      ? 'text-teal-electric'
      : trend.value < 0
        ? 'text-coral-alert'
        : 'text-slate-muted'
    : '';

  // Loading state
  if (loading) {
    return (
      <div className={cn('stat-card bg-slate-card rounded-xl border border-slate-border', sizeStyle.card, className)}>
        <div className="flex items-start justify-between mb-4">
          <div className="skeleton w-24 h-4 rounded" />
          <div className={cn('skeleton rounded-lg', sizeStyle.icon)} />
        </div>
        <div className="skeleton w-32 h-8 rounded mb-2" />
        <div className="skeleton w-20 h-4 rounded" />
      </div>
    );
  }

  const cardContent = (
    <>
      <div className="flex items-start justify-between mb-4">
        <span className={cn('text-slate-muted font-medium uppercase tracking-wide', sizeStyle.title)}>
          {title}
        </span>
        <div className="flex items-center gap-2">
          {Icon && (
            <div className={cn('rounded-lg flex items-center justify-center', sizeStyle.icon, iconStyles.bg)}>
              <Icon className={cn(sizeStyle.iconSize, iconStyles.color)} />
            </div>
          )}
          {isClickable && (
            <ChevronRight className="w-5 h-5 text-slate-muted group-hover:text-teal-electric group-hover:translate-x-0.5 transition-all duration-200" />
          )}
        </div>
      </div>

      <div className="space-y-1">
        <div className="flex items-baseline gap-2 flex-wrap min-w-0">
          <span className={cn('font-mono font-bold counter-value leading-tight break-words max-w-full', sizeStyle.value, valueColor)}>
            {typeof value === 'number' && animateValue ? (
              <AnimatedNumber value={value} />
            ) : (
              value
            )}
          </span>
          {trend && TrendIcon && (
            <div className={cn('flex items-center gap-1 text-sm', trendColor)}>
              <TrendIcon className="w-4 h-4" />
              <span className="font-mono">{Math.abs(trend.value)}%</span>
            </div>
          )}
        </div>

        {/* Percentage display */}
        {pct !== undefined && (
          <p className="text-slate-muted text-sm">
            {pct.toFixed(1)}% {pctLabel}
          </p>
        )}

        {subtitle && (
          <p className="text-slate-muted text-sm">{subtitle}</p>
        )}

        {trend?.label && (
          <p className="text-slate-muted text-xs">{trend.label}</p>
        )}
      </div>

      {/* Subtle glow effect on hover */}
      <div className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none bg-gradient-to-br from-teal-electric/5 to-transparent" />
    </>
  );

  const cardClasses = cn(
    'stat-card relative bg-slate-card rounded-xl border border-slate-border transition-all duration-300 hover:border-slate-elevated group',
    sizeStyle.card,
    isClickable && 'cursor-pointer hover:bg-slate-card/80',
    className
  );

  if (href) {
    return (
      <Link href={href} className={cn(cardClasses, 'block')}>
        {cardContent}
      </Link>
    );
  }

  if (onClick) {
    return (
      <button type="button" onClick={onClick} className={cn(cardClasses, 'w-full text-left')}>
        {cardContent}
      </button>
    );
  }

  return (
    <div className={cardClasses}>
      {cardContent}
    </div>
  );
}

// =============================================================================
// STAT INLINE - Compact stat for inline display
// =============================================================================

/**
 * Compact stat for inline display in lists or tables.
 */
export function StatInline({
  label,
  value,
  variant = 'default',
}: {
  label: string;
  value: string | number;
  variant?: StatCardVariant;
}) {
  const colors: Record<StatCardVariant, string> = {
    default: 'text-foreground',
    success: 'text-teal-electric',
    warning: 'text-amber-warn',
    danger: 'text-coral-alert',
    info: 'text-blue-info',
  };

  return (
    <div className="flex items-center justify-between py-2 border-b border-slate-border last:border-0">
      <span className="text-slate-muted text-sm">{label}</span>
      <span className={cn('font-mono font-semibold', colors[variant])}>{value}</span>
    </div>
  );
}

// =============================================================================
// STAT CARD GRID - Consistent layout for stat card sections
// =============================================================================

type GridColumns = 2 | 3 | 4 | 5;

interface StatCardGridProps {
  children: React.ReactNode;
  /** Number of columns at large breakpoint (default: 4) */
  columns?: GridColumns;
  /** Gap size (default: 4) */
  gap?: 4 | 6;
  className?: string;
}

const gridColsMap: Record<GridColumns, string> = {
  2: 'md:grid-cols-2',
  3: 'md:grid-cols-3',
  4: 'md:grid-cols-2 lg:grid-cols-4',
  5: 'md:grid-cols-3 lg:grid-cols-5',
};

/**
 * Responsive grid layout for stat cards.
 *
 * @example
 * <StatCardGrid columns={4}>
 *   <StatCard title="Revenue" value="₦1.2M" />
 *   <StatCard title="Expenses" value="₦800K" />
 *   ...
 * </StatCardGrid>
 */
export function StatCardGrid({ children, columns = 4, gap = 4, className }: StatCardGridProps) {
  return (
    <div
      className={cn(
        'grid grid-cols-1',
        gridColsMap[columns],
        gap === 4 ? 'gap-4' : 'gap-6',
        className
      )}
    >
      {children}
    </div>
  );
}

// =============================================================================
// RATIO CARD - For displaying financial ratios with status indicator
// =============================================================================

type RatioStatus = 'good' | 'warning' | 'bad' | 'neutral';

interface RatioCardProps {
  title: string;
  value: string | number;
  description?: string;
  status?: RatioStatus;
  className?: string;
}

const ratioStatusStyles: Record<RatioStatus, string> = {
  good: 'border-emerald-500/30 bg-emerald-500/10',
  warning: 'border-amber-500/30 bg-amber-500/10',
  bad: 'border-rose-500/30 bg-rose-500/10',
  neutral: 'border-slate-border bg-slate-elevated',
};

const ratioValueColors: Record<RatioStatus, string> = {
  good: 'text-emerald-400',
  warning: 'text-amber-400',
  bad: 'text-rose-400',
  neutral: 'text-foreground',
};

/**
 * Card for displaying financial ratios with status-based coloring.
 *
 * @example
 * <RatioCard
 *   title="Current Ratio"
 *   value="2.5"
 *   description="Total Assets / Total Liabilities"
 *   status="good"
 * />
 */
export function RatioCard({ title, value, description, status = 'neutral', className }: RatioCardProps) {
  return (
    <div
      className={cn(
        'rounded-xl border p-4 transition-colors',
        ratioStatusStyles[status],
        className
      )}
    >
      <p className="text-sm text-slate-muted mb-1">{title}</p>
      <p className={cn('text-2xl font-bold font-mono', ratioValueColors[status])}>
        {value}
      </p>
      {description && (
        <p className="text-xs text-slate-muted mt-1">{description}</p>
      )}
    </div>
  );
}

// =============================================================================
// SELECTABLE STAT CARD - Compound component for interactive stat cards
// =============================================================================

interface SelectableStatCardProps {
  title: string;
  value: string | number;
  icon?: LucideIcon;
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info' | 'muted';
  active?: boolean;
  onClick?: () => void;
  className?: string;
}

const selectableVariantStyles: Record<string, { bg: string; text: string; iconBg: string }> = {
  default: {
    bg: 'border-slate-border',
    text: 'text-foreground',
    iconBg: 'bg-slate-elevated text-teal-electric',
  },
  success: {
    bg: 'border-emerald-500/30 bg-emerald-500/5',
    text: 'text-emerald-400',
    iconBg: 'bg-emerald-500/10 text-emerald-400',
  },
  warning: {
    bg: 'border-amber-500/30 bg-amber-500/5',
    text: 'text-amber-400',
    iconBg: 'bg-amber-500/10 text-amber-400',
  },
  danger: {
    bg: 'border-rose-500/30 bg-rose-500/5',
    text: 'text-rose-400',
    iconBg: 'bg-rose-500/10 text-rose-400',
  },
  info: {
    bg: 'border-blue-500/30 bg-blue-500/5',
    text: 'text-blue-400',
    iconBg: 'bg-blue-500/10 text-blue-400',
  },
  muted: {
    bg: 'border-slate-border',
    text: 'text-slate-muted',
    iconBg: 'bg-slate-elevated text-slate-muted',
  },
};

/**
 * Selectable stat card with active state ring styling.
 * Used for filtering or mode selection in dashboards.
 *
 * Can be used as StatCard.Selectable or SelectableStatCard.
 *
 * @example
 * <SelectableStatCard
 *   title="Open Tickets"
 *   value={42}
 *   icon={AlertCircle}
 *   variant="warning"
 *   active={filter === 'open'}
 *   onClick={() => setFilter('open')}
 * />
 */
export function SelectableStatCard({
  title,
  value,
  icon: Icon,
  variant = 'default',
  active = false,
  onClick,
  className,
}: SelectableStatCardProps) {
  const styles = selectableVariantStyles[variant] || selectableVariantStyles.default;

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-xl p-4 border text-left transition-all w-full',
        'bg-slate-card hover:bg-slate-elevated/50',
        styles.bg,
        active && 'ring-2 ring-teal-electric ring-offset-2 ring-offset-slate-950',
        className
      )}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-slate-muted text-sm">{title}</span>
        {Icon && (
          <div className={cn('w-8 h-8 rounded-lg flex items-center justify-center', styles.iconBg)}>
            <Icon className="w-4 h-4" />
          </div>
        )}
      </div>
      <p className={cn('text-2xl font-bold', styles.text)}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </p>
    </button>
  );
}

// Attach Selectable as compound component
StatCard.Selectable = SelectableStatCard;

// =============================================================================
// DEPRECATED COMPONENTS - Kept for backwards compatibility
// =============================================================================

interface MiniStatCardProps {
  label: string;
  value: string | number;
  icon?: LucideIcon;
  colorClass?: string;
  className?: string;
}

/**
 * @deprecated Use `<StatCard size="sm" />` instead.
 *
 * @example
 * // Before:
 * <MiniStatCard label="Pending" value={12} icon={Clock} colorClass="text-amber-400" />
 *
 * // After:
 * <StatCard title="Pending" value={12} icon={Clock} size="sm" colorClass="text-amber-400" />
 */
export function MiniStatCard({ label, value, icon: Icon, colorClass = 'text-foreground', className }: MiniStatCardProps) {
  if (process.env.NODE_ENV === 'development') {
    console.warn(
      '[StatCard] MiniStatCard is deprecated. Use <StatCard size="sm" /> instead.'
    );
  }

  return (
    <div className={cn('bg-slate-card border border-slate-border rounded-xl p-4', className)}>
      <div className="flex items-center gap-2 text-slate-muted text-sm mb-1">
        {Icon && <Icon className={cn('w-4 h-4', colorClass)} />}
        <span>{label}</span>
      </div>
      <p className={cn('text-2xl font-bold', colorClass)}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </p>
    </div>
  );
}

interface PercentStatCardProps {
  title: string;
  value: string | number;
  pct?: number;
  pctLabel?: string;
  icon?: LucideIcon;
  colorClass?: string;
  className?: string;
}

/**
 * @deprecated Use `<StatCard pct={...} pctLabel="..." />` instead.
 *
 * @example
 * // Before:
 * <PercentStatCard title="Cost of Sales" value="₦500K" pct={35.2} pctLabel="of revenue" />
 *
 * // After:
 * <StatCard title="Cost of Sales" value="₦500K" pct={35.2} pctLabel="of revenue" />
 */
export function PercentStatCard({
  title,
  value,
  pct,
  pctLabel = 'of revenue',
  icon: Icon,
  colorClass = 'text-foreground',
  className,
}: PercentStatCardProps) {
  if (process.env.NODE_ENV === 'development') {
    console.warn(
      '[StatCard] PercentStatCard is deprecated. Use <StatCard pct={...} pctLabel="..." /> instead.'
    );
  }

  return (
    <div className={cn('bg-slate-card border border-slate-border rounded-xl p-4', className)}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-slate-muted text-sm">{title}</span>
        {Icon && (
          <div className="w-8 h-8 rounded-lg bg-slate-elevated flex items-center justify-center">
            <Icon className={cn('w-4 h-4', colorClass)} />
          </div>
        )}
      </div>
      <p className={cn('text-xl font-bold font-mono', colorClass)}>{value}</p>
      {pct !== undefined && (
        <p className="text-slate-muted text-sm mt-1">
          {pct.toFixed(1)}% {pctLabel}
        </p>
      )}
    </div>
  );
}

interface AccentStatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: LucideIcon;
  accent?: AccentColor;
  /** Use gradient background for icon instead of solid */
  gradient?: boolean;
  href?: string;
  className?: string;
}

/**
 * @deprecated Use `<StatCard accent="..." gradientIcon />` instead.
 *
 * @example
 * // Before:
 * <AccentStatCard title="Total Assets" value={42} icon={Box} accent="indigo" gradient href="/assets" />
 *
 * // After:
 * <StatCard title="Total Assets" value={42} icon={Box} accent="indigo" gradientIcon href="/assets" />
 */
export function AccentStatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  accent = 'teal',
  gradient = false,
  href,
  className,
}: AccentStatCardProps) {
  if (process.env.NODE_ENV === 'development') {
    console.warn(
      '[StatCard] AccentStatCard is deprecated. Use <StatCard accent="..." gradientIcon /> instead.'
    );
  }

  const styles = accentColorStyles[accent];

  const content = (
    <>
      <div className="flex items-start justify-between mb-3">
        <span className="text-slate-muted text-sm">{title}</span>
        {Icon && (
          <div
            className={cn(
              'w-10 h-10 rounded-xl flex items-center justify-center',
              gradient ? `bg-gradient-to-br ${styles.gradient}` : styles.bg
            )}
          >
            <Icon className={cn('w-5 h-5', gradient ? 'text-white' : styles.text)} />
          </div>
        )}
      </div>
      <p className={cn('text-2xl font-bold', styles.text)}>
        {typeof value === 'number' ? value.toLocaleString() : value}
      </p>
      {subtitle && <p className="text-slate-muted text-sm mt-1">{subtitle}</p>}
    </>
  );

  const cardClasses = cn(
    'bg-slate-card border border-slate-border rounded-xl p-5 transition-all',
    href && 'hover:border-slate-muted cursor-pointer',
    className
  );

  if (href) {
    return (
      <Link href={href} className={cardClasses}>
        {content}
      </Link>
    );
  }

  return <div className={cardClasses}>{content}</div>;
}
