'use client';

import { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';
import { TrendingUp, TrendingDown, Minus, LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: LucideIcon;
  trend?: {
    value: number;
    label?: string;
  };
  variant?: 'default' | 'success' | 'warning' | 'danger';
  loading?: boolean;
  className?: string;
  animateValue?: boolean;
}

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

export function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  trend,
  variant = 'default',
  loading = false,
  className,
  animateValue = true,
}: StatCardProps) {
  const variantStyles = {
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
  };

  const styles = variantStyles[variant];

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

  if (loading) {
    return (
      <div className={cn('stat-card bg-slate-card rounded-xl border border-slate-border p-6', className)}>
        <div className="flex items-start justify-between mb-4">
          <div className="skeleton w-24 h-4 rounded" />
          <div className="skeleton w-10 h-10 rounded-lg" />
        </div>
        <div className="skeleton w-32 h-8 rounded mb-2" />
        <div className="skeleton w-20 h-4 rounded" />
      </div>
    );
  }

  return (
    <div
      className={cn(
        'stat-card bg-slate-card rounded-xl border border-slate-border p-6 transition-all duration-300 hover:border-slate-elevated group',
        className
      )}
    >
      <div className="flex items-start justify-between mb-4">
        <span className="text-slate-muted text-sm font-medium uppercase tracking-wide">
          {title}
        </span>
        {Icon && (
          <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', styles.iconBg)}>
            <Icon className={cn('w-5 h-5', styles.iconColor)} />
          </div>
        )}
      </div>

      <div className="space-y-1">
        <div className="flex items-baseline gap-2">
          <span className="font-mono text-3xl font-bold text-white counter-value">
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

        {subtitle && (
          <p className="text-slate-muted text-sm">{subtitle}</p>
        )}

        {trend?.label && (
          <p className="text-slate-muted text-xs">{trend.label}</p>
        )}
      </div>

      {/* Subtle glow effect on hover */}
      <div className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none bg-gradient-to-br from-teal-electric/5 to-transparent" />
    </div>
  );
}

// Compact stat for inline display
export function StatInline({
  label,
  value,
  variant = 'default',
}: {
  label: string;
  value: string | number;
  variant?: 'default' | 'success' | 'warning' | 'danger';
}) {
  const colors = {
    default: 'text-white',
    success: 'text-teal-electric',
    warning: 'text-amber-warn',
    danger: 'text-coral-alert',
  };

  return (
    <div className="flex items-center justify-between py-2 border-b border-slate-border last:border-0">
      <span className="text-slate-muted text-sm">{label}</span>
      <span className={cn('font-mono font-semibold', colors[variant])}>{value}</span>
    </div>
  );
}
