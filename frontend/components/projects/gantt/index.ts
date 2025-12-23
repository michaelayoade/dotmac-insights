/**
 * Gantt Chart Component Exports
 *
 * Re-exports all Gantt chart related components and utilities.
 */

// Main component
export { GanttChart } from './GanttChart';
export { default } from './GanttChart';

// Sub-components
export { GanttTimeline } from './GanttTimeline';
export { GanttTaskRow } from './GanttTaskRow';
export { GanttDependencyArrows } from './GanttDependencyArrows';
export { GanttTooltip } from './GanttTooltip';
export { GanttControls } from './GanttControls';

// Types
export type {
  ZoomLevel,
  TaskStatus,
  TaskPriority,
  GanttTask,
  GanttDependency,
  GanttApiResponse,
  TaskPosition,
  GanttLayout,
  GanttConfig,
  GanttChartProps,
  GanttTimelineProps,
  GanttTaskRowProps,
  GanttDependencyArrowsProps,
  GanttTooltipProps,
  GanttControlsProps,
} from './types';

// Constants
export {
  ZOOM_PIXELS,
  ZOOM_DATE_FORMAT,
  DEFAULT_GANTT_CONFIG,
  DATE_RANGE_PADDING,
  STATUS_COLORS,
  PRIORITY_COLORS,
  GANTT_COLORS,
  STATUS_LABELS,
  PRIORITY_LABELS,
} from './constants';

// Utilities
export {
  dateToX,
  xToDate,
  dateRangeToWidth,
  getTimeUnits,
  getPrimaryHeaders,
  calculateLayout,
  calculateDateRange,
  getTodayX,
  transformApiTasks,
  extractDependencies,
  sortTasksForGantt,
  calculateDependencyPath,
  isTaskOverdue,
  formatTaskDate,
  getTaskDuration,
} from './utils';
