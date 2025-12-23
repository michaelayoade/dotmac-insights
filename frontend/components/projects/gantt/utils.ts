/**
 * Gantt Chart Utility Functions
 *
 * Date/pixel conversions, layout calculations, and data transformations.
 */

import {
  differenceInDays,
  addDays,
  startOfDay,
  startOfWeek,
  startOfMonth,
  endOfWeek,
  endOfMonth,
  format,
  eachDayOfInterval,
  eachWeekOfInterval,
  eachMonthOfInterval,
  isWeekend,
  isSameDay,
} from 'date-fns';

import type {
  GanttTask,
  GanttDependency,
  GanttLayout,
  GanttConfig,
  GanttApiResponse,
  TaskPosition,
  ZoomLevel,
  TaskStatus,
  TaskPriority,
} from './types';

import {
  ZOOM_PIXELS,
  DATE_RANGE_PADDING,
  DEFAULT_GANTT_CONFIG,
} from './constants';

// =============================================================================
// DATE UTILITIES
// =============================================================================

/**
 * Convert a date to its x-coordinate on the chart.
 */
export function dateToX(
  date: Date,
  startDate: Date,
  pixelsPerDay: number,
  leftPanelWidth: number
): number {
  const days = differenceInDays(startOfDay(date), startOfDay(startDate));
  return leftPanelWidth + days * pixelsPerDay;
}

/**
 * Convert an x-coordinate to a date.
 */
export function xToDate(
  x: number,
  startDate: Date,
  pixelsPerDay: number,
  leftPanelWidth: number
): Date {
  const days = Math.floor((x - leftPanelWidth) / pixelsPerDay);
  return addDays(startDate, days);
}

/**
 * Calculate the width in pixels for a date range.
 */
export function dateRangeToWidth(
  start: Date,
  end: Date,
  pixelsPerDay: number,
  minWidth: number
): number {
  const days = differenceInDays(startOfDay(end), startOfDay(start)) + 1;
  return Math.max(days * pixelsPerDay, minWidth);
}

/**
 * Get time units (days/weeks/months) for the timeline header.
 */
export function getTimeUnits(
  startDate: Date,
  endDate: Date,
  zoomLevel: ZoomLevel
): Array<{ date: Date; label: string; isWeekend?: boolean }> {
  switch (zoomLevel) {
    case 'day':
      return eachDayOfInterval({ start: startDate, end: endDate }).map((date) => ({
        date,
        label: format(date, 'd'),
        isWeekend: isWeekend(date),
      }));

    case 'week':
      return eachWeekOfInterval(
        { start: startDate, end: endDate },
        { weekStartsOn: 1 }
      ).map((date) => ({
        date,
        label: format(date, "'W'w"),
      }));

    case 'month':
      return eachMonthOfInterval({ start: startDate, end: endDate }).map((date) => ({
        date,
        label: format(date, 'MMM'),
      }));
  }
}

/**
 * Get primary header labels (months for day view, years for month view).
 */
export function getPrimaryHeaders(
  startDate: Date,
  endDate: Date,
  zoomLevel: ZoomLevel
): Array<{ date: Date; label: string; span: number }> {
  const units = getTimeUnits(startDate, endDate, zoomLevel);
  const headers: Array<{ date: Date; label: string; span: number }> = [];

  let currentLabel = '';
  let currentSpan = 0;
  let currentDate: Date | null = null;

  const getLabel = (date: Date): string => {
    switch (zoomLevel) {
      case 'day':
        return format(date, 'MMM yyyy');
      case 'week':
        return format(date, 'MMM yyyy');
      case 'month':
        return format(date, 'yyyy');
    }
  };

  units.forEach((unit) => {
    const label = getLabel(unit.date);
    if (label !== currentLabel) {
      if (currentLabel && currentSpan > 0) {
        headers.push({ date: currentDate!, label: currentLabel, span: currentSpan });
      }
      currentLabel = label;
      currentDate = unit.date;
      currentSpan = 1;
    } else {
      currentSpan++;
    }
  });

  // Add last header
  if (currentLabel && currentSpan > 0 && currentDate) {
    headers.push({ date: currentDate, label: currentLabel, span: currentSpan });
  }

  return headers;
}

// =============================================================================
// LAYOUT CALCULATION
// =============================================================================

/**
 * Calculate the full layout for the Gantt chart.
 */
