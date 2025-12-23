'use client';

/**
 * GanttTooltip Component
 *
 * Displays task details on hover.
 * Rendered as a portal to avoid SVG clipping issues.
 */

import React, { memo } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';
import type { GanttTooltipProps } from './types';
import {
  STATUS_COLORS,
  STATUS_LABELS,
  PRIORITY_LABELS,
  GANTT_COLORS,
} from './constants';
import { formatTaskDate, getTaskDuration, isTaskOverdue } from './utils';

/**
 * Tooltip component for showing task details.
 */
function GanttTooltipComponent({ task, position, visible }: GanttTooltipProps) {
  if (!visible || !task) return null;

  // Don't render on server
  if (typeof window === 'undefined') return null;

  const displayStatus = isTaskOverdue(task) ? 'overdue' : task.status;
  const statusColor = STATUS_COLORS[displayStatus];
  const statusLabel = STATUS_LABELS[displayStatus];
  const duration = getTaskDuration(task);

  const tooltip = (
    <div
      className={cn(
        'fixed z-[9999] pointer-events-none',
        'bg-slate-card border border-slate-border rounded-lg shadow-xl',
        'px-3 py-2 min-w-[200px] max-w-[280px]',
        'text-sm',
        'animate-in fade-in-0 zoom-in-95 duration-150'
      )}
      style={{
        left: position.x + 10,
        top: position.y + 10,
        // Prevent tooltip from going off-screen
        transform: `translate(
          ${position.x > window.innerWidth - 300 ? '-100%' : '0'},
          ${position.y > window.innerHeight - 200 ? '-100%' : '0'}
        )`,
      }}
    >
      {/* Task name */}
      <div className="font-semibold text-foreground mb-2 line-clamp-2">
        {task.subject}
      </div>

      {/* Status badge */}
      <div className="flex items-center gap-2 mb-2">
        <span
          className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium"
          style={{
            backgroundColor: `color-mix(in srgb, ${statusColor} 20%, transparent)`,
            color: statusColor,
          }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{ backgroundColor: statusColor }}
          />
          {statusLabel}
        </span>
        <span className="text-xs text-slate-muted">
          {PRIORITY_LABELS[task.priority]} priority
        </span>
      </div>

      {/* Details */}
      <div className="space-y-1 text-xs">
        <div className="flex justify-between">
          <span className="text-slate-muted">Start:</span>
          <span className="text-foreground">{formatTaskDate(task.startDate)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-muted">End:</span>
          <span className="text-foreground">{formatTaskDate(task.endDate)}</span>
        </div>
        {duration !== null && (
          <div className="flex justify-between">
            <span className="text-slate-muted">Duration:</span>
            <span className="text-foreground">
              {duration} day{duration !== 1 ? 's' : ''}
            </span>
          </div>
        )}
        {task.progress > 0 && (
          <div className="flex justify-between">
            <span className="text-slate-muted">Progress:</span>
            <span className="text-foreground">{Math.round(task.progress)}%</span>
          </div>
        )}
        {task.assignedTo && (
          <div className="flex justify-between">
            <span className="text-slate-muted">Assigned:</span>
            <span className="text-foreground truncate max-w-[120px]">
              {task.assignedTo.split('@')[0]}
            </span>
          </div>
        )}
        {task.dependsOn.length > 0 && (
          <div className="flex justify-between">
            <span className="text-slate-muted">Dependencies:</span>
            <span className="text-foreground">{task.dependsOn.length}</span>
          </div>
        )}
      </div>

      {/* Progress bar */}
      {task.progress > 0 && (
        <div className="mt-2 pt-2 border-t border-slate-border">
          <div className="h-1.5 bg-slate-elevated rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${task.progress}%`,
                backgroundColor: statusColor,
              }}
            />
          </div>
        </div>
      )}
    </div>
  );

  // Render as portal to document body
  return createPortal(tooltip, document.body);
}

// Memoize to prevent unnecessary re-renders
export const GanttTooltip = memo(GanttTooltipComponent);

export default GanttTooltip;
