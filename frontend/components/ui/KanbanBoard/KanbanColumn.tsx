'use client';

import { cn } from '@/lib/utils';
import { Plus } from 'lucide-react';
import type { KanbanItem, KanbanColumn as KanbanColumnType } from './types';
import { getColumnColors } from './types';

// =============================================================================
// KANBAN COLUMN
// =============================================================================

export interface KanbanColumnProps<T extends KanbanItem> {
  column: KanbanColumnType<T>;
  width?: number | string;
  isDragOver?: boolean;
  onDragOver: (e: React.DragEvent) => void;
  onDragLeave: () => void;
  onDrop: (e: React.DragEvent) => void;
  renderHeader?: (column: KanbanColumnType<T>) => React.ReactNode;
  renderFooter?: (column: KanbanColumnType<T>) => React.ReactNode;
  showAddButton?: boolean;
  onAddClick?: () => void;
  children: React.ReactNode;
  className?: string;
}

export function KanbanColumn<T extends KanbanItem>({
  column,
  width = 320,
  isDragOver = false,
  onDragOver,
  onDragLeave,
  onDrop,
  renderHeader,
  renderFooter,
  showAddButton = true,
  onAddClick,
  children,
  className,
}: KanbanColumnProps<T>) {
  const colors = getColumnColors(column.color);

  return (
    <div
      className={cn(
        'flex-shrink-0 flex flex-col rounded-xl border-t-2',
        colors.border,
        colors.bg,
        isDragOver && 'ring-2 ring-teal-electric/50',
        className
      )}
      style={{ width }}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      {/* Column Header */}
      {renderHeader ? (
        renderHeader(column)
      ) : (
        <DefaultColumnHeader column={column} colors={colors} />
      )}

      {/* Column Body */}
      <div className="flex-1 p-2 space-y-2 overflow-y-auto bg-slate-card/20">
        {children}
      </div>

      {/* Column Footer */}
      {renderFooter ? (
        renderFooter(column)
      ) : showAddButton && onAddClick ? (
        <button
          onClick={onAddClick}
          className="flex items-center justify-center gap-2 p-3 bg-slate-card/30 hover:bg-slate-card/50 text-slate-muted hover:text-foreground transition-colors rounded-b-xl"
        >
          <Plus className="w-4 h-4" />
          <span className="text-sm">Add Item</span>
        </button>
      ) : null}
    </div>
  );
}

// Default column header component
function DefaultColumnHeader<T extends KanbanItem>({
  column,
  colors,
}: {
  column: KanbanColumnType<T>;
  colors: ReturnType<typeof getColumnColors>;
}) {
  const Icon = column.icon;

  return (
    <div className={cn('p-4 rounded-t-xl', colors.header)}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {Icon && <Icon className="w-4 h-4 text-slate-muted" />}
          <h3 className="font-medium text-foreground">{column.title}</h3>
        </div>
        <span className="text-xs text-slate-muted bg-slate-elevated/50 px-2 py-0.5 rounded-full">
          {column.items.length}
        </span>
      </div>
      {column.metadata && (
        <div className="flex items-center justify-between text-sm text-slate-muted">
          {Object.entries(column.metadata).map(([key, value]) => (
            <span key={key}>
              {typeof value === 'number' ? value.toLocaleString() : String(value)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default KanbanColumn;