export function calculateLayout(
  tasks: GanttTask[],
  zoomLevel: ZoomLevel,
  config: GanttConfig = DEFAULT_GANTT_CONFIG
): GanttLayout {
  // Find date range from tasks
  const { startDate, endDate } = calculateDateRange(tasks);
  const pixelsPerDay = ZOOM_PIXELS[zoomLevel];
  const totalDays = differenceInDays(endDate, startDate) + 1;

  // Calculate dimensions
  const chartWidth = config.leftPanelWidth + totalDays * pixelsPerDay;
  const chartHeight = tasks.length * config.rowHeight + config.headerHeight;

  // Pre-calculate task positions
  const taskPositions = new Map<number, TaskPosition>();

  tasks.forEach((task, index) => {
    if (task.startDate && task.endDate) {
      const x = dateToX(task.startDate, startDate, pixelsPerDay, config.leftPanelWidth);
      const width = dateRangeToWidth(task.startDate, task.endDate, pixelsPerDay, config.minBarWidth);
      const y = index * config.rowHeight + config.headerHeight;

      taskPositions.set(task.id, { x, y, width });
    }
  });

  return {
    chartWidth,
    chartHeight,
    rowHeight: config.rowHeight,
    headerHeight: config.headerHeight,
    leftPanelWidth: config.leftPanelWidth,
    pixelsPerDay,
    startDate,
    endDate,
    totalDays,
    taskPositions,
  };
}

/**
 * Calculate the date range encompassing all tasks with padding.
 */
export function calculateDateRange(tasks: GanttTask[]): { startDate: Date; endDate: Date } {
  const now = new Date();
  let minDate: Date | null = null;
  let maxDate: Date | null = null;

  tasks.forEach((task) => {
    if (task.startDate) {
      if (!minDate || task.startDate < minDate) {
        minDate = task.startDate;
      }
    }
    if (task.endDate) {
      if (!maxDate || task.endDate > maxDate) {
        maxDate = task.endDate;
      }
    }
  });

  // Default to current month if no dates
  if (!minDate) minDate = startOfMonth(now);
  if (!maxDate) maxDate = endOfMonth(now);

  // Add padding
  const startDate = addDays(startOfDay(minDate), -DATE_RANGE_PADDING);
  const endDate = addDays(startOfDay(maxDate), DATE_RANGE_PADDING);

  return { startDate, endDate };
}

/**
 * Get the x-coordinate for today's marker.
 */
export function getTodayX(layout: GanttLayout): number | null {
  const today = startOfDay(new Date());

  if (today < layout.startDate || today > layout.endDate) {
    return null;
  }

  return dateToX(today, layout.startDate, layout.pixelsPerDay, layout.leftPanelWidth);
}

// =============================================================================
// DATA TRANSFORMATION
// =============================================================================

/**
 * Transform API response to GanttTask array.
 */
export function transformApiTasks(response: GanttApiResponse): GanttTask[] {
  const tasks = response.tasks.map((apiTask) => ({
    id: apiTask.id,
    subject: apiTask.subject,
    status: normalizeStatus(apiTask.status),
    priority: normalizePriority(apiTask.priority),
    progress: apiTask.progress ?? 0,
    startDate: apiTask.exp_start_date ? new Date(apiTask.exp_start_date) : null,
    endDate: apiTask.exp_end_date ? new Date(apiTask.exp_end_date) : null,
    assignedTo: apiTask.assigned_to,
    parentTaskId: apiTask.parent_task_id,
    depth: 0, // Will be calculated
    isGroup: apiTask.is_group,
    dependsOn: apiTask.depends_on || [],
  }));

  // Calculate depth for hierarchy
  return calculateTaskDepths(tasks);
}

/**
 * Calculate hierarchy depth for each task.
 */
function calculateTaskDepths(tasks: GanttTask[]): GanttTask[] {
  const taskMap = new Map(tasks.map((t) => [t.id, t]));

  const getDepth = (task: GanttTask, visited = new Set<number>()): number => {
    if (visited.has(task.id)) return 0; // Prevent circular references
    visited.add(task.id);

    if (!task.parentTaskId) return 0;

    const parent = taskMap.get(task.parentTaskId);
    if (!parent) return 0;

    return 1 + getDepth(parent, visited);
  };

  return tasks.map((task) => ({
    ...task,
    depth: getDepth(task),
  }));
}

/**
 * Extract dependencies from tasks.
 */
export function extractDependencies(tasks: GanttTask[]): GanttDependency[] {
  const dependencies: GanttDependency[] = [];

  tasks.forEach((task) => {
    task.dependsOn.forEach((dependsOnId) => {
      dependencies.push({
        fromTaskId: dependsOnId, // The task being depended upon
        toTaskId: task.id, // The task with the dependency
      });
    });
  });

  return dependencies;
}

