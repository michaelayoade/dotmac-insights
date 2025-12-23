import { useState, useMemo, useCallback } from 'react';

export type SortOrder = 'asc' | 'desc';

export interface UseTableSortOptions<T extends string> {
  /** Initial sort field */
  defaultField: T;
  /** Initial sort order */
  defaultOrder?: SortOrder;
}

export interface UseTableSortReturn<T extends string, R> {
  /** Current sort field */
  sortField: T;
  /** Current sort order */
  sortOrder: SortOrder;
  /** Sorted items */
  sortedItems: R[];
  /** Toggle sort on a field (flips order if same field, else sets to desc) */
  toggleSort: (field: T) => void;
  /** Check if a field is the current sort field */
  isActive: (field: T) => boolean;
}

/**
 * Generic hook for client-side table sorting.
 *
 * @example
 * type SortField = 'name' | 'count' | 'date';
 * const { sortedItems, toggleSort, sortField, sortOrder, isActive } = useTableSort<SortField, Item>(
 *   items,
 *   { defaultField: 'count', defaultOrder: 'desc' }
 * );
 */
export function useTableSort<T extends string, R extends object>(
  items: R[],
  options: UseTableSortOptions<T>
): UseTableSortReturn<T, R> {
  const { defaultField, defaultOrder = 'desc' } = options;

  const [sortField, setSortField] = useState<T>(defaultField);
  const [sortOrder, setSortOrder] = useState<SortOrder>(defaultOrder);

  const sortedItems = useMemo(() => {
    if (!items?.length) return [];

    return [...items].sort((a, b) => {
      const aRecord = a as Record<string, unknown>;
      const bRecord = b as Record<string, unknown>;
      let aVal = aRecord[sortField] ?? '';
      let bVal = bRecord[sortField] ?? '';

      // Handle string comparison (case-insensitive)
      if (typeof aVal === 'string') aVal = aVal.toLowerCase();
      if (typeof bVal === 'string') bVal = bVal.toLowerCase();

      // Handle null/undefined
      if (aVal === null || aVal === undefined) aVal = '';
      if (bVal === null || bVal === undefined) bVal = '';

      if (aVal < bVal) return sortOrder === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortOrder === 'asc' ? 1 : -1;
      return 0;
    });
  }, [items, sortField, sortOrder]);

  const toggleSort = useCallback((field: T) => {
    if (sortField === field) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortOrder('desc');
    }
  }, [sortField]);

  const isActive = useCallback((field: T) => sortField === field, [sortField]);

  return {
    sortField,
    sortOrder,
    sortedItems,
    toggleSort,
    isActive,
  };
}
