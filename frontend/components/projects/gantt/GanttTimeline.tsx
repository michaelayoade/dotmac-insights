'use client';

/**
 * GanttTimeline Component
 *
 * Renders the timeline header with date labels.
 * Supports day, week, and month zoom levels.
 */

import React, { memo, useMemo } from 'react';
import { isWeekend } from 'date-fns';
import type { GanttTimelineProps } from './types';
import { GANTT_COLORS, ZOOM_PIXELS, DEFAULT_GANTT_CONFIG } from './constants';
import { getTimeUnits, getPrimaryHeaders, dateToX } from './utils';

/**
 * Timeline header component with primary and secondary date labels.
 */
function GanttTimelineComponent({ layout, zoomLevel }: GanttTimelineProps) {
  const config = DEFAULT_GANTT_CONFIG;

  // Get time units for the secondary row (days/weeks/months)
  const timeUnits = useMemo(
    () => getTimeUnits(layout.startDate, layout.endDate, zoomLevel),
    [layout.startDate, layout.endDate, zoomLevel]
  );

  // Get primary headers (months for day view, years for month view)
  const primaryHeaders = useMemo(
    () => getPrimaryHeaders(layout.startDate, layout.endDate, zoomLevel),
    [layout.startDate, layout.endDate, zoomLevel]
  );

  const pixelsPerUnit = ZOOM_PIXELS[zoomLevel];
  const primaryRowHeight = config.headerHeight / 2;
  const secondaryRowHeight = config.headerHeight / 2;

  return (
    <g className="gantt-timeline">
      {/* Header background */}
      <rect
        x={0}
        y={0}
        width={layout.chartWidth}
        height={config.headerHeight}
        fill={GANTT_COLORS.gridAlt}
      />

      {/* Left panel header */}
      <rect
        x={0}
        y={0}
        width={config.leftPanelWidth}
        height={config.headerHeight}
        fill={GANTT_COLORS.gridAlt}
      />
      <text
        x={config.leftPanelWidth / 2}
        y={config.headerHeight / 2}
        fill={GANTT_COLORS.headerText}
        fontSize={12}
        fontWeight={500}
        textAnchor="middle"
        dominantBaseline="middle"
      >
        Tasks
      </text>

      {/* Left panel divider */}
      <line
        x1={config.leftPanelWidth}
        y1={0}
        x2={config.leftPanelWidth}
        y2={config.headerHeight}
        stroke={GANTT_COLORS.grid}
        strokeWidth={1}
      />

      {/* Primary row (months/years) */}
      <g className="gantt-timeline-primary">
        {primaryHeaders.map((header, index) => {
          const startX = dateToX(
            header.date,
            layout.startDate,
            layout.pixelsPerDay,
            config.leftPanelWidth
          );
          const width = header.span * pixelsPerUnit;

          return (
            <g key={`primary-${index}`}>
              {/* Header cell background */}
              <rect
                x={startX}
                y={0}
                width={width}
                height={primaryRowHeight}
                fill="transparent"
                stroke={GANTT_COLORS.grid}
                strokeWidth={0.5}
              />
              {/* Header label */}
              <text
                x={startX + width / 2}
                y={primaryRowHeight / 2}
                fill={GANTT_COLORS.headerText}
                fontSize={11}
                fontWeight={500}
                textAnchor="middle"
                dominantBaseline="middle"
              >
                {header.label}
              </text>
            </g>
          );
        })}
      </g>

      {/* Secondary row (days/weeks/months) */}
      <g className="gantt-timeline-secondary">
        {timeUnits.map((unit, index) => {
          const x = dateToX(
            unit.date,
            layout.startDate,
            layout.pixelsPerDay,
            config.leftPanelWidth
          );
          const width = pixelsPerUnit;
          const isWeekendDay = zoomLevel === 'day' && unit.isWeekend;

          return (
            <g key={`secondary-${index}`}>
              {/* Cell background (weekend highlight for day view) */}
              <rect
                x={x}
                y={primaryRowHeight}
                width={width}
                height={secondaryRowHeight}
                fill={isWeekendDay ? GANTT_COLORS.weekendBg : 'transparent'}
                stroke={GANTT_COLORS.grid}
                strokeWidth={0.5}
              />
              {/* Cell label */}
              <text
                x={x + width / 2}
                y={primaryRowHeight + secondaryRowHeight / 2}
                fill={GANTT_COLORS.headerText}
                fontSize={10}
                textAnchor="middle"
                dominantBaseline="middle"
                opacity={isWeekendDay ? 0.6 : 1}
              >
                {unit.label}
              </text>
            </g>
          );
        })}
      </g>

      {/* Header bottom border */}
      <line
        x1={0}
        y1={config.headerHeight}
        x2={layout.chartWidth}
        y2={config.headerHeight}
        stroke={GANTT_COLORS.grid}
        strokeWidth={1}
      />

      {/* Weekend column backgrounds (for day view) */}
      {zoomLevel === 'day' && (
        <g className="gantt-weekend-columns">
          {timeUnits
            .filter((unit) => unit.isWeekend)
            .map((unit, index) => {
              const x = dateToX(
                unit.date,
                layout.startDate,
                layout.pixelsPerDay,
                config.leftPanelWidth
              );
              return (
                <rect
                  key={`weekend-${index}`}
                  x={x}
                  y={config.headerHeight}
                  width={pixelsPerUnit}
                  height={layout.chartHeight - config.headerHeight}
                  fill={GANTT_COLORS.weekendBg}
                  opacity={0.3}
                />
              );
            })}
        </g>
      )}

      {/* Vertical grid lines */}
      <g className="gantt-grid-lines">
        {timeUnits.map((unit, index) => {
          const x = dateToX(
            unit.date,
            layout.startDate,
            layout.pixelsPerDay,
            config.leftPanelWidth
          );
          return (
            <line
              key={`grid-${index}`}
              x1={x}
              y1={config.headerHeight}
              x2={x}
              y2={layout.chartHeight}
              stroke={GANTT_COLORS.grid}
              strokeWidth={0.5}
              opacity={0.3}
            />
          );
        })}
      </g>
    </g>
  );
}

// Memoize to prevent unnecessary re-renders
export const GanttTimeline = memo(GanttTimelineComponent);

export default GanttTimeline;
