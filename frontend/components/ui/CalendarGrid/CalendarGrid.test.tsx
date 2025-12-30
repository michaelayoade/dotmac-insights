/**
 * CalendarGrid Component Tests
 *
 * Tests for calendar functionality including:
 * - View modes (month, week, day)
 * - Navigation
 * - Event rendering
 * - Loading states
 * - Custom renderers
 * - Utilities
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CalendarGrid } from './CalendarGrid';
import { CalendarHeader } from './CalendarHeader';
import { CalendarMonthView } from './CalendarMonthView';
import { CalendarWeekView } from './CalendarWeekView';
import {
  getEventColors,
  EVENT_COLORS,
  isSameDay,
  isToday,
  getWeekDays,
  getMonthDays,
  formatHour,
  parseDate,
} from './types';
import type { CalendarEvent, CalendarResource } from './types';

// =============================================================================
// Mock Data
// =============================================================================

const today = new Date();
const mockEvents: CalendarEvent[] = [
  {
    id: 1,
    title: 'Team Meeting',
    start: new Date(today.getFullYear(), today.getMonth(), 15, 10, 0),
    end: new Date(today.getFullYear(), today.getMonth(), 15, 11, 0),
    color: 'blue',
  },
  {
    id: 2,
    title: 'Project Deadline',
    start: new Date(today.getFullYear(), today.getMonth(), 20, 14, 0),
    allDay: true,
    color: 'red',
  },
  {
    id: 3,
    title: 'Client Call',
    start: new Date(today.getFullYear(), today.getMonth(), 15, 14, 0),
    end: new Date(today.getFullYear(), today.getMonth(), 15, 15, 0),
    color: 'teal',
    resourceId: 'user-1',
  },
];

const mockResources: CalendarResource[] = [
  { id: 'user-1', name: 'John Doe', status: 'available', subtitle: 'Developer' },
  { id: 'user-2', name: 'Jane Smith', status: 'busy', subtitle: 'Designer' },
  { id: 'user-3', name: 'Bob Johnson', status: 'offline' },
];

// =============================================================================
// CalendarGrid Tests
// =============================================================================

describe('CalendarGrid', () => {
  describe('Rendering', () => {
    it('renders with default month view', () => {
      render(<CalendarGrid events={mockEvents} />);

      // Should show weekday headers
      expect(screen.getByText('Sun')).toBeInTheDocument();
      expect(screen.getByText('Mon')).toBeInTheDocument();
      expect(screen.getByText('Tue')).toBeInTheDocument();
      expect(screen.getByText('Wed')).toBeInTheDocument();
      expect(screen.getByText('Thu')).toBeInTheDocument();
      expect(screen.getByText('Fri')).toBeInTheDocument();
      expect(screen.getByText('Sat')).toBeInTheDocument();
    });

    it('renders week view when specified', () => {
      render(<CalendarGrid events={mockEvents} view="week" />);

      // Week view shows time slots
      expect(screen.getByText('8 AM')).toBeInTheDocument();
      expect(screen.getByText('9 AM')).toBeInTheDocument();
    });

    it('renders events', () => {
      render(
        <CalendarGrid
          events={mockEvents}
          currentDate={new Date(today.getFullYear(), today.getMonth(), 15)}
        />
      );

      expect(screen.getByText('Team Meeting')).toBeInTheDocument();
    });

    it('shows header by default', () => {
      render(<CalendarGrid events={mockEvents} />);
      expect(screen.getByText('Today')).toBeInTheDocument();
    });

    it('hides header when showHeader is false', () => {
      render(<CalendarGrid events={mockEvents} showHeader={false} />);
      expect(screen.queryByText('Today')).not.toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('renders skeleton when loading', () => {
      const { container } = render(<CalendarGrid events={[]} loading={true} />);

      const skeletons = container.querySelectorAll('.animate-pulse');
      expect(skeletons.length).toBeGreaterThan(0);
    });

    it('does not render events when loading', () => {
      render(<CalendarGrid events={mockEvents} loading={true} />);
      expect(screen.queryByText('Team Meeting')).not.toBeInTheDocument();
    });
  });

  describe('Navigation', () => {
    it('navigates to previous period', async () => {
      const onDateChange = vi.fn();
      const user = userEvent.setup();

      render(
        <CalendarGrid
          events={[]}
          controlled={true}
          onDateChange={onDateChange}
          currentDate={new Date(2024, 5, 15)} // June 15, 2024
        />
      );

      const prevButton = screen.getByLabelText('Previous');
      await user.click(prevButton);

      expect(onDateChange).toHaveBeenCalled();
      const newDate = onDateChange.mock.calls[0][0];
      expect(newDate.getMonth()).toBe(4); // May
    });

    it('navigates to next period', async () => {
      const onDateChange = vi.fn();
      const user = userEvent.setup();

      render(
        <CalendarGrid
          events={[]}
          controlled={true}
          onDateChange={onDateChange}
          currentDate={new Date(2024, 5, 15)}
        />
      );

      const nextButton = screen.getByLabelText('Next');
      await user.click(nextButton);

      expect(onDateChange).toHaveBeenCalled();
      const newDate = onDateChange.mock.calls[0][0];
      expect(newDate.getMonth()).toBe(6); // July
    });

    it('navigates to today', async () => {
      const onDateChange = vi.fn();
      const user = userEvent.setup();

      render(
        <CalendarGrid
          events={[]}
          controlled={true}
          onDateChange={onDateChange}
          currentDate={new Date(2024, 5, 15)}
        />
      );

      const todayButton = screen.getByText('Today');
      await user.click(todayButton);

      expect(onDateChange).toHaveBeenCalled();
      const newDate = onDateChange.mock.calls[0][0];
      expect(isSameDay(newDate, new Date())).toBe(true);
    });

    it('navigates by week in week view', async () => {
      const onDateChange = vi.fn();
      const user = userEvent.setup();

      render(
        <CalendarGrid
          events={[]}
          view="week"
          controlled={true}
          onDateChange={onDateChange}
          currentDate={new Date(2024, 5, 15)}
        />
      );

      const nextButton = screen.getByLabelText('Next');
      await user.click(nextButton);

      const newDate = onDateChange.mock.calls[0][0];
      expect(newDate.getDate()).toBe(22); // +7 days
    });

    it('navigates by day in day view', async () => {
      const onDateChange = vi.fn();
      const user = userEvent.setup();

      render(
        <CalendarGrid
          events={[]}
          view="day"
          controlled={true}
          onDateChange={onDateChange}
          currentDate={new Date(2024, 5, 15)}
        />
      );

      const nextButton = screen.getByLabelText('Next');
      await user.click(nextButton);

      const newDate = onDateChange.mock.calls[0][0];
      expect(newDate.getDate()).toBe(16); // +1 day
    });
  });

  describe('View Changes', () => {
    it('changes view when view selector is clicked', async () => {
      const onViewChange = vi.fn();
      const user = userEvent.setup();

      render(
        <CalendarGrid
          events={[]}
          controlled={true}
          onViewChange={onViewChange}
          availableViews={['month', 'week', 'day']}
        />
      );

      const weekButton = screen.getByText('Week');
      await user.click(weekButton);

      expect(onViewChange).toHaveBeenCalledWith('week');
    });

    it('shows available views in header', () => {
      render(
        <CalendarGrid
          events={[]}
          availableViews={['month', 'week', 'day']}
        />
      );

      expect(screen.getByText('Month')).toBeInTheDocument();
      expect(screen.getByText('Week')).toBeInTheDocument();
      expect(screen.getByText('Day')).toBeInTheDocument();
    });

    it('hides view selector when only one view available', () => {
      render(<CalendarGrid events={[]} availableViews={['month']} />);

      // Only one view, so selector should be hidden
      expect(screen.queryByText('Week')).not.toBeInTheDocument();
      expect(screen.queryByText('Day')).not.toBeInTheDocument();
    });
  });

  describe('Event Interactions', () => {
    it('calls onEventClick when event is clicked', async () => {
      const onEventClick = vi.fn();
      const user = userEvent.setup();

      render(
        <CalendarGrid
          events={mockEvents}
          onEventClick={onEventClick}
          currentDate={new Date(today.getFullYear(), today.getMonth(), 15)}
        />
      );

      const event = screen.getByText('Team Meeting');
      await user.click(event);

      expect(onEventClick).toHaveBeenCalledWith(mockEvents[0]);
    });

    it('calls onSlotClick when empty slot is clicked', async () => {
      const onSlotClick = vi.fn();
      const user = userEvent.setup();

      const { container } = render(
        <CalendarGrid
          events={[]}
          onSlotClick={onSlotClick}
          currentDate={new Date(2024, 5, 15)}
        />
      );

      // Click on a day cell
      const dayCell = container.querySelector('.min-h-\\[100px\\]');
      if (dayCell) {
        await user.click(dayCell);
        expect(onSlotClick).toHaveBeenCalled();
      }
    });
  });

  describe('Custom Renderers', () => {
    it('uses custom event renderer', () => {
      const renderEvent = (event: CalendarEvent) => (
        <div data-testid={`custom-event-${event.id}`}>
          Custom: {event.title}
        </div>
      );

      render(
        <CalendarGrid
          events={mockEvents}
          renderEvent={renderEvent}
          currentDate={new Date(today.getFullYear(), today.getMonth(), 15)}
        />
      );

      expect(screen.getByTestId('custom-event-1')).toBeInTheDocument();
      expect(screen.getByText('Custom: Team Meeting')).toBeInTheDocument();
    });
  });

  describe('Controlled vs Uncontrolled', () => {
    it('works in uncontrolled mode', async () => {
      const user = userEvent.setup();

      render(<CalendarGrid events={[]} />);

      // Should be able to navigate without callbacks
      const nextButton = screen.getByLabelText('Next');
      await user.click(nextButton);

      // No error should occur
    });

    it('uses internal state in uncontrolled mode', async () => {
      const user = userEvent.setup();
      const currentMonth = today.toLocaleDateString('en-US', {
        month: 'long',
        year: 'numeric',
      });

      render(<CalendarGrid events={[]} />);

      // Should show current month
      expect(screen.getByText(currentMonth)).toBeInTheDocument();

      // Navigate to next month
      const nextButton = screen.getByLabelText('Next');
      await user.click(nextButton);

      // Month should have changed
      expect(screen.queryByText(currentMonth)).not.toBeInTheDocument();
    });
  });

  describe('Working Hours', () => {
    it('applies custom working hours in week view', () => {
      render(
        <CalendarGrid
          events={[]}
          view="week"
          workingHours={{ start: 9, end: 17 }}
        />
      );

      expect(screen.getByText('9 AM')).toBeInTheDocument();
      expect(screen.getByText('4 PM')).toBeInTheDocument();
      expect(screen.queryByText('8 AM')).not.toBeInTheDocument();
      expect(screen.queryByText('5 PM')).not.toBeInTheDocument();
    });
  });

  describe('CSS Classes', () => {
    it('applies custom className', () => {
      const { container } = render(
        <CalendarGrid events={[]} className="custom-calendar" />
      );
      expect(container.querySelector('.custom-calendar')).toBeInTheDocument();
    });

    it('applies gridClassName', () => {
      const { container } = render(
        <CalendarGrid events={[]} gridClassName="custom-grid" />
      );
      expect(container.querySelector('.custom-grid')).toBeInTheDocument();
    });
  });
});

// =============================================================================
// CalendarHeader Tests
// =============================================================================

describe('CalendarHeader', () => {
  const defaultProps = {
    title: 'June 2024',
    view: 'month' as const,
    availableViews: ['month', 'week', 'day'] as const,
    onViewChange: vi.fn(),
    onPrevious: vi.fn(),
    onNext: vi.fn(),
    onToday: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders title', () => {
    render(<CalendarHeader {...defaultProps} />);
    expect(screen.getByText('June 2024')).toBeInTheDocument();
  });

  it('renders navigation buttons', () => {
    render(<CalendarHeader {...defaultProps} />);
    expect(screen.getByLabelText('Previous')).toBeInTheDocument();
    expect(screen.getByLabelText('Next')).toBeInTheDocument();
    expect(screen.getByText('Today')).toBeInTheDocument();
  });

  it('calls onPrevious when previous button clicked', async () => {
    const user = userEvent.setup();
    render(<CalendarHeader {...defaultProps} />);

    await user.click(screen.getByLabelText('Previous'));
    expect(defaultProps.onPrevious).toHaveBeenCalled();
  });

  it('calls onNext when next button clicked', async () => {
    const user = userEvent.setup();
    render(<CalendarHeader {...defaultProps} />);

    await user.click(screen.getByLabelText('Next'));
    expect(defaultProps.onNext).toHaveBeenCalled();
  });

  it('calls onToday when today button clicked', async () => {
    const user = userEvent.setup();
    render(<CalendarHeader {...defaultProps} />);

    await user.click(screen.getByText('Today'));
    expect(defaultProps.onToday).toHaveBeenCalled();
  });

  it('renders view selector', () => {
    render(<CalendarHeader {...defaultProps} />);

    expect(screen.getByText('Month')).toBeInTheDocument();
    expect(screen.getByText('Week')).toBeInTheDocument();
    expect(screen.getByText('Day')).toBeInTheDocument();
  });

  it('highlights current view', () => {
    render(<CalendarHeader {...defaultProps} view="week" />);

    const weekButton = screen.getByText('Week');
    expect(weekButton).toHaveClass('bg-slate-card');
  });

  it('calls onViewChange when view button clicked', async () => {
    const user = userEvent.setup();
    render(<CalendarHeader {...defaultProps} />);

    await user.click(screen.getByText('Week'));
    expect(defaultProps.onViewChange).toHaveBeenCalledWith('week');
  });

  it('hides view selector when only one view', () => {
    render(
      <CalendarHeader {...defaultProps} availableViews={['month']} />
    );

    expect(screen.queryByText('Week')).not.toBeInTheDocument();
    expect(screen.queryByText('Day')).not.toBeInTheDocument();
  });
});

// =============================================================================
// CalendarMonthView Tests
// =============================================================================

describe('CalendarMonthView', () => {
  it('renders weekday headers', () => {
    render(
      <CalendarMonthView
        currentDate={new Date(2024, 5, 15)}
        events={[]}
      />
    );

    expect(screen.getByText('Sun')).toBeInTheDocument();
    expect(screen.getByText('Sat')).toBeInTheDocument();
  });

  it('renders days of the month', () => {
    render(
      <CalendarMonthView
        currentDate={new Date(2024, 5, 15)} // June 2024
        events={[]}
      />
    );

    // June 1st
    expect(screen.getByText('1')).toBeInTheDocument();
    // June 30th
    expect(screen.getByText('30')).toBeInTheDocument();
  });

  it('renders events on correct days', () => {
    const events = [
      {
        id: 1,
        title: 'Test Event',
        start: new Date(2024, 5, 15, 10, 0),
      },
    ];

    render(
      <CalendarMonthView
        currentDate={new Date(2024, 5, 15)}
        events={events}
      />
    );

    expect(screen.getByText('Test Event')).toBeInTheDocument();
  });

  it('limits events per day', () => {
    const events = Array.from({ length: 5 }, (_, i) => ({
      id: i + 1,
      title: `Event ${i + 1}`,
      start: new Date(2024, 5, 15, 10 + i, 0),
    }));

    render(
      <CalendarMonthView
        currentDate={new Date(2024, 5, 15)}
        events={events}
        maxEventsPerDay={3}
      />
    );

    expect(screen.getByText('Event 1')).toBeInTheDocument();
    expect(screen.getByText('Event 2')).toBeInTheDocument();
    expect(screen.getByText('Event 3')).toBeInTheDocument();
    expect(screen.queryByText('Event 4')).not.toBeInTheDocument();
    expect(screen.getByText('+2 more')).toBeInTheDocument();
  });

  it('calls onEventClick when event clicked', async () => {
    const onEventClick = vi.fn();
    const user = userEvent.setup();
    const events = [
      { id: 1, title: 'Test Event', start: new Date(2024, 5, 15) },
    ];

    render(
      <CalendarMonthView
        currentDate={new Date(2024, 5, 15)}
        events={events}
        onEventClick={onEventClick}
      />
    );

    await user.click(screen.getByText('Test Event'));
    expect(onEventClick).toHaveBeenCalledWith(events[0]);
  });

  it('calls onSlotClick when day clicked', async () => {
    const onSlotClick = vi.fn();
    const user = userEvent.setup();

    const { container } = render(
      <CalendarMonthView
        currentDate={new Date(2024, 5, 15)}
        events={[]}
        onSlotClick={onSlotClick}
      />
    );

    const dayCell = container.querySelector('.min-h-\\[100px\\]');
    if (dayCell) {
      await user.click(dayCell);
      expect(onSlotClick).toHaveBeenCalled();
    }
  });

  it('highlights today', () => {
    const { container } = render(
      <CalendarMonthView
        currentDate={new Date()}
        events={[]}
      />
    );

    const todayElement = container.querySelector('.bg-teal-electric');
    expect(todayElement).toBeInTheDocument();
  });
});

// =============================================================================
// CalendarWeekView Tests
// =============================================================================

describe('CalendarWeekView', () => {
  it('renders time slots', () => {
    render(
      <CalendarWeekView
        currentDate={new Date(2024, 5, 15)}
        events={[]}
        workingHours={{ start: 8, end: 12 }}
      />
    );

    expect(screen.getByText('8 AM')).toBeInTheDocument();
    expect(screen.getByText('9 AM')).toBeInTheDocument();
    expect(screen.getByText('10 AM')).toBeInTheDocument();
    expect(screen.getByText('11 AM')).toBeInTheDocument();
  });

  it('renders 7 days for week view', () => {
    render(
      <CalendarWeekView
        currentDate={new Date(2024, 5, 15)} // Saturday
        events={[]}
      />
    );

    // Should show all weekdays
    const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    weekdays.forEach((day) => {
      expect(screen.getByText(day)).toBeInTheDocument();
    });
  });

  it('renders single day in day view mode', () => {
    const date = new Date(2024, 5, 15); // Saturday

    render(
      <CalendarWeekView
        currentDate={date}
        events={[]}
        singleDay={true}
      />
    );

    // Should only show one day column header (Saturday)
    expect(screen.getByText('Sat')).toBeInTheDocument();
    // Should not have other days in single-day mode
    const allSuns = screen.queryAllByText('Sun');
    expect(allSuns.length).toBe(0);
  });

  it('renders events in correct time slots', () => {
    const events = [
      {
        id: 1,
        title: 'Morning Meeting',
        start: new Date(2024, 5, 15, 9, 0),
      },
    ];

    render(
      <CalendarWeekView
        currentDate={new Date(2024, 5, 15)}
        events={events}
        workingHours={{ start: 8, end: 18 }}
      />
    );

    expect(screen.getByText('Morning Meeting')).toBeInTheDocument();
  });

  it('calls onEventClick when event clicked', async () => {
    const onEventClick = vi.fn();
    const user = userEvent.setup();
    const events = [
      { id: 1, title: 'Test Event', start: new Date(2024, 5, 15, 10, 0) },
    ];

    render(
      <CalendarWeekView
        currentDate={new Date(2024, 5, 15)}
        events={events}
        onEventClick={onEventClick}
        workingHours={{ start: 8, end: 18 }}
      />
    );

    await user.click(screen.getByText('Test Event'));
    expect(onEventClick).toHaveBeenCalledWith(events[0]);
  });

  it('calls onSlotClick when slot clicked', async () => {
    const onSlotClick = vi.fn();
    const user = userEvent.setup();

    const { container } = render(
      <CalendarWeekView
        currentDate={new Date(2024, 5, 15)}
        events={[]}
        onSlotClick={onSlotClick}
        workingHours={{ start: 8, end: 10 }}
      />
    );

    const slot = container.querySelector('.min-h-\\[60px\\]');
    if (slot) {
      await user.click(slot);
      expect(onSlotClick).toHaveBeenCalled();
    }
  });
});

// =============================================================================
// CalendarWeekView Resource Mode Tests
// =============================================================================

describe('CalendarWeekView - Resource Mode', () => {
  it('renders resources', () => {
    render(
      <CalendarWeekView
        currentDate={new Date(2024, 5, 15)}
        events={[]}
        resources={mockResources}
      />
    );

    expect(screen.getByText('John Doe')).toBeInTheDocument();
    expect(screen.getByText('Jane Smith')).toBeInTheDocument();
    expect(screen.getByText('Bob Johnson')).toBeInTheDocument();
  });

  it('renders resource subtitles', () => {
    render(
      <CalendarWeekView
        currentDate={new Date(2024, 5, 15)}
        events={[]}
        resources={mockResources}
      />
    );

    expect(screen.getByText('Developer')).toBeInTheDocument();
    expect(screen.getByText('Designer')).toBeInTheDocument();
  });

  it('shows resource status indicators', () => {
    const { container } = render(
      <CalendarWeekView
        currentDate={new Date(2024, 5, 15)}
        events={[]}
        resources={mockResources}
      />
    );

    expect(container.querySelector('.bg-emerald-500')).toBeInTheDocument(); // available
    expect(container.querySelector('.bg-amber-500')).toBeInTheDocument(); // busy
    expect(container.querySelector('.bg-slate-500')).toBeInTheDocument(); // offline
  });

  it('renders events for resources', () => {
    const events = [
      {
        id: 1,
        title: 'John\'s Task',
        start: new Date(2024, 5, 15, 10, 0),
        resourceId: 'user-1',
      },
    ];

    render(
      <CalendarWeekView
        currentDate={new Date(2024, 5, 15)}
        events={events}
        resources={mockResources}
      />
    );

    expect(screen.getByText("John's Task")).toBeInTheDocument();
  });

  it('shows resource initials when no avatar', () => {
    render(
      <CalendarWeekView
        currentDate={new Date(2024, 5, 15)}
        events={[]}
        resources={[{ id: 1, name: 'Alice' }]}
      />
    );

    expect(screen.getByText('A')).toBeInTheDocument();
  });
});

// =============================================================================
// Type Utilities Tests
// =============================================================================

describe('getEventColors', () => {
  it('returns colors for known color key', () => {
    const colors = getEventColors('blue');
    expect(colors.bg).toBe('bg-blue-500/20');
    expect(colors.border).toBe('border-blue-500');
    expect(colors.text).toBe('text-blue-300');
  });

  it('returns default colors for unknown key', () => {
    const colors = getEventColors('unknown');
    expect(colors).toEqual(EVENT_COLORS.default);
  });

  it('returns default colors for undefined', () => {
    const colors = getEventColors(undefined);
    expect(colors).toEqual(EVENT_COLORS.default);
  });
});

describe('isSameDay', () => {
  it('returns true for same day', () => {
    const date1 = new Date(2024, 5, 15, 10, 0);
    const date2 = new Date(2024, 5, 15, 14, 30);
    expect(isSameDay(date1, date2)).toBe(true);
  });

  it('returns false for different days', () => {
    const date1 = new Date(2024, 5, 15);
    const date2 = new Date(2024, 5, 16);
    expect(isSameDay(date1, date2)).toBe(false);
  });

  it('returns false for different months', () => {
    const date1 = new Date(2024, 5, 15);
    const date2 = new Date(2024, 6, 15);
    expect(isSameDay(date1, date2)).toBe(false);
  });

  it('returns false for different years', () => {
    const date1 = new Date(2024, 5, 15);
    const date2 = new Date(2025, 5, 15);
    expect(isSameDay(date1, date2)).toBe(false);
  });
});

describe('isToday', () => {
  it('returns true for today', () => {
    expect(isToday(new Date())).toBe(true);
  });

  it('returns false for yesterday', () => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    expect(isToday(yesterday)).toBe(false);
  });

  it('returns false for tomorrow', () => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    expect(isToday(tomorrow)).toBe(false);
  });
});

describe('getWeekDays', () => {
  it('returns 7 days', () => {
    const days = getWeekDays(new Date(2024, 5, 15));
    expect(days.length).toBe(7);
  });

  it('starts with Sunday', () => {
    const days = getWeekDays(new Date(2024, 5, 15)); // Saturday
    expect(days[0].getDay()).toBe(0); // Sunday
  });

  it('ends with Saturday', () => {
    const days = getWeekDays(new Date(2024, 5, 15));
    expect(days[6].getDay()).toBe(6); // Saturday
  });

  it('contains the input date', () => {
    const inputDate = new Date(2024, 5, 12); // Wednesday
    const days = getWeekDays(inputDate);
    const containsDate = days.some((d) => isSameDay(d, inputDate));
    expect(containsDate).toBe(true);
  });
});

describe('getMonthDays', () => {
  it('includes all days of the month', () => {
    const days = getMonthDays(new Date(2024, 5, 15)); // June 2024
    const juneDays = days.filter((d) => d.getMonth() === 5);
    expect(juneDays.length).toBe(30); // June has 30 days
  });

  it('includes days from previous month to fill first week', () => {
    const days = getMonthDays(new Date(2024, 5, 15)); // June 2024
    // June 1, 2024 is Saturday, so we need May 26-31 (6 days)
    const mayDays = days.filter((d) => d.getMonth() === 4);
    expect(mayDays.length).toBeGreaterThan(0);
  });

  it('includes days from next month to fill last week', () => {
    const days = getMonthDays(new Date(2024, 5, 15)); // June 2024
    // June 30, 2024 is Sunday, so we need July 1-6 (6 days)
    const julyDays = days.filter((d) => d.getMonth() === 6);
    expect(julyDays.length).toBeGreaterThan(0);
  });

  it('returns multiples of 7 (complete weeks)', () => {
    const days = getMonthDays(new Date(2024, 5, 15));
    expect(days.length % 7).toBe(0);
  });
});

describe('formatHour', () => {
  it('formats morning hours', () => {
    expect(formatHour(8)).toBe('8 AM');
    expect(formatHour(9)).toBe('9 AM');
    expect(formatHour(11)).toBe('11 AM');
  });

  it('formats noon', () => {
    expect(formatHour(12)).toBe('12 PM');
  });

  it('formats afternoon hours', () => {
    expect(formatHour(13)).toBe('1 PM');
    expect(formatHour(14)).toBe('2 PM');
    expect(formatHour(17)).toBe('5 PM');
  });

  it('formats midnight', () => {
    expect(formatHour(0)).toBe('12 AM');
  });
});

describe('parseDate', () => {
  it('returns Date object unchanged', () => {
    const date = new Date(2024, 5, 15);
    expect(parseDate(date)).toBe(date);
  });

  it('parses ISO string', () => {
    const result = parseDate('2024-06-15T10:00:00');
    expect(result instanceof Date).toBe(true);
    expect(result.getFullYear()).toBe(2024);
    expect(result.getMonth()).toBe(5); // June
    expect(result.getDate()).toBe(15);
  });
});

// =============================================================================
// EVENT_COLORS Tests
// =============================================================================

describe('EVENT_COLORS', () => {
  it('has consistent structure for all colors', () => {
    Object.entries(EVENT_COLORS).forEach(([colorName, colorConfig]) => {
      expect(colorConfig).toHaveProperty('bg');
      expect(colorConfig).toHaveProperty('border');
      expect(colorConfig).toHaveProperty('text');
    });
  });

  it('has all expected color options', () => {
    const expectedColors = [
      'default', 'blue', 'cyan', 'teal', 'emerald', 'green',
      'amber', 'orange', 'red', 'rose', 'purple', 'indigo',
    ];

    expectedColors.forEach((color) => {
      expect(EVENT_COLORS[color]).toBeDefined();
    });
  });
});
