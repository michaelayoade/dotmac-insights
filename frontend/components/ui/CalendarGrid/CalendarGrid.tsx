'use client';

import { useState, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { CalendarHeader } from './CalendarHeader';
import { CalendarMonthView } from './CalendarMonthView';
import { CalendarWeekView } from './CalendarWeekView';
import type { CalendarView, CalendarEvent, CalendarResource } from './types';

// =============================================================================
// CALENDAR GRID
// =============================================================================

export interface CalendarGridProps {
  /** Current view mode */
  view?: CalendarView;
  /** Callback when view changes */
  onViewChange?: (view: CalendarView) => void;
  /** Currently displayed date */
  currentDate?: Date;
  /** Callback when date changes */
  onDateChange?: (date: Date) => void;
  /** Events to display */
  events: CalendarEvent[];
  /** Resources for resource view (dispatch board) */
  resources?: CalendarResource[];
  /** Callback when an event is clicked */
  onEventClick?: (event: CalendarEvent) => void;
  /** Callback when a time slot is clicked */
  onSlotClick?: (date: Date, hour?: number, resourceId?: string | number) => void;
  /** Custom render function for events */
  renderEvent?: (event: CalendarEvent) => React.ReactNode;
  /** Show header with navigation */
  showHeader?: boolean;
  /** Available views */
  availableViews?: CalendarView[];
  /** Loading state */
  loading?: boolean;
  /** Controlled vs uncontrolled mode */
  controlled?: boolean;
  /** Working hours (for week/day view) */
  workingHours?: { start: number; end: number };
  /** Custom class name */
  className?: string;
  /** Custom class for the grid */
  gridClassName?: string;
}

export function CalendarGrid({
  view: viewProp = 'month',
  onViewChange,
  currentDate: currentDateProp,
  onDateChange,
  events,
  resources,
  onEventClick,
  onSlotClick,
  renderEvent,
  showHeader = true,
  availableViews = ['month', 'week'],
  loading = false,
  controlled = false,
  workingHours = { start: 8, end: 18 },
  className,
  gridClassName,
}: CalendarGridProps) {
  // Internal state for uncontrolled mode
  const [internalView, setInternalView] = useState<CalendarView>(viewProp);
  const [internalDate, setInternalDate] = useState<Date>(() => currentDateProp ?? new Date());
  const fallbackDate = useMemo(() => new Date(), []);

  // Use controlled or internal state
  const view = controlled && onViewChange ? viewProp : internalView;
  const currentDate = controlled && onDateChange ? (currentDateProp ?? fallbackDate) : internalDate;

  const handleViewChange = (newView: CalendarView) => {
    if (controlled && onViewChange) {
      onViewChange(newView);
    } else {
      setInternalView(newView);
    }
  };

  const handleDateChange = (newDate: Date) => {
    if (controlled && onDateChange) {
      onDateChange(newDate);
    } else {
      setInternalDate(newDate);
    }
  };

  // Navigation handlers
  const goToPrevious = () => {
    const newDate = new Date(currentDate);
    if (view === 'month') {
      newDate.setMonth(newDate.getMonth() - 1);
    } else if (view === 'week') {
      newDate.setDate(newDate.getDate() - 7);
    } else {
      newDate.setDate(newDate.getDate() - 1);
    }
    handleDateChange(newDate);
  };

  const goToNext = () => {
    const newDate = new Date(currentDate);
    if (view === 'month') {
      newDate.setMonth(newDate.getMonth() + 1);
    } else if (view === 'week') {
      newDate.setDate(newDate.getDate() + 7);
    } else {
      newDate.setDate(newDate.getDate() + 1);
    }
    handleDateChange(newDate);
  };

  const goToToday = () => {
    handleDateChange(new Date());
  };

  // Format title based on view
  const title = useMemo(() => {
    const options: Intl.DateTimeFormatOptions = { year: 'numeric' };

    if (view === 'month') {
      options.month = 'long';
    } else if (view === 'week') {
      options.month = 'short';
      options.day = 'numeric';
    } else {
      options.month = 'long';
      options.day = 'numeric';
      options.weekday = 'long';
    }

    return currentDate.toLocaleDateString('en-US', options);
  }, [currentDate, view]);

  if (loading) {
    return (
      <div className={cn('bg-slate-card border border-slate-border rounded-xl', className)}>
        {showHeader && (
          <div className="p-4 border-b border-slate-border animate-pulse">
            <div className="flex items-center justify-between">
              <div className="h-6 w-40 bg-slate-elevated rounded" />
              <div className="flex gap-2">
                <div className="h-8 w-20 bg-slate-elevated rounded" />
                <div className="h-8 w-20 bg-slate-elevated rounded" />
              </div>
            </div>
          </div>
        )}
        <div className="p-4">
          <div className="grid grid-cols-7 gap-2">
            {Array.from({ length: 35 }).map((_, i) => (
              <div key={i} className="h-20 bg-slate-elevated rounded animate-pulse" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={cn('bg-slate-card border border-slate-border rounded-xl overflow-hidden', className)}>
      {showHeader && (
        <CalendarHeader
          title={title}
          view={view}
          availableViews={availableViews}
          onViewChange={handleViewChange}
          onPrevious={goToPrevious}
          onNext={goToNext}
          onToday={goToToday}
        />
      )}

      <div className={cn('p-4', gridClassName)}>
        {view === 'month' && (
          <CalendarMonthView
            currentDate={currentDate}
            events={events}
            onEventClick={onEventClick}
            onSlotClick={onSlotClick}
            renderEvent={renderEvent}
          />
        )}

        {view === 'week' && (
          <CalendarWeekView
            currentDate={currentDate}
            events={events}
            resources={resources}
            onEventClick={onEventClick}
            onSlotClick={onSlotClick}
            renderEvent={renderEvent}
            workingHours={workingHours}
          />
        )}

        {view === 'day' && (
          <CalendarWeekView
            currentDate={currentDate}
            events={events}
            resources={resources}
            onEventClick={onEventClick}
            onSlotClick={onSlotClick}
            renderEvent={renderEvent}
            workingHours={workingHours}
            singleDay
          />
        )}
      </div>
    </div>
  );
}

export default CalendarGrid;
