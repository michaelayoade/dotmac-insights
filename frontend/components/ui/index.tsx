'use client';

import { cn } from '@/lib/utils';
import { LucideIcon, AlertTriangle, RefreshCw, Inbox } from 'lucide-react';
import Link from 'next/link';

// =============================================================================
// PAGE HEADER
// =============================================================================

export interface PageHeaderProps {
  title: string;
  subtitle?: string;
  icon?: LucideIcon;
  iconClassName?: string;
  actions?: React.ReactNode;
  breadcrumbs?: { label: string; href?: string }[];
}

export function PageHeader({
  title,
  subtitle,
  icon: Icon,
  iconClassName,
  actions,
  breadcrumbs,
}: PageHeaderProps) {
  return (
    <div className="space-y-3">
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav className="flex items-center gap-2 text-sm">
          {breadcrumbs.map((crumb, idx) => (
            <div key={idx} className="flex items-center gap-2">
              {idx > 0 && <span className="text-slate-muted">/</span>}
              {crumb.href ? (
                <Link
                  href={crumb.href}
                  className="text-slate-muted hover:text-white transition-colors"
                >
                  {crumb.label}
                </Link>
              ) : (
                <span className="text-white">{crumb.label}</span>
              )}
            </div>
          ))}
        </nav>
      )}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          {Icon && (
            <div
              className={cn(
                'w-10 h-10 rounded-xl flex items-center justify-center',
                iconClassName || 'bg-teal-electric/10 border border-teal-electric/30'
              )}
            >
              <Icon className="w-5 h-5 text-teal-electric" />
            </div>
          )}
          <div>
            <h1 className="text-2xl font-bold text-white">{title}</h1>
            {subtitle && <p className="text-slate-muted text-sm">{subtitle}</p>}
          </div>
        </div>
        {actions && <div className="flex items-center gap-3">{actions}</div>}
      </div>
    </div>
  );
}

// =============================================================================
// EMPTY STATE
// =============================================================================

export interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick?: () => void;
    href?: string;
    icon?: LucideIcon;
  };
  className?: string;
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  const ActionIcon = action?.icon;

  return (
    <div
      className={cn(
        'bg-slate-card border border-slate-border rounded-xl p-8',
        className
      )}
    >
      <div className="flex flex-col items-center justify-center text-center">
        <Icon className="w-12 h-12 mb-3 text-slate-muted opacity-50" />
        <p className="text-white font-medium mb-1">{title}</p>
        {description && (
          <p className="text-sm text-slate-muted mb-4 max-w-md">{description}</p>
        )}
        {action && (
          action.href ? (
            <Link
              href={action.href}
              className="inline-flex items-center gap-2 px-4 py-2 bg-teal-electric text-white rounded-lg text-sm font-medium hover:bg-teal-glow transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-electric"
            >
              {ActionIcon && <ActionIcon className="w-4 h-4" />}
              {action.label}
            </Link>
          ) : (
            <button
              onClick={action.onClick}
              className="inline-flex items-center gap-2 px-4 py-2 bg-teal-electric text-white rounded-lg text-sm font-medium hover:bg-teal-glow transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-electric"
            >
              {ActionIcon && <ActionIcon className="w-4 h-4" />}
              {action.label}
            </button>
          )
        )}
      </div>
    </div>
  );
}

// =============================================================================
// ERROR STATE
// =============================================================================

export interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({
  message = 'Something went wrong',
  onRetry,
  className,
}: ErrorStateProps) {
  return (
    <div
      className={cn(
        'bg-slate-card border border-slate-border rounded-xl p-8',
        className
      )}
    >
      <div className="flex flex-col items-center justify-center text-center">
        <AlertTriangle className="w-12 h-12 mb-3 text-coral-alert" />
        <p className="text-sm text-coral-alert mb-4">{message}</p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="flex items-center gap-2 px-4 py-2 bg-slate-elevated hover:bg-slate-border rounded-lg text-sm text-white transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-electric"
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// LOADING STATE
// =============================================================================

export interface LoadingStateProps {
  message?: string;
  className?: string;
}

export function LoadingState({
  message = 'Loading...',
  className,
}: LoadingStateProps) {
  return (
    <div
      className={cn(
        'bg-slate-card border border-slate-border rounded-xl p-8',
        className
      )}
    >
      <div className="flex flex-col items-center justify-center text-center">
        <div className="w-8 h-8 border-2 border-teal-400 border-t-transparent rounded-full animate-spin mb-3" />
        <p className="text-sm text-slate-muted">{message}</p>
      </div>
    </div>
  );
}

// =============================================================================
// SKELETON COMPONENTS
// =============================================================================

export interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        'skeleton bg-slate-elevated animate-pulse rounded',
        className
      )}
    />
  );
}

export function SkeletonCard({ className }: SkeletonProps) {
  return (
    <div
      className={cn(
        'bg-slate-card border border-slate-border rounded-xl p-5 animate-pulse',
        className
      )}
    >
      <div className="flex items-center gap-3 mb-4">
        <Skeleton className="w-10 h-10 rounded-lg" />
        <div className="flex-1">
          <Skeleton className="h-4 w-24 mb-2" />
          <Skeleton className="h-3 w-32" />
        </div>
      </div>
      <Skeleton className="h-8 w-20 mb-2" />
      <Skeleton className="h-3 w-full" />
    </div>
  );
}

