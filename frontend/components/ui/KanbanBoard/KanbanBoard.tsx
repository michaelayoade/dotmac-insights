'use client';

import { useState, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { Plus } from 'lucide-react';
import { KanbanColumn as KanbanColumnComponent } from './KanbanColumn';
import { KanbanCard } from './KanbanCard';
import type { KanbanItem, KanbanColumn, DragResult, getColumnColors } from './types';

// =============================================================================
// KANBAN BOARD
// =============================================================================

export interface KanbanBoardProps<T extends KanbanItem> {
  /** Array of columns */
  columns: KanbanColumn<T>[];
  /** Callback when an item is moved */
  onMoveItem: (result: DragResult<T>) => Promise<void> | void;
  /** Custom render function for items */
  renderItem: (item: T, columnId: string | number) => React.ReactNode;
  /** Custom render function for column headers */
  renderColumnHeader?: (column: KanbanColumn<T>) => React.ReactNode;
  /** Custom render function for column footers */
  renderColumnFooter?: (column: KanbanColumn<T>) => React.ReactNode;
  /** Callback when add button is clicked in a column */
  onAddItem?: (columnId: string | number) => void;
  /** Show add button in columns */
  showAddButton?: boolean;
  /** Loading state */
  loading?: boolean;
  /** Column width */
  columnWidth?: number | string;
  /** Minimum column height */
  minColumnHeight?: number | string;
  /** Custom class name */
  className?: string;
  /** Custom class for columns container */
  columnsClassName?: string;
}

export function KanbanBoard<T extends KanbanItem>({
  columns,
  onMoveItem,
  renderItem,
  renderColumnHeader,
  renderColumnFooter,
  onAddItem,
  showAddButton = true,
  loading = false,
  columnWidth = 320,
  minColumnHeight = 'calc(100vh - 320px)',
  className,
  columnsClassName,
}: KanbanBoardProps<T>) {
  const [draggingItem, setDraggingItem] = useState<{ item: T; columnId: string | number } | null>(null);
  const [dragOverColumnId, setDragOverColumnId] = useState<string | number | null>(null);
  const [isMoving, setIsMoving] = useState(false);

  // Handle drag start
  const handleDragStart = useCallback(
    (e: React.DragEvent, item: T, columnId: string | number) => {
      setDraggingItem({ item, columnId });
      e.dataTransfer.effectAllowed = 'move';
      // Set drag image (optional - can customize)
      if (e.currentTarget instanceof HTMLElement) {
        e.dataTransfer.setDragImage(e.currentTarget, 20, 20);
      }
    },
    []
  );

  // Handle drag over column
  const handleDragOver = useCallback((e: React.DragEvent, columnId: string | number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverColumnId(columnId);
  }, []);

  // Handle drag leave
  const handleDragLeave = useCallback(() => {
    setDragOverColumnId(null);
  }, []);

  // Handle drop
  const handleDrop = useCallback(
    async (e: React.DragEvent, destinationColumnId: string | number) => {
      e.preventDefault();
      setDragOverColumnId(null);

      if (!draggingItem || draggingItem.columnId === destinationColumnId) {
        setDraggingItem(null);
        return;
      }

      // Find source column and index
      const sourceColumn = columns.find((col) => col.id === draggingItem.columnId);
      const sourceIndex = sourceColumn?.items.findIndex((item) => item.id === draggingItem.item.id) ?? -1;

      // Find destination column
      const destColumn = columns.find((col) => col.id === destinationColumnId);
      const destinationIndex = destColumn?.items.length ?? 0;

      setIsMoving(true);
      try {
        await onMoveItem({
          item: draggingItem.item,
          sourceColumnId: draggingItem.columnId,
          destinationColumnId,
          sourceIndex,
          destinationIndex,
        });
      } catch (error) {
        console.error('Failed to move item:', error);
      } finally {
        setIsMoving(false);
        setDraggingItem(null);
      }
    },
    [draggingItem, columns, onMoveItem]
  );

  // Handle drag end (cleanup)
  const handleDragEnd = useCallback(() => {
    setDraggingItem(null);
    setDragOverColumnId(null);
  }, []);

  if (loading) {
    return (
      <div className={cn('flex gap-4 overflow-x-auto pb-4', className)}>
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="flex-shrink-0 w-80 rounded-xl border border-slate-border bg-slate-card animate-pulse"
            style={{ width: columnWidth, minHeight: minColumnHeight }}
          >
            <div className="p-4 border-b border-slate-border">
              <div className="h-5 w-24 bg-slate-elevated rounded" />
              <div className="h-4 w-16 bg-slate-elevated rounded mt-2" />
            </div>
            <div className="p-2 space-y-2">
              {[1, 2, 3].map((j) => (
                <div key={j} className="h-24 bg-slate-elevated rounded-lg" />
              ))}
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className={cn('overflow-x-auto', className)}>
      <div
        className={cn('flex gap-4 pb-4', columnsClassName)}
        style={{ minHeight: minColumnHeight }}
      >
        {columns.map((column) => (
          <KanbanColumnComponent
            key={column.id}
            column={column}
            width={columnWidth}
            isDragOver={dragOverColumnId === column.id}
            onDragOver={(e) => handleDragOver(e, column.id)}
            onDragLeave={handleDragLeave}
            onDrop={(e) => handleDrop(e, column.id)}
            renderHeader={renderColumnHeader}
            renderFooter={renderColumnFooter}
            showAddButton={showAddButton && column.allowAdd !== false}
            onAddClick={() => onAddItem?.(column.id)}
          >
            {column.items.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-32 text-slate-muted text-sm">
                <p>No items</p>
                <p className="text-xs">Drag items here</p>
              </div>
            ) : (
              column.items.map((item) => (
                <KanbanCard
                  key={item.id}
                  isDragging={draggingItem?.item.id === item.id}
                  isMoving={isMoving && draggingItem?.item.id === item.id}
                  onDragStart={(e) => handleDragStart(e, item, column.id)}
                  onDragEnd={handleDragEnd}
                >
                  {renderItem(item, column.id)}
                </KanbanCard>
              ))
            )}
          </KanbanColumnComponent>
        ))}
      </div>
    </div>
  );
}

export default KanbanBoard;
