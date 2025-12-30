'use client';

import { useState, useCallback, useMemo } from 'react';
import { cn } from '@/lib/utils';
import { Plus, Trash2, GripVertical, AlertCircle } from 'lucide-react';
import { LineItemRow } from './LineItemRow';
import type { LineItemColumn, TotalConfig, LineItemValidation } from './types';

// =============================================================================
// LINE ITEM EDITOR
// =============================================================================

export interface LineItemEditorProps<T extends Record<string, unknown>> {
  /** Array of line items */
  items: T[];
  /** Callback when items change */
  onChange: (items: T[]) => void;
  /** Column definitions */
  columns: LineItemColumn<T>[];
  /** Function to create a new empty row */
  createRow?: () => T;
  /** Callback when a row is deleted */
  onDeleteRow?: (index: number, row: T) => void;
  /** Minimum number of rows */
  minRows?: number;
  /** Maximum number of rows */
  maxRows?: number;
  /** Show totals row */
  showTotals?: boolean;
  /** Totals configuration */
  totalsConfig?: TotalConfig<T>[];
  /** Whether the editor is read-only */
  readOnly?: boolean;
  /** Show row numbers */
  showRowNumbers?: boolean;
  /** Allow row reordering */
  allowReorder?: boolean;
  /** Validation errors */
  errors?: LineItemValidation[];
  /** Custom class name */
  className?: string;
  /** Class for the table */
  tableClassName?: string;
  /** Add button label */
  addButtonLabel?: string;
  /** Empty state message */
  emptyMessage?: string;
}