export function SkeletonTable({ rows = 5 }: { rows?: number }) {
  return (
    <div className="bg-slate-card border border-slate-border rounded-xl overflow-hidden">
      <div className="border-b border-slate-border px-4 py-3">
        <Skeleton className="h-4 w-32" />
      </div>
      <table className="w-full">
        <thead>
          <tr className="border-b border-slate-border">
            {[1, 2, 3, 4].map((i) => (
              <th key={i} className="px-4 py-3 text-left">
                <Skeleton className="h-3 w-20" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, i) => (
            <tr key={i} className="border-b border-slate-border/50">
              {[1, 2, 3, 4].map((j) => (
                <td key={j} className="px-4 py-3">
                  <Skeleton className="h-4 w-24" />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// =============================================================================
// SECTION HEADER
// =============================================================================

export interface SectionHeaderProps {
  title: string;
  subtitle?: string;
  action?: React.ReactNode;
  className?: string;
}

export function SectionHeader({
  title,
  subtitle,
  action,
  className,
}: SectionHeaderProps) {
  return (
    <div className={cn('flex items-center justify-between mb-4', className)}>
      <div>
        <h2 className="text-lg font-semibold text-white">{title}</h2>
        {subtitle && <p className="text-sm text-slate-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

// =============================================================================
// STAT GRID
// =============================================================================

export interface StatGridProps {
  children: React.ReactNode;
  columns?: 2 | 3 | 4;
  className?: string;
}

export function StatGrid({ children, columns = 4, className }: StatGridProps) {
  const columnClasses = {
    2: 'grid-cols-1 sm:grid-cols-2',
    3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-2 md:grid-cols-4',
  };

  return (
    <div className={cn('grid gap-4', columnClasses[columns], className)}>
      {children}
    </div>
  );
}

// =============================================================================
// BUTTON
// =============================================================================

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  icon?: LucideIcon;
  iconPosition?: 'left' | 'right';
  loading?: boolean;
}

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  icon: Icon,
  iconPosition = 'left',
  loading,
  disabled,
  className,
  ...props
}: ButtonProps) {
  const variants = {
    primary:
      'bg-gradient-to-r from-teal-electric to-teal-glow text-white hover:shadow-lg hover:shadow-teal-electric/25',
    secondary:
      'bg-slate-elevated border border-slate-border text-white hover:bg-slate-border',
    danger:
      'bg-coral-alert/15 border border-coral-alert/30 text-coral-alert hover:bg-coral-alert/25',
    ghost: 'text-slate-muted hover:text-white hover:bg-slate-elevated',
  };

  const sizes = {
    sm: 'px-3 py-1.5 text-xs',
    md: 'px-4 py-2 text-sm',
    lg: 'px-6 py-3 text-base',
  };

  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-2 font-medium rounded-lg transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-electric focus-visible:ring-offset-2 focus-visible:ring-offset-slate-deep',
        variants[variant],
        sizes[size],
        (disabled || loading) && 'opacity-60 cursor-not-allowed',
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
      ) : Icon && iconPosition === 'left' ? (
        <Icon className="w-4 h-4" />
      ) : null}
      {children}
      {!loading && Icon && iconPosition === 'right' && (
        <Icon className="w-4 h-4" />
      )}
    </button>
  );
}

// =============================================================================
// SEARCH INPUT
// =============================================================================

export interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

export function SearchInput({
  value,
  onChange,
  placeholder = 'Search...',
  className,
}: SearchInputProps) {
  return (
    <div className={cn('relative', className)}>
      <svg
        className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-muted"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
        />
      </svg>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-slate-card border border-slate-border rounded-lg pl-10 pr-4 py-2 text-sm text-white placeholder:text-slate-muted focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
      />
    </div>
  );
}

// =============================================================================
// SELECT
// =============================================================================

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  className?: string;
  'aria-label'?: string;
}

export function Select({
  value,
  onChange,
  options,
  placeholder,
  className,
  'aria-label': ariaLabel,
}: SelectProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label={ariaLabel}
      className={cn(
        'bg-slate-card border border-slate-border rounded-lg px-4 py-2 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50 appearance-none cursor-pointer',
        'bg-[url("data:image/svg+xml,%3csvg xmlns=\'http://www.w3.org/2000/svg\' fill=\'none\' viewBox=\'0 0 20 20\'%3e%3cpath stroke=\'%2364748b\' stroke-linecap=\'round\' stroke-linejoin=\'round\' stroke-width=\'1.5\' d=\'M6 8l4 4 4-4\'/%3e%3c/svg%3e")] bg-[length:1.5em_1.5em] bg-[right_0.5rem_center] bg-no-repeat pr-10',
        className
      )}
    >
      {placeholder && (
        <option value="" disabled>
          {placeholder}
        </option>
      )}
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}

// =============================================================================
// TABS
// =============================================================================

export interface Tab {
  key: string;
  label: string;
  icon?: LucideIcon;
  count?: number;
}

export interface TabsProps {
  tabs: Tab[];
  activeTab: string;
  onChange: (key: string) => void;
  className?: string;
}

export function Tabs({ tabs, activeTab, onChange, className }: TabsProps) {
  return (
    <div
      className={cn(
        'flex items-center gap-1 p-1 bg-slate-elevated rounded-lg',
        className
      )}
    >
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = tab.key === activeTab;

        return (
          <button
            key={tab.key}
            onClick={() => onChange(tab.key)}
            className={cn(
              'flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-electric',
              isActive
                ? 'bg-slate-card text-white shadow-sm'
                : 'text-slate-muted hover:text-white'
            )}
          >
            {Icon && <Icon className="w-4 h-4" />}
            {tab.label}
            {tab.count !== undefined && (
              <span
                className={cn(
                  'px-1.5 py-0.5 rounded text-xs',
                  isActive
                    ? 'bg-teal-electric/20 text-teal-electric'
                    : 'bg-slate-border text-slate-muted'
                )}
              >
                {tab.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

// =============================================================================
// RE-EXPORTS
// =============================================================================

export {
  DashboardShell,
  DashboardLoadingState,
  DashboardErrorState,
  DashboardEmptyState,
} from './DashboardShell';
