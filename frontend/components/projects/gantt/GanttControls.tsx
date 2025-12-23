'use client';

/**
 * GanttControls Component
 *
 * Zoom level selector and navigation controls for the Gantt chart.
 */

import React, { memo } from 'react';
import { ZoomIn, ZoomOut, Calendar, ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui';
import type { GanttControlsProps, ZoomLevel } from './types';

const ZOOM_LEVELS: { value: ZoomLevel; label: string; shortLabel: string }[] = [
  { value: 'day', label: 'Day View', shortLabel: 'Day' },
  { value: 'week', label: 'Week View', shortLabel: 'Week' },
  { value: 'month', label: 'Month View', shortLabel: 'Month' },
];

/**
 * Controls component with zoom selector and today button.
 */
function GanttControlsComponent({
  zoomLevel,
  onZoomChange,
  onScrollToToday,
}: GanttControlsProps) {
  const currentIndex = ZOOM_LEVELS.findIndex((z) => z.value === zoomLevel);

  const handleZoomIn = () => {
    if (currentIndex > 0) {
      onZoomChange(ZOOM_LEVELS[currentIndex - 1].value);
    }
  };

  const handleZoomOut = () => {
    if (currentIndex < ZOOM_LEVELS.length - 1) {
      onZoomChange(ZOOM_LEVELS[currentIndex + 1].value);
    }
  };

  return (
    <div className="flex items-center gap-2">
      {/* Zoom controls */}
      <div className="flex items-center gap-1 bg-slate-elevated border border-slate-border rounded-lg p-1">
        <button
          onClick={handleZoomIn}
          disabled={currentIndex === 0}
          className={cn(
            'p-1.5 rounded-md transition-colors',
            currentIndex === 0
              ? 'text-slate-muted cursor-not-allowed'
              : 'text-foreground hover:bg-slate-card'
          )}
          title="Zoom in"
        >
          <ZoomIn className="w-4 h-4" />
        </button>

        {/* Zoom level buttons */}
        <div className="flex items-center border-x border-slate-border px-1">
          {ZOOM_LEVELS.map((level) => (
            <button
              key={level.value}
              onClick={() => onZoomChange(level.value)}
              className={cn(
                'px-2 py-1 text-xs font-medium rounded transition-colors',
                zoomLevel === level.value
                  ? 'bg-teal-electric text-slate-950'
                  : 'text-slate-muted hover:text-foreground hover:bg-slate-card'
              )}
              title={level.label}
            >
              {level.shortLabel}
            </button>
          ))}
        </div>

        <button
          onClick={handleZoomOut}
          disabled={currentIndex === ZOOM_LEVELS.length - 1}
          className={cn(
            'p-1.5 rounded-md transition-colors',
            currentIndex === ZOOM_LEVELS.length - 1
              ? 'text-slate-muted cursor-not-allowed'
              : 'text-foreground hover:bg-slate-card'
          )}
          title="Zoom out"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
      </div>

      {/* Today button */}
      <button
        onClick={onScrollToToday}
        className={cn(
          'flex items-center gap-1.5 px-3 py-1.5',
          'bg-slate-elevated border border-slate-border rounded-lg',
          'text-sm text-foreground hover:border-teal-electric/50',
          'transition-colors'
        )}
        title="Scroll to today"
      >
        <Calendar className="w-4 h-4" />
        <span>Today</span>
      </button>
    </div>
  );
}

// Memoize to prevent unnecessary re-renders
export const GanttControls = memo(GanttControlsComponent);

export default GanttControls;
