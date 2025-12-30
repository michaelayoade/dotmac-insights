'use client';

import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import type { CalendarEvent } from './types';
import { getMonthDays, isSameDay, isToday, parseDate, getEventColors } from './types';

// =============================================================================
// CALENDAR MONTH VIEW
// =============================================================================

export interface CalendarMonthViewProps {
  currentDate: Date;
  events: CalendarEvent[];
  onEventClick?: (event: CalendarEvent) => void;
  onSlotClick?: (date: Date) => void;
  renderEvent?: (event: CalendarEvent) => React.ReactNode;
  maxEventsPerDay?: number;
  className?: string;
}

const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export function CalendarMonthView({
  currentDate,
  events,
  onEventClick,
  onSlotClick,
  renderEvent,
  maxEventsPerDay = 3,
  className,
}: CalendarMonthViewProps) {
  // Get all days to display
  const days = useMemo(() => getMonthDays(currentDate), [currentDate]);

  // Group events by date
  const eventsByDate = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();

    events.forEach((event) => {
      const start = parseDate(event.start);
      const key = start.toISOString().split('T')[0];

      if (!map.has(key)) {
        map.set(key, []);
      }
      map.get(key)!.push(event);
    });

    return map;
  }, [events]);

  const currentMonth = currentDate.getMonth();

  return (
    <div className={cn('', className)}>
      {/* Weekday Headers */}
      <div className="grid grid-cols-7 gap-px mb-2">
        {WEEKDAYS.map((day) => (
          <div
            key={day}
            className="py-2 text-center text-xs font-medium text-slate-muted uppercase tracking-wider"
          >
            {day}
          </div>
        ))}
      </div>

      {/* Calendar Grid */}
      <div className="grid grid-cols-7 gap-px bg-slate-border rounded-lg overflow-hidden">
        {days.map((day, index) => {
          const dateKey = day.toISOString().split('T')[0];
          const dayEvents = eventsByDate.get(dateKey) || [];
          const isCurrentMonth = day.getMonth() === currentMonth;
          const isTodayDate = isToday(day);
          const displayEvents = dayEvents.slice(0, maxEventsPerDay);
          const moreCount = dayEvents.length - maxEventsPerDay;

          return (
            <div
              key={index}
              onClick={() => onSlotClick?.(day)}
              className={cn(
                'min-h-[100px] p-1.5 bg-slate-card transition-colors',
                !isCurrentMonth && 'bg-slate-elevated/50',
                onSlotClick && 'cursor-pointer hover:bg-slate-elevated'
              )}
            >
              {/* Day Number */}
              <div className="flex justify-end mb-1">
                <span
                  className={cn(
                    'w-7 h-7 flex items-center justify-center text-sm rounded-full',
                    isTodayDate
                      ? 'bg-teal-electric text-foreground font-semibold'
                      : isCurrentMonth
                      ? 'text-foreground'
                      : 'text-slate-muted'
                  )}
                >
                  {day.getDate()}
                </span>
              </div>

              {/* Events */}
              <div className="space-y-1">
                {displayEvents.map((event) => {
                  if (renderEvent) {
                    return (
                      <div
                        key={event.id}
                        onClick={(e) => {
                          e.stopPropagation();
                          onEventClick?.(event);
                        }}
                      >
                        {renderEvent(event)}
                      </div>
                    );
                  }

                  const colors = getEventColors(event.color);

                  return (
                    <button
                      key={event.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        onEventClick?.(event);
                      }}
                      className={cn(
                        'w-full text-left px-1.5 py-0.5 text-xs rounded truncate border-l-2',
                        colors.bg,
                        colors.border,
                        colors.text,
                        onEventClick && 'hover:opacity-80 transition-opacity'
                      )}
                      title={event.title}
                    >
                      {event.title}
                    </button>
                  );
                })}

                {moreCount > 0 && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      // Could open a modal showing all events
                    }}
                    className="w-full text-left px-1.5 py-0.5 text-xs text-slate-muted hover:text-foreground transition-colors"
                  >
                    +{moreCount} more
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default CalendarMonthView;
