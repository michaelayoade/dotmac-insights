import { LucideIcon } from 'lucide-react';

// =============================================================================
// KANBAN TYPES
// =============================================================================

/**
 * A single item in a Kanban column
 */
export interface KanbanItem {
  id: string | number;
  [key: string]: unknown;
}

/**
 * A column in the Kanban board
 */
export interface KanbanColumn<T extends KanbanItem = KanbanItem> {
  /** Unique identifier for the column */
  id: string | number;
  /** Display title */
  title: string;
  /** Items in this column */
  items: T[];
  /** Color key (maps to color scheme) */
  color?: string;
  /** Optional icon */
  icon?: LucideIcon;
  /** Optional metadata (e.g., probability, value) */
  metadata?: Record<string, unknown>;
  /** Whether new items can be added to this column */
  allowAdd?: boolean;
}

/**
 * Result of a drag operation
 */
export interface DragResult<T extends KanbanItem = KanbanItem> {
  item: T;
  sourceColumnId: string | number;
  destinationColumnId: string | number;
  sourceIndex: number;
  destinationIndex: number;
}

/**
 * Color schemes for Kanban columns
 */
export const KANBAN_COLORS: Record<string, { border: string; bg: string; header: string }> = {
  slate: {
    border: 'border-slate-500',
    bg: 'bg-slate-500/10',
    header: 'bg-slate-800/50',
  },
  blue: {
    border: 'border-blue-500',
    bg: 'bg-blue-500/10',
    header: 'bg-blue-900/30',
  },
  cyan: {
    border: 'border-cyan-500',
    bg: 'bg-cyan-500/10',
    header: 'bg-cyan-900/30',
  },
  teal: {
    border: 'border-teal-500',
    bg: 'bg-teal-500/10',
    header: 'bg-teal-900/30',
  },
  emerald: {
    border: 'border-emerald-500',
    bg: 'bg-emerald-500/10',
    header: 'bg-emerald-900/30',
  },
  green: {
    border: 'border-green-500',
    bg: 'bg-green-500/10',
    header: 'bg-green-900/30',
  },
  amber: {
    border: 'border-amber-500',
    bg: 'bg-amber-500/10',
    header: 'bg-amber-900/30',
  },
  orange: {
    border: 'border-orange-500',
    bg: 'bg-orange-500/10',
    header: 'bg-orange-900/30',
  },
  red: {
    border: 'border-red-500',
    bg: 'bg-red-500/10',
    header: 'bg-red-900/30',
  },
  rose: {
    border: 'border-rose-500',
    bg: 'bg-rose-500/10',
    header: 'bg-rose-900/30',
  },
  purple: {
    border: 'border-purple-500',
    bg: 'bg-purple-500/10',
    header: 'bg-purple-900/30',
  },
  indigo: {
    border: 'border-indigo-500',
    bg: 'bg-indigo-500/10',
    header: 'bg-indigo-900/30',
  },
};

export function getColumnColors(color?: string) {
  return KANBAN_COLORS[color || 'slate'] || KANBAN_COLORS.slate;
}
