// =============================================================================
// CALENDAR GRID - Barrel Export
// =============================================================================

export { CalendarGrid, type CalendarGridProps } from './CalendarGrid';
export { CalendarHeader, type CalendarHeaderProps } from './CalendarHeader';
export { CalendarMonthView, type CalendarMonthViewProps } from './CalendarMonthView';
export { CalendarWeekView, type CalendarWeekViewProps } from './CalendarWeekView';
export {
  type CalendarView,
  type CalendarEvent,
  type CalendarResource,
  EVENT_COLORS,
  getEventColors,
  isSameDay,
  isToday,
  getWeekDays,
  getMonthDays,
  formatHour,
  parseDate,
} from './types';

// Default export
export { CalendarGrid as default } from './CalendarGrid';
