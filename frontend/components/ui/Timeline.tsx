'use client';

import { cn } from '@/lib/utils';
import { LucideIcon, Circle } from 'lucide-react';
import { VARIANT_COLORS, type Variant } from '@/lib/design-tokens';

// =============================================================================
// TIMELINE
// =============================================================================

export interface TimelineItem {
  id: string;
  /** Timestamp for the event */
  timestamp: string | Date;
  /** Icon to display (defaults to Circle) */
  icon?: LucideIcon;
  /** Variant for icon color */
  variant?: Variant;
  /** Main title/label */
  title: string;
  /** Optional description */
  description?: string;
  /** Optional actor/user who performed the action */
  actor?: string;
  /** Optional metadata to display */
  metadata?: React.ReactNode;
}

export interface TimelineProps {
  /** Array of timeline items */
  items: TimelineItem[];
  /** Custom render function for items */
  renderItem?: (item: TimelineItem, index: number) => React.ReactNode;
  /** Show loading state */
  loading?: boolean;
  /** Empty state message */
  emptyMessage?: string;
  /** Maximum items to show (with "show more" behavior) */
  maxItems?: number;
  /** Callback when "show more" is clicked */
  onShowMore?: () => void;
  /** Whether more items are available */
  hasMore?: boolean;
  /** Custom class name */
  className?: string;
}

/**
 * Format a timestamp for display
 */
function formatTimestamp(timestamp: string | Date): string {
  const date = typeof timestamp === 'string' ? new Date(timestamp) : timestamp;
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'Just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: date.getFullYear() !== now.getFullYear() ? 'numeric' : undefined,
  });
}

export function Timeline({
  items,
  renderItem,
  loading = false,
  emptyMessage = 'No activity yet',
  maxItems,
  onShowMore,
  hasMore,
  className,
}: TimelineProps) {
  const displayItems = maxItems ? items.slice(0, maxItems) : items;

  if (loading) {
    return (
      <div className={cn('space-y-4', className)}>
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex gap-3 animate-pulse">
            <div className="w-8 h-8 rounded-full bg-slate-elevated" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-32 bg-slate-elevated rounded" />
              <div className="h-3 w-48 bg-slate-elevated rounded" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className={cn('text-center py-8 text-slate-muted text-sm', className)}>
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className={cn('relative', className)}>
      {/* Vertical line */}
      <div className="absolute left-4 top-2 bottom-2 w-px bg-slate-border" />

      <div className="space-y-4">
        {displayItems.map((item, index) => {
          if (renderItem) {
            return (
              <div key={item.id} className="relative pl-10">
                {renderItem(item, index)}
              </div>
            );
          }

          const Icon = item.icon || Circle;
          const colors = VARIANT_COLORS[item.variant || 'default'];

          return (
            <div key={item.id} className="relative flex gap-3 pl-0">
              {/* Icon */}
              <div
                className={cn(
                  'relative z-10 flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center',
                  colors.bg,
                  'border',
                  colors.border
                )}
              >
                <Icon className={cn('w-4 h-4', colors.icon)} />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0 pt-1">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-foreground truncate">{item.title}</p>
                    {item.actor && (
                      <p className="text-xs text-slate-muted">by {item.actor}</p>
                    )}
                  </div>
                  <span className="flex-shrink-0 text-xs text-slate-muted">
                    {formatTimestamp(item.timestamp)}
                  </span>
                </div>
                {item.description && (
                  <p className="mt-1 text-sm text-slate-muted line-clamp-2">{item.description}</p>
                )}
                {item.metadata && <div className="mt-2">{item.metadata}</div>}
              </div>
            </div>
          );
        })}
      </div>

      {/* Show more button */}
      {(hasMore || (maxItems && items.length > maxItems)) && onShowMore && (
        <button
          onClick={onShowMore}
          className="mt-4 w-full py-2 text-sm text-teal-electric hover:text-teal-glow transition-colors"
        >
          Show more
        </button>
      )}
    </div>
  );
}

// =============================================================================
// TIMELINE ITEM (Standalone)
// =============================================================================

export interface TimelineItemComponentProps {
  icon?: LucideIcon;
  variant?: Variant;
  title: string;
  timestamp?: string | Date;
  description?: string;
  actor?: string;
  children?: React.ReactNode;
  className?: string;
}

export function TimelineItemComponent({
  icon: Icon = Circle,
  variant = 'default',
  title,
  timestamp,
  description,
  actor,
  children,
  className,
}: TimelineItemComponentProps) {
  const colors = VARIANT_COLORS[variant];

  return (
    <div className={cn('flex gap-3', className)}>
      {/* Icon */}
      <div
        className={cn(
          'flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center',
          colors.bg,
          'border',
          colors.border
        )}
      >
        <Icon className={cn('w-4 h-4', colors.icon)} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 pt-1">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <p className="text-sm font-medium text-foreground">{title}</p>
            {actor && <p className="text-xs text-slate-muted">by {actor}</p>}
          </div>
          {timestamp && (
            <span className="flex-shrink-0 text-xs text-slate-muted">
              {formatTimestamp(timestamp)}
            </span>
          )}
        </div>
        {description && (
          <p className="mt-1 text-sm text-slate-muted">{description}</p>
        )}
        {children}
      </div>
    </div>
  );
}

export default Timeline;
