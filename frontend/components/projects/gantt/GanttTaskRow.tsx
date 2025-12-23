'use client';

/**
 * GanttTaskRow Component
 *
 * Renders a single task bar in the Gantt chart.
 * Includes the task name in the left panel and the bar in the timeline area.
 */

import React, { memo } from 'react';
import { cn } from '@/lib/utils';
import type { GanttTaskRowProps } from './types';
import { STATUS_COLORS, GANTT_COLORS, STATUS_LABELS } from './constants';
import { isTaskOverdue } from './utils';

/**
 * Single task row component with task name and bar.
 */
function GanttTaskRowComponent({
  task,
  layout,
  config,
  rowIndex,
  showProgress,
  isHovered,
  onHover,
  onClick,
}: GanttTaskRowProps) {
  const position = layout.taskPositions.get(task.id);
  const y = rowIndex * config.rowHeight + config.headerHeight;
  const barY = y + (config.rowHeight - config.barHeight) / 2;

  // Determine actual status (check for overdue)
  const displayStatus = isTaskOverdue(task) ? 'overdue' : task.status;
  const barColor = STATUS_COLORS[displayStatus];

  // Handle tasks without dates
  const hasBar = position !== undefined;

  return (
    <g
      className={cn('gantt-task-row', isHovered && 'is-hovered')}
      onMouseEnter={() => onHover(task)}
      onMouseLeave={() => onHover(null)}
      onClick={() => onClick?.(task)}
      style={{ cursor: onClick ? 'pointer' : 'default' }}
    >
      {/* Row background (for hover effect) */}
      <rect
        x={0}
        y={y}
        width={layout.chartWidth}
        height={config.rowHeight}
        fill={isHovered ? GANTT_COLORS.rowHover : 'transparent'}
        className="transition-colors duration-150"
      />

      {/* Left panel divider */}
      <line
        x1={config.leftPanelWidth}
        y1={y}
        x2={config.leftPanelWidth}
        y2={y + config.rowHeight}
        stroke={GANTT_COLORS.grid}
        strokeWidth={1}
      />

      {/* Task name in left panel */}
      <g className="gantt-task-name">
        {/* Hierarchy indent indicator */}
        {task.depth > 0 && (
          <line
            x1={8 + (task.depth - 1) * config.indentPerLevel + 6}
            y1={y + config.rowHeight / 2}
            x2={8 + task.depth * config.indentPerLevel - 4}
            y2={y + config.rowHeight / 2}
            stroke={GANTT_COLORS.grid}
            strokeWidth={1}
          />
        )}

        {/* Group indicator (folder icon placeholder) */}
        {task.isGroup && (
          <rect
            x={8 + task.depth * config.indentPerLevel}
            y={y + config.rowHeight / 2 - 4}
            width={8}
            height={8}
            rx={1}
            fill={GANTT_COLORS.taskNameMuted}
            opacity={0.5}
          />
        )}

        {/* Task name text */}
        <text
          x={8 + task.depth * config.indentPerLevel + (task.isGroup ? 12 : 0)}
          y={y + config.rowHeight / 2}
          fill={GANTT_COLORS.taskName}
          fontSize={12}
          dominantBaseline="middle"
          className="select-none"
        >
          {truncateText(task.subject, config.leftPanelWidth - 20 - task.depth * config.indentPerLevel)}
        </text>
      </g>

      {/* Task bar (only if task has dates) */}
      {hasBar && (
        <g className="gantt-task-bar">
          {/* Main bar */}
          <rect
            x={position.x}
            y={barY}
            width={position.width}
            height={config.barHeight}
            rx={config.barRadius}
            fill={barColor}
            className={cn(
              'transition-opacity duration-150',
              isHovered && 'opacity-90'
            )}
          />

          {/* Progress overlay */}
          {showProgress && task.progress > 0 && (
            <rect
              x={position.x}
              y={barY}
              width={position.width * (task.progress / 100)}
              height={config.barHeight}
              rx={config.barRadius}
              fill={GANTT_COLORS.progressOverlay}
              className="pointer-events-none"
            />
          )}

          {/* Progress text inside bar (if wide enough) */}
          {showProgress && task.progress > 0 && position.width > 40 && (
            <text
              x={position.x + position.width / 2}
              y={barY + config.barHeight / 2}
              fill="white"
              fontSize={10}
              fontWeight={500}
              textAnchor="middle"
              dominantBaseline="middle"
              className="pointer-events-none select-none"
            >
              {Math.round(task.progress)}%
            </text>
          )}

          {/* Dependency indicator (small circle on left edge) */}
          {task.dependsOn.length > 0 && (
            <circle
              cx={position.x}
              cy={barY + config.barHeight / 2}
              r={3}
              fill={GANTT_COLORS.dependencyLine}
              className="pointer-events-none"
            />
          )}
        </g>
      )}

      {/* No dates indicator */}
      {!hasBar && (
        <text
          x={config.leftPanelWidth + 10}
          y={y + config.rowHeight / 2}
          fill={GANTT_COLORS.taskNameMuted}
          fontSize={11}
          dominantBaseline="middle"
          fontStyle="italic"
          className="select-none"
        >
          No dates set
        </text>
      )}

      {/* Row bottom border */}
      <line
        x1={0}
        y1={y + config.rowHeight}
        x2={layout.chartWidth}
        y2={y + config.rowHeight}
        stroke={GANTT_COLORS.grid}
        strokeWidth={0.5}
        opacity={0.5}
      />
    </g>
  );
}

/**
 * Truncate text to fit within a given width (approximate).
 */
function truncateText(text: string, maxWidth: number): string {
  // Approximate character width at 12px font
  const charWidth = 7;
  const maxChars = Math.floor(maxWidth / charWidth);

  if (text.length <= maxChars) {
    return text;
  }

  return text.substring(0, maxChars - 1) + '...';
}

// Memoize to prevent unnecessary re-renders
export const GanttTaskRow = memo(GanttTaskRowComponent);

export default GanttTaskRow;
