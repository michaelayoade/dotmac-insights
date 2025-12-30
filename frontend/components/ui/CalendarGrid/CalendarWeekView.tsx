'use client';

import Image from 'next/image';
import { useMemo } from 'react';
import { cn } from '@/lib/utils';
import type { CalendarEvent, CalendarResource } from './types';
import { getWeekDays, isSameDay, isToday, parseDate, getEventColors, formatHour } from './types';

// =============================================================================
// CALENDAR WEEK VIEW
// =============================================================================

export interface CalendarWeekViewProps {
  currentDate: Date;
  events: CalendarEvent[];
  resources?: CalendarResource[];
  onEventClick?: (event: CalendarEvent) => void;
  onSlotClick?: (date: Date, hour?: number, resourceId?: string | number) => void;
  renderEvent?: (event: CalendarEvent) => React.ReactNode;
  workingHours?: { start: number; end: number };
  singleDay?: boolean;
  className?: string;
}

export function CalendarWeekView({
  currentDate,
  events,
  resources,
  onEventClick,
  onSlotClick,
  renderEvent,
  workingHours = { start: 8, end: 18 },
  singleDay = false,
  className,
}: CalendarWeekViewProps) {
  // Get days to display
  const days = useMemo(() => {
    if (singleDay) {
      return [currentDate];
    }
    return getWeekDays(currentDate);
  }, [currentDate, singleDay]);

  // Generate hours array
  const hours = useMemo(() => {
    return Array.from(
      { length: workingHours.end - workingHours.start },
      (_, i) => workingHours.start + i
    );
  }, [workingHours]);

  // Group events by day and hour
  const eventsBySlot = useMemo(() => {
    const map = new Map<string, CalendarEvent[]>();

    events.forEach((event) => {
      const start = parseDate(event.start);
      const dayKey = start.toISOString().split('T')[0];
      const hour = start.getHours();
      const slotKey = `${dayKey}-${hour}`;

      if (!map.has(slotKey)) {
        map.set(slotKey, []);
      }
      map.get(slotKey)!.push(event);
    });

    return map;
  }, [events]);

  // Resource mode (dispatch board style)
  if (resources && resources.length > 0) {
    return (
      <ResourceView
        days={days}
        hours={hours}
        resources={resources}
        events={events}
        onEventClick={onEventClick}
        onSlotClick={onSlotClick}
        renderEvent={renderEvent}
        className={className}
      />
    );
  }

  // Standard week/day view
  return (
    <div className={cn('', className)}>
      {/* Header with day names */}
      <div className="grid gap-px bg-slate-border rounded-t-lg overflow-hidden" style={{ gridTemplateColumns: `60px repeat(${days.length}, 1fr)` }}>
        <div className="bg-slate-card p-2" />
        {days.map((day, index) => {
          const isTodayDate = isToday(day);
          return (
            <div
              key={index}
              className={cn('bg-slate-card p-2 text-center', isTodayDate && 'bg-teal-electric/10')}
            >
              <div className="text-xs text-slate-muted uppercase">
                {day.toLocaleDateString('en-US', { weekday: 'short' })}
              </div>
              <div
                className={cn(
                  'text-lg font-semibold',
                  isTodayDate ? 'text-teal-electric' : 'text-foreground'
                )}
              >
                {day.getDate()}
              </div>
            </div>
          );
        })}
      </div>

      {/* Time Grid */}
      <div className="grid gap-px bg-slate-border rounded-b-lg overflow-hidden" style={{ gridTemplateColumns: `60px repeat(${days.length}, 1fr)` }}>
        {hours.map((hour) => (
          <>
            {/* Hour Label */}
            <div key={`hour-${hour}`} className="bg-slate-card p-2 text-right">
              <span className="text-xs text-slate-muted">{formatHour(hour)}</span>
            </div>

            {/* Day Slots */}
            {days.map((day, dayIndex) => {
              const dayKey = day.toISOString().split('T')[0];
              const slotKey = `${dayKey}-${hour}`;
              const slotEvents = eventsBySlot.get(slotKey) || [];
              const isTodayDate = isToday(day);

              return (
                <div
                  key={`${dayIndex}-${hour}`}
                  onClick={() => onSlotClick?.(day, hour)}
                  className={cn(
                    'min-h-[60px] bg-slate-card p-1 transition-colors',
                    isTodayDate && 'bg-teal-electric/5',
                    onSlotClick && 'cursor-pointer hover:bg-slate-elevated'
                  )}
                >
                  {slotEvents.map((event) => {
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
                          'w-full text-left px-2 py-1 text-xs rounded border-l-2 mb-1',
                          colors.bg,
                          colors.border,
                          colors.text,
                          onEventClick && 'hover:opacity-80 transition-opacity'
                        )}
                      >
                        <div className="font-medium truncate">{event.title}</div>
                        {!!event.metadata?.location && (
                          <div className="text-[10px] opacity-75 truncate">
                            {String(event.metadata.location)}
                          </div>
                        )}
                      </button>
                    );
                  })}
                </div>
              );
            })}
          </>
        ))}
      </div>
    </div>
  );
}

