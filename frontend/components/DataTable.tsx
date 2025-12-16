'use client';

import { useEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { ChevronUp, ChevronDown, ChevronsUpDown } from 'lucide-react';

interface Column<T = any> {
  key: string;
  header: string;
  render?: (item: T) => React.ReactNode;
  sortable?: boolean;
  align?: 'left' | 'center' | 'right';
  width?: string;
}

interface DataTableProps<T = any> {
  columns: Column<T>[];
  data: T[];
  keyField: string;
  loading?: boolean;
  emptyMessage?: string;
  onRowClick?: (item: T) => void;
  className?: string;
  selectable?: boolean;
  selectedRowIds?: Record<string, boolean> | Set<string>;
  onSelectChange?: (selected: Record<string, boolean>) => void;
}

export function DataTable<T = any>({
  columns,
  data,
  keyField,
  loading = false,
  emptyMessage = 'No data available',
  onRowClick,
  className,
  selectable = false,
  selectedRowIds,
  onSelectChange,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const selectAllRef = useRef<HTMLInputElement>(null);
  const selection =
    selectedRowIds instanceof Set
      ? Object.fromEntries(Array.from(selectedRowIds).map((id) => [id, true]))
      : selectedRowIds || {};

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const sortedData = sortKey
    ? [...data].sort((a, b) => {
      const aVal = (a as Record<string, unknown>)[sortKey];
      const bVal = (b as Record<string, unknown>)[sortKey];
      if (aVal === bVal) return 0;
      if (aVal === null || aVal === undefined) return 1;
      if (bVal === null || bVal === undefined) return -1;
      const comparison = aVal < bVal ? -1 : 1;
      return sortDir === 'asc' ? comparison : -comparison;
    })
    : data;

  const getRowKey = (item: T, fallback?: string) => {
    const value = (item as any)[keyField];
    if (value === undefined || value === null) return fallback || '';
    return String(value);
  };

  const allSelected =
    selectable &&
    sortedData.length > 0 &&
    sortedData.every((item, index) => selection[getRowKey(item, `row-${index}`)]);

  const hasSelection = selectable && Object.values(selection).some(Boolean);

  useEffect(() => {
    if (selectAllRef.current) {
      selectAllRef.current.indeterminate = Boolean(hasSelection && !allSelected);
    }
  }, [allSelected, hasSelection]);

  const handleToggleRow = (rowKey: string, checked: boolean) => {
    if (!onSelectChange) return;
    const next = { ...selection };
    if (checked) {
      next[rowKey] = true;
    } else {
      delete next[rowKey];
    }
    onSelectChange(next);
  };

  const handleToggleAll = (checked: boolean) => {
    if (!onSelectChange) return;
    if (!checked) {
      onSelectChange({});
      return;
    }

    const next: Record<string, boolean> = {};
    sortedData.forEach((item, index) => {
      const rowKey = getRowKey(item, `row-${index}`);
      next[rowKey] = true;
    });
    onSelectChange(next);
  };

  if (loading) {
    return (
      <div className={cn('bg-slate-card rounded-xl border border-slate-border overflow-hidden', className)}>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-border bg-slate-elevated/50">
                {selectable && (
                  <th className="w-12 px-4 py-3 text-left text-xs font-semibold text-slate-muted uppercase tracking-wide">
                    <div className="h-4 w-4 rounded border border-slate-border bg-slate-elevated" />
                  </th>
                )}
                {columns.map((col) => (
                  <th
                    key={col.key}
                    className="px-4 py-3 text-left text-xs font-semibold text-slate-muted uppercase tracking-wide"
                  >
                    {col.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[...Array(5)].map((_, i) => (
                <tr key={i} className="border-b border-slate-border">
                  {selectable && (
                    <td className="px-4 py-3">
                      <div className="h-4 w-4 rounded border border-slate-border bg-slate-elevated" />
                    </td>
                  )}
                  {columns.map((col) => (
                    <td key={col.key} className="px-4 py-3">
                      <div className="skeleton h-4 w-24 rounded" />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  if (!data.length) {
    return (
      <div className={cn('bg-slate-card rounded-xl border border-slate-border p-12 text-center', className)}>
        <p className="text-slate-muted">{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className={cn('bg-slate-card rounded-xl border border-slate-border overflow-hidden', className)}>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-border bg-slate-elevated/50">
              {selectable && (
                <th className="w-12 px-4 py-3">
                  <input
                    ref={selectAllRef}
                    type="checkbox"
                    checked={allSelected}
                    onChange={(e) => handleToggleAll(e.target.checked)}
                    className="h-4 w-4 rounded border border-slate-border bg-slate-elevated accent-teal-electric"
                  />
                </th>
              )}
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={cn(
                    'px-4 py-3 text-xs font-semibold text-slate-muted uppercase tracking-wide',
                    col.align === 'center' && 'text-center',
                    col.align === 'right' && 'text-right',
                    !col.align && 'text-left',
                    col.sortable && 'cursor-pointer hover:text-white transition-colors select-none'
                  )}
                  style={{ width: col.width }}
                  onClick={() => col.sortable && handleSort(col.key)}
                >
                  <div className="flex items-center gap-1">
                    {col.header}
                    {col.sortable && (
                      <span className="text-slate-muted">
                        {sortKey === col.key ? (
                          sortDir === 'asc' ? (
                            <ChevronUp className="w-4 h-4" />
                          ) : (
                            <ChevronDown className="w-4 h-4" />
                          )
                        ) : (
                          <ChevronsUpDown className="w-4 h-4 opacity-50" />
                        )}
                      </span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedData.map((item, index) => (
              <tr
                key={getRowKey(item, `row-${index}`)}
                className={cn(
                  'border-b border-slate-border last:border-0 transition-colors',
                  onRowClick && 'cursor-pointer hover:bg-slate-elevated/50',
                  index % 2 === 0 ? 'bg-transparent' : 'bg-slate-elevated/20'
                )}
                onClick={() => onRowClick?.(item)}
              >
                {selectable && (
                  <td className="px-4 py-3" onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={Boolean(selection[getRowKey(item, `row-${index}`)])}
                      onChange={(e) => handleToggleRow(getRowKey(item, `row-${index}`), e.target.checked)}
                      className="h-4 w-4 rounded border border-slate-border bg-slate-elevated accent-teal-electric"
                    />
                  </td>
                )}
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={cn(
                      'px-4 py-3 font-mono text-sm',
                      col.align === 'center' && 'text-center',
                      col.align === 'right' && 'text-right'
                    )}
                  >
                    {col.render
                      ? col.render(item)
                      : String((item as Record<string, unknown>)[col.key as string] ?? '—')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Pagination component
interface PaginationProps {
  total: number;
  limit: number;
  offset: number;
  onPageChange: (offset: number) => void;
  onLimitChange?: (limit: number) => void;
  limitOptions?: number[];
}

export function Pagination({
  total,
  limit,
  offset,
  onPageChange,
  onLimitChange,
  limitOptions = [20, 50, 100]
}: PaginationProps) {
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(total / limit);

  const pages: (number | 'ellipsis')[] = [];

  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) {
      pages.push(i);
    }
  } else {
    pages.push(1);
    if (currentPage > 3) pages.push('ellipsis');

    const start = Math.max(2, currentPage - 1);
    const end = Math.min(totalPages - 1, currentPage + 1);

    for (let i = start; i <= end; i++) {
      pages.push(i);
    }

    if (currentPage < totalPages - 2) pages.push('ellipsis');
    pages.push(totalPages);
  }

  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-slate-border">
      <div className="flex items-center gap-4">
        <span className="text-slate-muted text-sm">
          Showing {offset + 1} to {Math.min(offset + limit, total)} of {total}
        </span>
        {onLimitChange && (
          <div className="flex items-center gap-2">
            <span className="text-slate-muted text-sm">Per page:</span>
            <select
              value={limit}
              onChange={(e) => {
                onLimitChange(Number(e.target.value));
                onPageChange(0); // Reset to first page when changing limit
              }}
              className="bg-slate-elevated border border-slate-border rounded-lg px-2 py-1 text-sm text-white focus:outline-none focus:ring-2 focus:ring-teal-electric/50"
            >
              {limitOptions.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
      {totalPages > 1 && (
        <div className="flex items-center gap-1">
          <button
            onClick={() => onPageChange(Math.max(0, offset - limit))}
            disabled={offset === 0}
            className="px-3 py-1.5 text-sm rounded-lg border border-slate-border text-slate-muted hover:text-white hover:border-slate-elevated disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Previous
          </button>

          {pages.map((page, index) =>
            page === 'ellipsis' ? (
              <span key={`ellipsis-${index}`} className="px-2 text-slate-muted">
                ...
              </span>
            ) : (
              <button
                key={page}
                onClick={() => onPageChange((page - 1) * limit)}
                className={cn(
                  'w-8 h-8 text-sm rounded-lg transition-colors',
                  currentPage === page
                    ? 'bg-teal-electric/20 text-teal-electric border border-teal-electric/30'
                    : 'text-slate-muted hover:text-white hover:bg-slate-elevated'
                )}
              >
                {page}
              </button>
            )
          )}

          <button
            onClick={() => onPageChange(offset + limit)}
            disabled={offset + limit >= total}
            className="px-3 py-1.5 text-sm rounded-lg border border-slate-border text-slate-muted hover:text-white hover:border-slate-elevated disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