export function LineItemEditor<T extends Record<string, unknown>>({
  items,
  onChange,
  columns,
  createRow,
  onDeleteRow,
  minRows = 0,
  maxRows,
  showTotals = false,
  totalsConfig,
  readOnly = false,
  showRowNumbers = true,
  allowReorder = false,
  errors = [],
  className,
  tableClassName,
  addButtonLabel = 'Add Row',
  emptyMessage = 'No items. Click "Add Row" to start.',
}: LineItemEditorProps<T>) {
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);

  // Handle row value change
  const handleRowChange = useCallback(
    (index: number, key: keyof T, value: unknown) => {
      const newItems = [...items];
      newItems[index] = { ...newItems[index], [key]: value };

      // Apply computed values
      columns.forEach((col) => {
        if (col.compute) {
          newItems[index] = {
            ...newItems[index],
            [col.key]: col.compute(newItems[index], newItems, index),
          };
        }
      });

      onChange(newItems);
    },
    [items, columns, onChange]
  );

  // Add new row
  const handleAddRow = useCallback(() => {
    if (maxRows && items.length >= maxRows) return;

    const newRow = createRow ? createRow() : ({} as T);
    onChange([...items, newRow]);
  }, [items, maxRows, createRow, onChange]);

  // Delete row
  const handleDeleteRow = useCallback(
    (index: number) => {
      if (items.length <= minRows) return;

      const row = items[index];
      const newItems = items.filter((_, i) => i !== index);
      onChange(newItems);
      onDeleteRow?.(index, row);
    },
    [items, minRows, onChange, onDeleteRow]
  );

  // Drag and drop handlers
  const handleDragStart = useCallback((e: React.DragEvent, index: number) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = 'move';
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent, index: number) => {
    e.preventDefault();
    setDragOverIndex(index);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent, targetIndex: number) => {
      e.preventDefault();
      if (draggedIndex === null || draggedIndex === targetIndex) {
        setDraggedIndex(null);
        setDragOverIndex(null);
        return;
      }

      const newItems = [...items];
      const [removed] = newItems.splice(draggedIndex, 1);
      newItems.splice(targetIndex, 0, removed);
      onChange(newItems);

      setDraggedIndex(null);
      setDragOverIndex(null);
    },
    [draggedIndex, items, onChange]
  );

  const handleDragEnd = useCallback(() => {
    setDraggedIndex(null);
    setDragOverIndex(null);
  }, []);

  // Calculate totals
  const totals = useMemo(() => {
    if (!showTotals || !totalsConfig) return null;

    return totalsConfig.map((config) => {
      let value: number;
      if (config.calculate) {
        value = config.calculate(items);
      } else {
        value = items.reduce((sum, row) => {
          const v = row[config.key];
          return sum + (typeof v === 'number' ? v : 0);
        }, 0);
      }
      return {
        ...config,
        value,
        formatted: config.format ? config.format(value) : value.toLocaleString(),
      };
    });
  }, [items, showTotals, totalsConfig]);

  // Get errors for a specific cell
  const getCellError = useCallback(
    (rowIndex: number, column: string) => {
      return errors.find((e) => e.rowIndex === rowIndex && e.column === column);
    },
    [errors]
  );

  const canAddRow = !readOnly && (!maxRows || items.length < maxRows);
  const canDeleteRow = !readOnly && items.length > minRows;

  return (
    <div className={cn('', className)}>
      <div className={cn('overflow-x-auto', tableClassName)}>
        <table className="w-full border-collapse">
          {/* Header */}
          <thead>
            <tr className="bg-slate-elevated border-b border-slate-border">
              {allowReorder && !readOnly && (
                <th className="w-8 px-2 py-2" />
              )}
              {showRowNumbers && (
                <th className="w-10 px-2 py-2 text-xs font-medium text-slate-muted text-center">#</th>
              )}
              {columns.map((col) => (
                <th
                  key={String(col.key)}
                  className={cn(
                    'px-3 py-2 text-xs font-medium text-slate-muted text-left',
                    col.align === 'center' && 'text-center',
                    col.align === 'right' && 'text-right',
                    col.className
                  )}
                  style={{ width: col.width }}
                >
                  {col.header}
                  {col.required && <span className="text-coral-alert ml-0.5">*</span>}
                </th>
              ))}
              {canDeleteRow && (
                <th className="w-10 px-2 py-2" />
              )}
            </tr>
          </thead>

          {/* Body */}
          <tbody>
            {items.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length + (showRowNumbers ? 1 : 0) + (allowReorder && !readOnly ? 1 : 0) + (canDeleteRow ? 1 : 0)}
                  className="px-4 py-8 text-center text-sm text-slate-muted"
                >
                  {emptyMessage}
                </td>
              </tr>
            ) : (
              items.map((row, index) => (
                <tr
                  key={index}
                  className={cn(
                    'border-b border-slate-border/50 hover:bg-slate-elevated/50 transition-colors',
                    draggedIndex === index && 'opacity-50',
                    dragOverIndex === index && 'bg-teal-electric/10'
                  )}
                  onDragOver={(e) => allowReorder && handleDragOver(e, index)}
                  onDrop={(e) => allowReorder && handleDrop(e, index)}
                >
                  {/* Drag Handle */}
                  {allowReorder && !readOnly && (
                    <td className="px-2 py-2">
                      <button
                        type="button"
                        draggable
                        onDragStart={(e) => handleDragStart(e, index)}
                        onDragEnd={handleDragEnd}
                        className="p-1 cursor-grab active:cursor-grabbing text-slate-muted hover:text-foreground"
                      >
                        <GripVertical className="w-4 h-4" />
                      </button>
                    </td>
                  )}

                  {/* Row Number */}
                  {showRowNumbers && (
                    <td className="px-2 py-2 text-xs text-slate-muted text-center">{index + 1}</td>
                  )}

                  {/* Data Cells */}
                  {columns.map((col) => {
                    const error = getCellError(index, String(col.key));
                    return (
                      <LineItemRow
                        key={String(col.key)}
                        column={col}
                        value={row[col.key]}
                        row={row}
                        rowIndex={index}
                        allRows={items}
                        onChange={(value) => handleRowChange(index, col.key, value)}
                        readOnly={readOnly || col.editable === false}
                        error={error?.message}
                      />
                    );
                  })}

                  {/* Delete Button */}
                  {canDeleteRow && (
                    <td className="px-2 py-2">
                      <button
                        type="button"
                        onClick={() => handleDeleteRow(index)}
                        className="p-1 text-slate-muted hover:text-coral-alert transition-colors"
                        title="Delete row"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>

          {/* Totals */}
          {showTotals && totals && totals.length > 0 && items.length > 0 && (
            <tfoot>
              <tr className="bg-slate-elevated border-t border-slate-border font-medium">
                {allowReorder && !readOnly && <td />}
                {showRowNumbers && <td />}
                {columns.map((col, colIndex) => {
                  const totalConfig = totals.find((t) => t.key === col.key);
                  if (totalConfig) {
                    return (
                      <td
                        key={String(col.key)}
                        className={cn(
                          'px-3 py-2 text-sm',
                          col.align === 'center' && 'text-center',
                          col.align === 'right' && 'text-right',
                          'text-foreground'
                        )}
                      >
                        {totalConfig.formatted}
                      </td>
                    );
                  }
                  // Show label in first empty column
                  if (colIndex === 0 && !totals.find((t) => t.key === columns[0].key)) {
                    return (
                      <td key={String(col.key)} className="px-3 py-2 text-sm text-slate-muted text-right">
                        Total:
                      </td>
                    );
                  }
                  return <td key={String(col.key)} />;
                })}
                {canDeleteRow && <td />}
              </tr>
            </tfoot>
          )}
        </table>
      </div>

      {/* Add Row Button */}
      {canAddRow && (
        <button
          type="button"
          onClick={handleAddRow}
          className="mt-2 flex items-center gap-2 px-3 py-2 text-sm text-teal-electric hover:text-teal-glow transition-colors"
        >
          <Plus className="w-4 h-4" />
          {addButtonLabel}
        </button>
      )}

      {/* Validation Errors Summary */}
      {errors.length > 0 && (
        <div className="mt-3 p-3 bg-coral-alert/10 border border-coral-alert/30 rounded-lg">
          <div className="flex items-center gap-2 text-coral-alert text-sm font-medium mb-1">
            <AlertCircle className="w-4 h-4" />
            Validation Errors
          </div>
          <ul className="text-xs text-coral-alert space-y-1">
            {errors.slice(0, 5).map((error, i) => (
              <li key={i}>
                Row {error.rowIndex + 1}, {error.column}: {error.message}
              </li>
            ))}
            {errors.length > 5 && (
              <li>...and {errors.length - 5} more errors</li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

export default LineItemEditor;
