'use client';

/**
 * GanttChart Component
 *
 * Main Gantt chart component that assembles all sub-components.
 * Provides a visual timeline view of project tasks with dependencies.
 */

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useGanttData, useGanttDataFallback } from '@/hooks/useGanttData';
import type { GanttChartProps, GanttTask, ZoomLevel } from './types';
import { DEFAULT_GANTT_CONFIG, GANTT_COLORS } from './constants';
import { getTodayX, calculateLayout } from './utils';

import { GanttTimeline } from './GanttTimeline';
import { GanttTaskRow } from './GanttTaskRow';
import { GanttDependencyArrows } from './GanttDependencyArrows';
import { GanttTooltip } from './GanttTooltip';
import { GanttControls } from './GanttControls';

/**
 * Main Gantt chart component.
 */
export function GanttChart({
  projectId,
  zoomLevel: initialZoomLevel = 'week',
  onZoomChange,
  showDependencies = true,
  showTodayMarker = true,
  showProgress = true,
  height = 400,
  className,
  onTaskClick,
}: GanttChartProps) {
  // Internal zoom state (controlled or uncontrolled)
  const [internalZoomLevel, setInternalZoomLevel] = useState<ZoomLevel>(initialZoomLevel);
  const zoomLevel = onZoomChange ? initialZoomLevel : internalZoomLevel;

  const handleZoomChange = useCallback(
    (level: ZoomLevel) => {
      if (onZoomChange) {
        onZoomChange(level);
      } else {
        setInternalZoomLevel(level);
      }
    },
    [onZoomChange]
  );

  // Fetch data - try dedicated endpoint first, fallback to task list
  const {
    tasks,
    dependencies,
    layout,
    isLoading,
    error,
  } = useGanttDataFallback(projectId, zoomLevel);

  // Hover state
  const [hoveredTask, setHoveredTask] = useState<GanttTask | null>(null);
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });

  // Scroll container ref
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  // Handle task hover
  const handleTaskHover = useCallback(
    (task: GanttTask | null) => {
      setHoveredTask(task);
    },
    []
  );

  // Track mouse position for tooltip
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (hoveredTask) {
        setTooltipPosition({ x: e.clientX, y: e.clientY });
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, [hoveredTask]);

  // Scroll to today
  const handleScrollToToday = useCallback(() => {
    if (!layout || !scrollContainerRef.current) return;

    const todayX = getTodayX(layout);
    if (todayX !== null) {
      const containerWidth = scrollContainerRef.current.clientWidth;
      // Center today in the viewport
      scrollContainerRef.current.scrollLeft = todayX - containerWidth / 2;
    }
  }, [layout]);

  // Auto-scroll to today on initial load
  useEffect(() => {
    if (layout && scrollContainerRef.current) {
      // Small delay to ensure DOM is ready
      const timer = setTimeout(handleScrollToToday, 100);
      return () => clearTimeout(timer);
    }
  }, [layout?.totalDays]); // Only on initial layout calculation

  // Loading state
  if (isLoading) {
    return (
      <div
        className={cn(
          'flex items-center justify-center bg-slate-card border border-slate-border rounded-xl',
          className
        )}
        style={{ height }}
      >
        <div className="flex items-center gap-3 text-slate-muted">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span>Loading timeline...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div
        className={cn(
          'flex items-center justify-center bg-red-500/10 border border-red-500/30 rounded-xl',
          className
        )}
        style={{ height }}
      >
        <div className="flex items-center gap-3 text-red-400">
          <AlertTriangle className="w-5 h-5" />
          <span>Failed to load timeline</span>
        </div>
      </div>
    );
  }

  // Empty state
  if (tasks.length === 0) {
    return (
      <div
        className={cn(
          'flex flex-col items-center justify-center bg-slate-card border border-slate-border rounded-xl',
          className
        )}
        style={{ height }}
      >
        <div className="text-slate-muted text-center">
          <svg
            className="w-12 h-12 mx-auto mb-3 opacity-50"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <rect x="3" y="4" width="18" height="16" rx="2" />
            <line x1="3" y1="10" x2="21" y2="10" />
            <line x1="8" y1="4" x2="8" y2="10" />
            <line x1="16" y1="4" x2="16" y2="10" />
          </svg>
          <p className="font-medium mb-1">No tasks to display</p>
          <p className="text-sm">Add tasks with dates to see them on the timeline</p>
        </div>
      </div>
    );
  }

  // No layout (shouldn't happen with tasks, but safety check)
  if (!layout) {
    return null;
  }

  const todayX = showTodayMarker ? getTodayX(layout) : null;
  const config = DEFAULT_GANTT_CONFIG;

  return (
    <div className={cn('flex flex-col', className)}>
      {/* Controls */}
      <div className="flex items-center justify-between mb-3">
        <div className="text-sm text-slate-muted">
          {tasks.length} task{tasks.length !== 1 ? 's' : ''}
          {dependencies.length > 0 && (
            <span className="ml-2">
              ({dependencies.length} dependenc{dependencies.length !== 1 ? 'ies' : 'y'})
            </span>
          )}
        </div>
        <GanttControls
          zoomLevel={zoomLevel}
          onZoomChange={handleZoomChange}
          onScrollToToday={handleScrollToToday}
        />
      </div>

      {/* Chart container */}
      <div
        ref={scrollContainerRef}
        className="overflow-x-auto overflow-y-auto bg-slate-card border border-slate-border rounded-xl"
        style={{ height }}
      >
        <svg
          width={layout.chartWidth}
          height={layout.chartHeight}
          className="gantt-chart"
        >
          {/* Timeline header */}
          <GanttTimeline layout={layout} zoomLevel={zoomLevel} />

          {/* Task rows */}
          <g className="gantt-task-rows">
            {tasks.map((task, index) => (
              <GanttTaskRow
                key={task.id}
                task={task}
                layout={layout}
                config={config}
                rowIndex={index}
                showProgress={showProgress}
                isHovered={hoveredTask?.id === task.id}
                onHover={handleTaskHover}
                onClick={onTaskClick}
              />
            ))}
          </g>

          {/* Dependency arrows */}
          {showDependencies && dependencies.length > 0 && (
            <GanttDependencyArrows
              dependencies={dependencies}
              layout={layout}
              config={config}
            />
          )}

          {/* Today marker */}
          {todayX !== null && (
            <g className="gantt-today-marker">
              <line
                x1={todayX}
                y1={config.headerHeight}
                x2={todayX}
                y2={layout.chartHeight}
                stroke={GANTT_COLORS.todayMarker}
                strokeWidth={config.todayMarkerWidth}
                strokeDasharray="4 2"
              />
              <circle
                cx={todayX}
                cy={config.headerHeight - 4}
                r={4}
                fill={GANTT_COLORS.todayMarker}
              />
            </g>
          )}
        </svg>
      </div>

      {/* Tooltip */}
      <GanttTooltip
        task={hoveredTask}
        position={tooltipPosition}
        visible={!!hoveredTask}
      />
    </div>
  );
}

export default GanttChart;