// =============================================================================
// RESOURCE VIEW (Dispatch Board)
// =============================================================================

interface ResourceViewProps {
  days: Date[];
  hours: number[];
  resources: CalendarResource[];
  events: CalendarEvent[];
  onEventClick?: (event: CalendarEvent) => void;
  onSlotClick?: (date: Date, hour?: number, resourceId?: string | number) => void;
  renderEvent?: (event: CalendarEvent) => React.ReactNode;
  className?: string;
}

function ResourceView({
  days,
  hours,
  resources,
  events,
  onEventClick,
  onSlotClick,
  renderEvent,
  className,
}: ResourceViewProps) {
  // Group events by resource
  const eventsByResource = useMemo(() => {
    const map = new Map<string | number, CalendarEvent[]>();

    events.forEach((event) => {
      if (event.resourceId) {
        if (!map.has(event.resourceId)) {
          map.set(event.resourceId, []);
        }
        map.get(event.resourceId)!.push(event);
      }
    });

    return map;
  }, [events]);

  return (
    <div className={cn('', className)}>
      {/* Header */}
      <div className="grid gap-px bg-slate-border rounded-t-lg overflow-hidden" style={{ gridTemplateColumns: `150px repeat(${days.length}, 1fr)` }}>
        <div className="bg-slate-card p-2 text-sm font-medium text-foreground">Resources</div>
        {days.map((day, index) => {
          const isTodayDate = isToday(day);
          return (
            <div
              key={index}
              className={cn('bg-slate-card p-2 text-center', isTodayDate && 'bg-teal-electric/10')}
            >
              <div className="text-xs text-slate-muted">
                {day.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
              </div>
            </div>
          );
        })}
      </div>

      {/* Resource Rows */}
      <div className="grid gap-px bg-slate-border rounded-b-lg overflow-hidden" style={{ gridTemplateColumns: `150px repeat(${days.length}, 1fr)` }}>
        {resources.map((resource) => {
          const resourceEvents = eventsByResource.get(resource.id) || [];

          return (
            <>
              {/* Resource Info */}
              <div key={`resource-${resource.id}`} className="bg-slate-card p-2 flex items-center gap-2">
                {resource.avatar ? (
                  <Image
                    src={resource.avatar}
                    alt={resource.name}
                    width={32}
                    height={32}
                    sizes="32px"
                    className="w-8 h-8 rounded-full"
                  />
                ) : resource.icon ? (
                  <div className="w-8 h-8 rounded-full bg-slate-elevated flex items-center justify-center">
                    <resource.icon className="w-4 h-4 text-slate-muted" />
                  </div>
                ) : (
                  <div className="w-8 h-8 rounded-full bg-slate-elevated flex items-center justify-center text-sm text-slate-muted">
                    {resource.name.charAt(0)}
                  </div>
                )}
                <div className="min-w-0">
                  <div className="text-sm font-medium text-foreground truncate">{resource.name}</div>
                  {resource.subtitle && (
                    <div className="text-xs text-slate-muted truncate">{resource.subtitle}</div>
                  )}
                </div>
                {resource.status && (
                  <div
                    className={cn(
                      'w-2 h-2 rounded-full ml-auto flex-shrink-0',
                      resource.status === 'available' && 'bg-emerald-500',
                      resource.status === 'busy' && 'bg-amber-500',
                      resource.status === 'offline' && 'bg-slate-500'
                    )}
                  />
                )}
              </div>

              {/* Day Cells */}
              {days.map((day, dayIndex) => {
                const dayKey = day.toISOString().split('T')[0];
                const dayEvents = resourceEvents.filter((e) => {
                  const eventDate = parseDate(e.start);
                  return isSameDay(eventDate, day);
                });
                const isTodayDate = isToday(day);

                return (
                  <div
                    key={`${resource.id}-${dayIndex}`}
                    onClick={() => onSlotClick?.(day, undefined, resource.id)}
                    className={cn(
                      'min-h-[80px] bg-slate-card p-1.5 transition-colors',
                      isTodayDate && 'bg-teal-electric/5',
                      onSlotClick && 'cursor-pointer hover:bg-slate-elevated'
                    )}
                  >
                    <div className="space-y-1">
                      {dayEvents.map((event) => {
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
                        const startTime = parseDate(event.start).toLocaleTimeString('en-US', {
                          hour: 'numeric',
                          minute: '2-digit',
                        });

                        return (
                          <button
                            key={event.id}
                            onClick={(e) => {
                              e.stopPropagation();
                              onEventClick?.(event);
                            }}
                            className={cn(
                              'w-full text-left px-2 py-1 text-xs rounded border-l-2',
                              colors.bg,
                              colors.border,
                              colors.text,
                              onEventClick && 'hover:opacity-80 transition-opacity'
                            )}
                          >
                            <div className="flex items-center justify-between gap-1">
                              <span className="font-medium truncate">{event.title}</span>
                              <span className="text-[10px] opacity-75 flex-shrink-0">{startTime}</span>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </>
          );
        })}
      </div>
    </div>
  );
}

export default CalendarWeekView;
