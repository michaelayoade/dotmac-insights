/**
 * Gantt Chart Type Definitions
 *
 * Core types for the custom SVG-based Gantt chart component.
 */

// =============================================================================
// ENUMS & LITERALS
// =============================================================================

export type ZoomLevel = 'day' | 'week' | 'month';

export type TaskStatus =
  | 'open'
  | 'working'
  | 'pending_review'
  | 'completed'
  | 'cancelled'
  | 'overdue';

export type TaskPriority = 'low' | 'medium' | 'high' | 'urgent';

// =============================================================================
// DATA TYPES
// =============================================================================

/**
 * Processed task ready for Gantt rendering.
 * Transformed from API response with computed fields.
 */
export interface GanttTask {
  id: number;
  subject: string;
  status: TaskStatus;
  priority: TaskPriority;
  progress: number; // 0-100

  // Dates
  startDate: Date | null;
  endDate: Date | null;

  // Assignment
  assignedTo: string | null;

  // Hierarchy
  parentTaskId: number | null;
  depth: number; // 0 = root, 1 = child, etc.
  isGroup: boolean;

  // Dependencies (task IDs this task depends on)
  dependsOn: number[];
}

/**
 * Dependency link between two tasks.
 * Arrow goes FROM the dependency TO the dependent task.
 */
export interface GanttDependency {
  fromTaskId: number; // The task being depended upon
  toTaskId: number; // The task with the dependency
}

/**
 * API response from /projects/{id}/gantt endpoint.
 */
export interface GanttApiResponse {
  tasks: Array<{
    id: number;
    subject: string;
    status: string;
    priority: string;
    progress: number | null;
    exp_start_date: string | null;
    exp_end_date: string | null;
    assigned_to: string | null;
    parent_task_id: number | null;
    is_group: boolean;
    depends_on: number[];
  }>;
  date_range: {
    min_date: string | null;
    max_date: string | null;
  };
}

// =============================================================================
// LAYOUT TYPES
// =============================================================================

/**
 * Position of a task bar in the chart.
 */
export interface TaskPosition {
  x: number;
  y: number;
  width: number;
}

/**
 * Computed layout dimensions and positions.
 */
export interface GanttLayout {
  chartWidth: number;
  chartHeight: number;
  rowHeight: number;
  headerHeight: number;
  leftPanelWidth: number;
  pixelsPerDay: number;
  startDate: Date;
  endDate: Date;
  totalDays: number;
  taskPositions: Map<number, TaskPosition>;
}

/**
 * Gantt chart configuration constants.
 */
export interface GanttConfig {
  rowHeight: number;
  headerHeight: number;
  leftPanelWidth: number;
  barHeight: number;
  barRadius: number;
  minBarWidth: number;
  indentPerLevel: number;
  arrowStrokeWidth: number;
  todayMarkerWidth: number;
}

// =============================================================================
// COMPONENT PROPS
// =============================================================================

/**
 * Main GanttChart component props.
 */
export interface GanttChartProps {
  projectId: number;

  // View options
  zoomLevel?: ZoomLevel;
  onZoomChange?: (level: ZoomLevel) => void;
  showDependencies?: boolean;
  showTodayMarker?: boolean;
  showProgress?: boolean;

  // Dimensions
  height?: number;
  className?: string;

  // Callbacks
  onTaskClick?: (task: GanttTask) => void;
}

/**
 * GanttTimeline header props.
 */
export interface GanttTimelineProps {
  layout: GanttLayout;
  zoomLevel: ZoomLevel;
}

/**
 * GanttTaskRow props.
 */
export interface GanttTaskRowProps {
  task: GanttTask;
  layout: GanttLayout;
  config: GanttConfig;
  rowIndex: number;
  showProgress: boolean;
  isHovered: boolean;
  onHover: (task: GanttTask | null) => void;
  onClick?: (task: GanttTask) => void;
}

/**
 * GanttDependencyArrows props.
 */
export interface GanttDependencyArrowsProps {
  dependencies: GanttDependency[];
  layout: GanttLayout;
  config: GanttConfig;
}

/**
 * GanttTooltip props.
 */
export interface GanttTooltipProps {
  task: GanttTask | null;
  position: { x: number; y: number };
  visible: boolean;
}

/**
 * GanttControls props.
 */
export interface GanttControlsProps {
  zoomLevel: ZoomLevel;
  onZoomChange: (level: ZoomLevel) => void;
  onScrollToToday: () => void;
}
