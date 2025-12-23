'use client';

/**
 * GanttDependencyArrows Component
 *
 * Renders SVG arrows connecting dependent tasks.
 * Uses bezier curves for smooth paths.
 */

import React, { memo } from 'react';
import type { GanttDependencyArrowsProps } from './types';
import { GANTT_COLORS, DEFAULT_GANTT_CONFIG } from './constants';
import { calculateDependencyPath } from './utils';

/**
 * Component for rendering dependency arrows between tasks.
 */
function GanttDependencyArrowsComponent({
  dependencies,
  layout,
  config,
}: GanttDependencyArrowsProps) {
  // Filter dependencies to only those with valid positions
  const visibleDependencies = dependencies.filter((dep) => {
    const fromPos = layout.taskPositions.get(dep.fromTaskId);
    const toPos = layout.taskPositions.get(dep.toTaskId);
    return fromPos && toPos;
  });

  if (visibleDependencies.length === 0) {
    return null;
  }

  return (
    <g className="gantt-dependencies">
      {/* Arrow marker definition */}
      <defs>
        <marker
          id="gantt-arrowhead"
          markerWidth={8}
          markerHeight={8}
          refX={7}
          refY={4}
          orient="auto"
          markerUnits="strokeWidth"
        >
          <path
            d="M 0 0 L 8 4 L 0 8 Z"
            fill={GANTT_COLORS.dependencyArrow}
            opacity={0.7}
          />
        </marker>
      </defs>

      {/* Dependency arrows */}
      {visibleDependencies.map((dep) => {
        const fromPos = layout.taskPositions.get(dep.fromTaskId)!;
        const toPos = layout.taskPositions.get(dep.toTaskId)!;

        // Calculate the bezier path
        const path = calculateDependencyPath(fromPos, toPos, config);

        return (
          <g
            key={`dep-${dep.fromTaskId}-${dep.toTaskId}`}
            className="gantt-dependency-arrow"
          >
            {/* Shadow/glow effect for better visibility */}
            <path
              d={path}
              fill="none"
              stroke={GANTT_COLORS.grid}
              strokeWidth={config.arrowStrokeWidth + 2}
              opacity={0.2}
              className="pointer-events-none"
            />

            {/* Main arrow path */}
            <path
              d={path}
              fill="none"
              stroke={GANTT_COLORS.dependencyLine}
              strokeWidth={config.arrowStrokeWidth}
              markerEnd="url(#gantt-arrowhead)"
              opacity={0.6}
              className="pointer-events-none transition-opacity hover:opacity-100"
            />
          </g>
        );
      })}
    </g>
  );
}

// Memoize to prevent unnecessary re-renders
export const GanttDependencyArrows = memo(GanttDependencyArrowsComponent);

export default GanttDependencyArrows;
