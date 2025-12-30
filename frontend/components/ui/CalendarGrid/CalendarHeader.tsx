'use client';

import { cn } from '@/lib/utils';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { CalendarView } from './types';

// =============================================================================
// CALENDAR HEADER
// =============================================================================

export interface CalendarHeaderProps {
  /** Current title (month, week, date) */
  title: string;
  /** Current view */
  view: CalendarView;
  /** Available view options */
  availableViews: CalendarView[];
  /** Callback when view changes */
  onViewChange: (view: CalendarView) => void;
  /** Navigate to previous period */
  onPrevious: () => void;
  /** Navigate to next period */
  onNext: () => void;
  /** Navigate to today */
  onToday: () => void;
  /** Custom class name */
  className?: string;
}

const VIEW_LABELS: Record<CalendarView, string> = {
  month: 'Month',
  week: 'Week',
  day: 'Day',
};

export function CalendarHeader({
  title,
  view,
  availableViews,
  onViewChange,
  onPrevious,
  onNext,
  onToday,
  className,
}: CalendarHeaderProps) {
  return (
    <div
      className={cn(
        'flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 border-b border-slate-border',
        className
      )}
    >
      {/* Title and Navigation */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1">
          <button
            onClick={onPrevious}
            className="p-1.5 rounded-lg hover:bg-slate-elevated text-slate-muted hover:text-foreground transition-colors"
            aria-label="Previous"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <button
            onClick={onNext}
            className="p-1.5 rounded-lg hover:bg-slate-elevated text-slate-muted hover:text-foreground transition-colors"
            aria-label="Next"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>

        <h2 className="text-lg font-semibold text-foreground">{title}</h2>

        <button
          onClick={onToday}
          className="px-3 py-1 text-sm rounded-lg bg-slate-elevated hover:bg-slate-border text-foreground transition-colors"
        >
          Today
        </button>
      </div>

      {/* View Selector */}
      {availableViews.length > 1 && (
        <div className="flex items-center gap-1 p-1 bg-slate-elevated rounded-lg">
          {availableViews.map((v) => (
            <button
              key={v}
              onClick={() => onViewChange(v)}
              className={cn(
                'px-3 py-1 text-sm font-medium rounded-md transition-colors',
                view === v
                  ? 'bg-slate-card text-foreground shadow-sm'
                  : 'text-slate-muted hover:text-foreground'
              )}
            >
              {VIEW_LABELS[v]}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default CalendarHeader;