/**
 * Sort tasks by hierarchy (parents before children) and then by date.
 */
export function sortTasksForGantt(tasks: GanttTask[]): GanttTask[] {
  const taskMap = new Map(tasks.map((t) => [t.id, t]));
  const result: GanttTask[] = [];
  const processed = new Set<number>();

  // Recursive function to add task and its children
  const addTaskWithChildren = (task: GanttTask) => {
    if (processed.has(task.id)) return;
    processed.add(task.id);
    result.push(task);

    // Find and add children
    const children = tasks
      .filter((t) => t.parentTaskId === task.id)
      .sort((a, b) => {
        // Sort by start date, then by name
        if (a.startDate && b.startDate) {
          return a.startDate.getTime() - b.startDate.getTime();
        }
        return a.subject.localeCompare(b.subject);
      });

    children.forEach(addTaskWithChildren);
  };

  // Start with root tasks (no parent)
  const rootTasks = tasks
    .filter((t) => !t.parentTaskId)
    .sort((a, b) => {
      if (a.startDate && b.startDate) {
        return a.startDate.getTime() - b.startDate.getTime();
      }
      return a.subject.localeCompare(b.subject);
    });

  rootTasks.forEach(addTaskWithChildren);

  // Add any orphaned tasks (parent not in list)
  tasks.forEach((task) => {
    if (!processed.has(task.id)) {
      result.push(task);
    }
  });

  return result;
}

// =============================================================================
// DEPENDENCY PATH CALCULATION
// =============================================================================

/**
 * Calculate SVG path for a dependency arrow (bezier curve).
 */
export function calculateDependencyPath(
  fromPos: TaskPosition,
  toPos: TaskPosition,
  config: GanttConfig
): string {
  // Start from right edge of 'from' task bar
  const startX = fromPos.x + fromPos.width;
  const startY = fromPos.y + config.barHeight / 2;

  // End at left edge of 'to' task bar
  const endX = toPos.x;
  const endY = toPos.y + config.barHeight / 2;

  // Handle different cases
  if (endX > startX + 20) {
    // Normal case: 'to' task starts after 'from' task ends
    // Simple bezier curve
    const midX = (startX + endX) / 2;
    return `M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`;
  } else {
    // Overlap case: 'to' task starts before/during 'from' task
    // Route around with more control points
    const offset = 20;
    return `M ${startX} ${startY}
            L ${startX + offset} ${startY}
            Q ${startX + offset + 10} ${startY}, ${startX + offset + 10} ${(startY + endY) / 2}
            Q ${startX + offset + 10} ${endY}, ${endX - offset} ${endY}
            L ${endX} ${endY}`;
  }
}

// =============================================================================
// HELPERS
// =============================================================================

/**
 * Normalize status string to TaskStatus type.
 */
function normalizeStatus(status: string): TaskStatus {
  const normalized = status.toLowerCase().replace(/[_-]/g, '_');
  const validStatuses: TaskStatus[] = [
    'open',
    'working',
    'pending_review',
    'completed',
    'cancelled',
    'overdue',
  ];

  if (validStatuses.includes(normalized as TaskStatus)) {
    return normalized as TaskStatus;
  }

  // Map common variations
  const statusMap: Record<string, TaskStatus> = {
    in_progress: 'working',
    inprogress: 'working',
    pending: 'open',
    done: 'completed',
    closed: 'completed',
    template: 'open',
  };

  return statusMap[normalized] || 'open';
}

/**
 * Normalize priority string to TaskPriority type.
 */
function normalizePriority(priority: string): TaskPriority {
  const normalized = priority.toLowerCase();
  const validPriorities: TaskPriority[] = ['low', 'medium', 'high', 'urgent'];

  if (validPriorities.includes(normalized as TaskPriority)) {
    return normalized as TaskPriority;
  }

  return 'medium';
}

/**
 * Check if a task is currently overdue.
 */
export function isTaskOverdue(task: GanttTask): boolean {
  if (task.status === 'completed' || task.status === 'cancelled') {
    return false;
  }

  if (!task.endDate) {
    return false;
  }

  return task.endDate < new Date();
}

/**
 * Format a date for display in tooltips.
 */
export function formatTaskDate(date: Date | null): string {
  if (!date) return '-';
  return format(date, 'MMM d, yyyy');
}

/**
 * Calculate task duration in days.
 */
export function getTaskDuration(task: GanttTask): number | null {
  if (!task.startDate || !task.endDate) return null;
  return differenceInDays(task.endDate, task.startDate) + 1;
}
