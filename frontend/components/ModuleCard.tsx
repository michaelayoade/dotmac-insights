'use client';

import Link from 'next/link';
import { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

// Color variants for module cards
const ACCENT_COLORS = {
  teal: {
    bg: 'bg-teal-500/10',
    border: 'border-teal-500/30',
    text: 'text-teal-400',
    glow: 'group-hover:shadow-teal-500/20',
  },
  blue: {
    bg: 'bg-blue-500/10',
    border: 'border-blue-500/30',
    text: 'text-blue-400',
    glow: 'group-hover:shadow-blue-500/20',
  },
  emerald: {
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/30',
    text: 'text-emerald-400',
    glow: 'group-hover:shadow-emerald-500/20',
  },
  amber: {
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/30',
    text: 'text-amber-400',
    glow: 'group-hover:shadow-amber-500/20',
  },
  violet: {
    bg: 'bg-violet-500/10',
    border: 'border-violet-500/30',
    text: 'text-violet-400',
    glow: 'group-hover:shadow-violet-500/20',
  },
  rose: {
    bg: 'bg-rose-500/10',
    border: 'border-rose-500/30',
    text: 'text-rose-400',
    glow: 'group-hover:shadow-rose-500/20',
  },
  orange: {
    bg: 'bg-orange-500/10',
    border: 'border-orange-500/30',
    text: 'text-orange-400',
    glow: 'group-hover:shadow-orange-500/20',
  },
  cyan: {
    bg: 'bg-cyan-500/10',
    border: 'border-cyan-500/30',
    text: 'text-cyan-400',
    glow: 'group-hover:shadow-cyan-500/20',
  },
} as const;

export type AccentColor = keyof typeof ACCENT_COLORS;

export interface ModuleCardProps {
  /** Module name/title */
  name: string;
  /** Short description of the module */
  description: string;
  /** Route to navigate to */
  href: string;
  /** Lucide icon component */
  icon: LucideIcon;
  /** Optional badge text (e.g., "HR", "CRM") */
  badge?: string;
  /** Accent color for the card */
  accentColor?: AccentColor;
  /** Whether the module is disabled/coming soon */
  disabled?: boolean;
  /** Whether the module is a stub/placeholder */
  stub?: boolean;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Module card component for dashboard navigation
 *
 * @example
 * <ModuleCard
 *   name="HR Management"
 *   description="Manage employees, payroll, and attendance"
 *   href="/hr"
 *   icon={Users}
 *   badge="HR"
 *   accentColor="amber"
 * />
 */
export function ModuleCard({
  name,
  description,
  href,
  icon: Icon,
  badge,
  accentColor = 'teal',
  disabled = false,
  stub = false,
  className,
}: ModuleCardProps) {
  const colors = ACCENT_COLORS[accentColor];

  const cardContent = (
    <>
      {/* Icon */}
      <div
        className={cn(
          'w-12 h-12 rounded-xl flex items-center justify-center mb-4 transition-transform group-hover:scale-110',
          colors.bg,
          colors.border,
          'border'
        )}
      >
        <Icon className={cn('w-6 h-6', colors.text)} />
      </div>

      {/* Content */}
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-1">
          <h3 className="text-lg font-semibold text-white group-hover:text-teal-electric transition-colors">
            {name}
          </h3>
          {badge && (
            <span
              className={cn(
                'px-2 py-0.5 rounded-full text-xs font-medium',
                colors.bg,
                colors.text
              )}
            >
              {badge}
            </span>
          )}
          {stub && (
            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-slate-elevated text-slate-muted">
              Coming Soon
            </span>
          )}
        </div>
        <p className="text-sm text-slate-muted line-clamp-2">{description}</p>
      </div>

      {/* Arrow indicator */}
      <div
        className={cn(
          'w-8 h-8 rounded-full flex items-center justify-center transition-all',
          'bg-slate-elevated group-hover:bg-teal-electric/20',
          'text-slate-muted group-hover:text-teal-electric'
        )}
      >
        <svg
          className="w-4 h-4 transition-transform group-hover:translate-x-0.5"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5l7 7-7 7"
          />
        </svg>
      </div>
    </>
  );

  const cardClasses = cn(
    'group relative flex items-center gap-4 p-5 rounded-xl border transition-all duration-200',
    'bg-slate-card border-slate-border',
    disabled || stub
      ? 'opacity-60 cursor-not-allowed'
      : 'hover:border-slate-elevated hover:shadow-lg cursor-pointer',
    colors.glow,
    className
  );

  if (disabled || stub) {
    return <div className={cardClasses}>{cardContent}</div>;
  }

  return (
    <Link href={href} className={cardClasses}>
      {cardContent}
    </Link>
  );
}

/**
 * Grid container for module cards
 *
 * @example
 * <ModuleCardGrid>
 *   <ModuleCard ... />
 *   <ModuleCard ... />
 * </ModuleCardGrid>
 */
export function ModuleCardGrid({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4',
        className
      )}
    >
      {children}
    </div>
  );
}

export default ModuleCard;
