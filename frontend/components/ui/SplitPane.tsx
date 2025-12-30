'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';

// =============================================================================
// SPLIT PANE
// =============================================================================

export interface SplitPaneProps {
  /** Left panel content */
  left: React.ReactNode;
  /** Right panel content */
  right: React.ReactNode;
  /** Default width of left panel in pixels or percentage string */
  defaultLeftWidth?: number | string;
  /** Minimum width of left panel in pixels */
  minLeftWidth?: number;
  /** Maximum width of left panel in pixels */
  maxLeftWidth?: number;
  /** Whether the divider is resizable */
  resizable?: boolean;
  /** Whether left panel can be collapsed */
  collapsible?: boolean;
  /** Collapsed state (controlled) */
  collapsed?: boolean;
  /** Callback when collapsed state changes */
  onCollapsedChange?: (collapsed: boolean) => void;
  /** Persist width to localStorage with this key */
  persistKey?: string;
  /** Stack panels vertically on mobile */
  stackOnMobile?: boolean;
  /** Custom class for container */
  className?: string;
  /** Custom class for left panel */
  leftClassName?: string;
  /** Custom class for right panel */
  rightClassName?: string;
}

export function SplitPane({
  left,
  right,
  defaultLeftWidth = 384,
  minLeftWidth = 200,
  maxLeftWidth = 600,
  resizable = true,
  collapsible = false,
  collapsed: controlledCollapsed,
  onCollapsedChange,
  persistKey,
  stackOnMobile = true,
  className,
  leftClassName,
  rightClassName,
}: SplitPaneProps) {
  // Parse default width
  const parseWidth = (w: number | string): number => {
    if (typeof w === 'number') return w;
    if (w.endsWith('%')) {
      // Convert percentage to pixels (approximate)
      return (parseFloat(w) / 100) * 800;
    }
    return parseInt(w, 10) || 384;
  };

  // Load persisted width
  const getInitialWidth = (): number => {
    if (persistKey && typeof window !== 'undefined') {
      const stored = localStorage.getItem(`splitpane-${persistKey}`);
      if (stored) return parseInt(stored, 10);
    }
    return parseWidth(defaultLeftWidth);
  };

  const [leftWidth, setLeftWidth] = useState(getInitialWidth);
  const [isResizing, setIsResizing] = useState(false);
  const [internalCollapsed, setInternalCollapsed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // Use controlled or internal collapsed state
  const collapsed = controlledCollapsed ?? internalCollapsed;
  const setCollapsed = (value: boolean) => {
    if (onCollapsedChange) {
      onCollapsedChange(value);
    } else {
      setInternalCollapsed(value);
    }
  };

  // Persist width changes
  useEffect(() => {
    if (persistKey && typeof window !== 'undefined') {
      localStorage.setItem(`splitpane-${persistKey}`, String(leftWidth));
    }
  }, [leftWidth, persistKey]);

  useEffect(() => {
    if (!stackOnMobile || typeof window === 'undefined') return;

    const mediaQuery = window.matchMedia('(max-width: 1023px)');
    const handleChange = (event: MediaQueryListEvent | MediaQueryList) => {
      setIsMobile(event.matches);
    };

    handleChange(mediaQuery);
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [stackOnMobile]);

  // Handle resize
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (!resizable) return;
      e.preventDefault();
      setIsResizing(true);
    },
    [resizable]
  );

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const newWidth = e.clientX - containerRect.left;
      setLeftWidth(Math.min(Math.max(newWidth, minLeftWidth), maxLeftWidth));
    };

    const handleMouseUp = () => {
      setIsResizing(false);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing, minLeftWidth, maxLeftWidth]);

  // Handle keyboard resize
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!resizable) return;
      const step = e.shiftKey ? 50 : 10;
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        setLeftWidth((w) => Math.max(w - step, minLeftWidth));
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        setLeftWidth((w) => Math.min(w + step, maxLeftWidth));
      }
    },
    [resizable, minLeftWidth, maxLeftWidth]
  );

  return (
    <div
      ref={containerRef}
      className={cn(
        'flex h-full',
        stackOnMobile && 'flex-col lg:flex-row',
        !stackOnMobile && 'flex-row',
        className
      )}
    >
      {/* Left Panel */}
      <div
        className={cn(
          'flex-shrink-0 overflow-auto',
          stackOnMobile && 'w-full lg:w-auto',
          collapsed && 'hidden lg:hidden',
          leftClassName
        )}
        style={
          stackOnMobile
            ? { width: collapsed ? 0 : isMobile ? '100%' : leftWidth }
            : { width: collapsed ? 0 : leftWidth }
        }
      >
        <div className={cn(stackOnMobile ? 'h-auto lg:h-full' : 'h-full')}>
          {left}
        </div>
      </div>

      {/* Resize Handle */}
      {resizable && !collapsed && (
        <div
          role="separator"
          aria-orientation="vertical"
          aria-valuenow={leftWidth}
          aria-valuemin={minLeftWidth}
          aria-valuemax={maxLeftWidth}
          tabIndex={0}
          onMouseDown={handleMouseDown}
          onKeyDown={handleKeyDown}
          onDoubleClick={() => collapsible && setCollapsed(true)}
          className={cn(
            'hidden lg:flex flex-shrink-0 w-1 bg-slate-border hover:bg-teal-electric/50 transition-colors',
            'cursor-col-resize items-center justify-center group',
            isResizing && 'bg-teal-electric',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal-electric'
          )}
        >
          <div
            className={cn(
              'w-1 h-8 rounded-full bg-slate-muted/50 group-hover:bg-teal-electric/50',
              isResizing && 'bg-teal-electric'
            )}
          />
        </div>
      )}

      {/* Collapsed Expand Button */}
      {collapsible && collapsed && (
        <button
          onClick={() => setCollapsed(false)}
          className="hidden lg:flex flex-shrink-0 w-6 items-center justify-center bg-slate-elevated border-r border-slate-border hover:bg-slate-border transition-colors"
          aria-label="Expand left panel"
        >
          <svg
            className="w-4 h-4 text-slate-muted"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      )}

      {/* Right Panel */}
      <div className={cn('flex-1 min-w-0 overflow-auto', rightClassName)}>{right}</div>
    </div>
  );
}

export default SplitPane;
