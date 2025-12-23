/**
 * Gantt Chart Constants
 *
 * Colors, dimensions, and configuration for the Gantt chart.
 * Uses design tokens from @/lib/design-tokens for consistency.
 */

import { CHART_COLORS } from '@/lib/design-tokens';
import type { GanttConfig, ZoomLevel, TaskStatus, TaskPriority } from './types';

// =============================================================================
// ZOOM CONFIGURATION
// =============================================================================

/**
 * Pixels per day for each zoom level.
 */
export const ZOOM_PIXELS: Record<ZoomLevel, number> = {
  day: 40, // Detailed view - 40px per day
  week: 15, // Medium view - ~105px per week
  month: 4, // Overview - ~120px per month
};

/**
 * Date format for header labels at each zoom level.
 */
export const ZOOM_DATE_FORMAT: Record<ZoomLevel, { primary: string; secondary: string }> = {
  day: { primary: 'MMM yyyy', secondary: 'd' },
  week: { primary: 'MMM yyyy', secondary: "'W'w" },
  month: { primary: 'yyyy', secondary: 'MMM' },
};

// =============================================================================
// DIMENSIONS
// =============================================================================

/**
 * Default Gantt chart configuration.
 */
export const DEFAULT_GANTT_CONFIG: GanttConfig = {
  rowHeight: 36,
  headerHeight: 48,
  leftPanelWidth: 200,
  barHeight: 20,
  barRadius: 4,
  minBarWidth: 8,
  indentPerLevel: 16,
  arrowStrokeWidth: 1.5,
  todayMarkerWidth: 2,
};

/**
 * Padding around the date range (in days).
 */
export const DATE_RANGE_PADDING = 7;

// =============================================================================
// COLORS
// =============================================================================

/**
 * Task status colors using design tokens.
 */
export const STATUS_COLORS: Record<TaskStatus, string> = {
  open: CHART_COLORS.info, // Blue
  working: CHART_COLORS.warning, // Amber
  pending_review: CHART_COLORS.palette[2], // Purple
  completed: CHART_COLORS.success, // Teal/Green
  cancelled: CHART_COLORS.axis, // Gray
  overdue: CHART_COLORS.danger, // Red/Coral
};

/**
 * Task priority indicator colors.
 */
export const PRIORITY_COLORS: Record<TaskPriority, string> = {
  low: CHART_COLORS.axis,
  medium: CHART_COLORS.warning,
  high: CHART_COLORS.danger,
  urgent: 'var(--color-coral-alert)',
};

/**
 * UI element colors.
 */
export const GANTT_COLORS = {
  // Grid and markers
  grid: CHART_COLORS.grid,
  gridAlt: 'var(--color-slate-elevated)',
  todayMarker: CHART_COLORS.danger,
  weekendBg: 'var(--color-slate-elevated)',

  // Dependencies
  dependencyLine: CHART_COLORS.axis,
  dependencyArrow: CHART_COLORS.axis,

  // Progress bar overlay
  progressOverlay: 'rgba(255, 255, 255, 0.3)',

  // Text
  taskName: 'var(--color-text-primary)',
  taskNameMuted: 'var(--color-slate-muted)',
  headerText: 'var(--color-slate-muted)',

  // Hover states
  rowHover: 'var(--color-slate-elevated)',
  barHover: 'rgba(255, 255, 255, 0.1)',

  // Tooltip (from design tokens)
  tooltip: CHART_COLORS.tooltip,
};

// =============================================================================
// STATUS LABELS
// =============================================================================

/**
 * Display labels for task statuses.
 */
export const STATUS_LABELS: Record<TaskStatus, string> = {
  open: 'Open',
  working: 'In Progress',
  pending_review: 'Pending Review',
  completed: 'Completed',
  cancelled: 'Cancelled',
  overdue: 'Overdue',
};

/**
 * Display labels for task priorities.
 */
export const PRIORITY_LABELS: Record<TaskPriority, string> = {
  low: 'Low',
  medium: 'Medium',
  high: 'High',
  urgent: 'Urgent',
};
