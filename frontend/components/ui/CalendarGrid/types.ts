import { LucideIcon } from 'lucide-react';

// =============================================================================
// CALENDAR TYPES
// =============================================================================

export type CalendarView = 'month' | 'week' | 'day';

/**
 * A calendar event
 */
export interface CalendarEvent {
  id: string | number;
  /** Event title */
  title: string;
  /** Start date/time */
  start: Date | string;
  /** End date/time (optional for all-day events) */
  end?: Date | string;
  /** Whether this is an all-day event */
  allDay?: boolean;
  /** Resource/row ID for resource views */
  resourceId?: string | number;
  /** Color key or hex color */
  color?: string;
  /** Event type/category */
  type?: string;
  /** Priority */
  priority?: 'low' | 'medium' | 'high' | 'urgent';
  /** Status */
  status?: string;
  /** Additional metadata */
  metadata?: Record<string, unknown>;
}

/**
 * A resource row for resource-based views (dispatch board, team schedule)
 */
export interface CalendarResource {
  id: string | number;
  /** Display name */
  name: string;
  /** Avatar or icon */
  avatar?: string;
  icon?: LucideIcon;
  /** Status indicator */
  status?: 'available' | 'busy' | 'offline';
  /** Additional info to display */
  subtitle?: string;
  /** Group/category */
  group?: string;
  /** Metadata */
  metadata?: Record<string, unknown>;
}

/**
 * Event colors
 */
export const EVENT_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  default: { bg: 'bg-slate-500/20', border: 'border-slate-500', text: 'text-slate-300' },
  blue: { bg: 'bg-blue-500/20', border: 'border-blue-500', text: 'text-blue-300' },
  cyan: { bg: 'bg-cyan-500/20', border: 'border-cyan-500', text: 'text-cyan-300' },
  teal: { bg: 'bg-teal-500/20', border: 'border-teal-500', text: 'text-teal-300' },
  emerald: { bg: 'bg-emerald-500/20', border: 'border-emerald-500', text: 'text-emerald-300' },
  green: { bg: 'bg-green-500/20', border: 'border-green-500', text: 'text-green-300' },
  amber: { bg: 'bg-amber-500/20', border: 'border-amber-500', text: 'text-amber-300' },
  orange: { bg: 'bg-orange-500/20', border: 'border-orange-500', text: 'text-orange-300' },
  red: { bg: 'bg-red-500/20', border: 'border-red-500', text: 'text-red-300' },
  rose: { bg: 'bg-rose-500/20', border: 'border-rose-500', text: 'text-rose-300' },
  purple: { bg: 'bg-purple-500/20', border: 'border-purple-500', text: 'text-purple-300' },
  indigo: { bg: 'bg-indigo-500/20', border: 'border-indigo-500', text: 'text-indigo-300' },
};

export function getEventColors(color?: string) {
  return EVENT_COLORS[color || 'default'] || EVENT_COLORS.default;
}

/**
 * Date utility functions
 */
export function isSameDay(date1: Date, date2: Date): boolean {
  return (
    date1.getFullYear() === date2.getFullYear() &&
    date1.getMonth() === date2.getMonth() &&
    date1.getDate() === date2.getDate()
  );
}

export function isToday(date: Date): boolean {
  return isSameDay(date, new Date());
}

export function getWeekDays(date: Date): Date[] {
  const start = new Date(date);
  start.setDate(start.getDate() - start.getDay());

  return Array.from({ length: 7 }, (_, i) => {
    const day = new Date(start);
    day.setDate(start.getDate() + i);
    return day;
  });
}

export function getMonthDays(date: Date): Date[] {
  const year = date.getFullYear();
  const month = date.getMonth();

  // First day of the month
  const firstDay = new Date(year, month, 1);
  // Last day of the month
  const lastDay = new Date(year, month + 1, 0);

  // Start from the Sunday of the first week
  const start = new Date(firstDay);
  start.setDate(start.getDate() - start.getDay());

  // End on the Saturday of the last week
  const end = new Date(lastDay);
  end.setDate(end.getDate() + (6 - end.getDay()));

  const days: Date[] = [];
  const current = new Date(start);

  while (current <= end) {
    days.push(new Date(current));
    current.setDate(current.getDate() + 1);
  }

  return days;
}

export function formatHour(hour: number): string {
  const period = hour >= 12 ? 'PM' : 'AM';
  const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
  return `${displayHour} ${period}`;
}

export function parseDate(date: Date | string): Date {
  return typeof date === 'string' ? new Date(date) : date;
}
