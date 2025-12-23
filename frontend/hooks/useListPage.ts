import { useState, useCallback, useMemo } from 'react';
import { usePagination, type UsePaginationOptions, type UsePaginationReturn } from './usePagination';

// =============================================================================
// LIST PAGE HOOK - Composite hook for list pages
// =============================================================================

export type SortOrder = 'asc' | 'desc';

export interface FilterConfig {
  /** Filter field name */
  name: string;
  /** Filter type for rendering */
  type: 'text' | 'select' | 'date' | 'date-range' | 'boolean' | 'multi-select';
  /** Default value */
  defaultValue?: string | boolean | null;
  /** Label for UI */
  label?: string;
  /** Options for select/multi-select */
  options?: Array<{ value: string; label: string }>;
  /** Placeholder text */
  placeholder?: string;
}

export interface UseListPageOptions<TSortField extends string = string> {
  /** Unique key for persisting state (future: URL sync) */
  persistKey?: string;
  /** Initial sort field */
  defaultSortField?: TSortField;
  /** Initial sort order */
  defaultSortOrder?: SortOrder;
  /** Pagination options */
  pagination?: UsePaginationOptions;
  /** Default filter values */
  defaultFilters?: Record<string, string | boolean | null>;
  /** Callback when any state changes */
  onStateChange?: () => void;
}

export interface FilterState {
  search: string;
  status: string;
  dateFrom: string | null;
  dateTo: string | null;
  [key: string]: string | boolean | null;
}

export interface UseListPageReturn<TSortField extends string = string> {
  // Pagination (delegates to usePagination)
  pagination: UsePaginationReturn;

  // Filters
  /** Current filter state */
  filters: FilterState;
  /** Set a single filter value */
  setFilter: <K extends keyof FilterState>(key: K, value: FilterState[K]) => void;
  /** Set multiple filters at once */
  setFilters: (updates: Partial<FilterState>) => void;
  /** Clear all filters to defaults */
  clearFilters: () => void;
  /** Whether any filters are active (non-default) */
  hasActiveFilters: boolean;
  /** Get active filter count */
  activeFilterCount: number;

  // Sorting
  /** Current sort field */
  sortField: TSortField;
  /** Current sort order */
  sortOrder: SortOrder;
  /** Toggle sort on a field (flips order if same field) */
  toggleSort: (field: TSortField) => void;
  /** Set sort explicitly */
  setSort: (field: TSortField, order: SortOrder) => void;
  /** Check if field is currently sorted */
  isSorted: (field: TSortField) => boolean;

  // Query builder for API calls
  /** Build params object for API calls (includes pagination, filters, sort) */
  buildApiParams: () => Record<string, string | number | boolean | undefined>;

  // Reset everything
  /** Reset all state (pagination, filters, sort) to defaults */
  resetAll: () => void;

  // Convenience helpers for filter inputs
  /** Get props for a filter input */
  getFilterProps: (name: string) => {
    value: string | boolean;
    onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => void;
  };
  /** Get props for search input */
  getSearchProps: () => {
    value: string;
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
    placeholder: string;
  };
}

const DEFAULT_FILTERS: FilterState = {
  search: '',
  status: '',
  dateFrom: null,
  dateTo: null,
};

/**
 * Composite hook for list pages that combines pagination, filtering, and sorting.
 *
 * This hook is designed to handle 90% of list page state management, reducing
 * boilerplate from ~50 lines to ~5 lines per page.
 *
 * Sorting is intended for server-side APIs (via buildApiParams). When paired with
 * ListPageTemplate, the default sort mode is server to keep UI indicators aligned.
 *
 * @example
 * // Basic usage
 * const listPage = useListPage({ persistKey: 'books.suppliers' });
 * const { data, isLoading, error } = useAccountingSuppliers(listPage.buildApiParams());
 *
 * <ListPageTemplate
 *   listPageState={listPage}
 *   data={data?.suppliers || []}
 *   ...
 * />
 *
 * @example
 * // With sorting
 * type SortField = 'name' | 'balance' | 'created_at';
 * const listPage = useListPage<SortField>({
 *   defaultSortField: 'created_at',
 *   defaultSortOrder: 'desc',
 * });
 *
 * @example
 * // With custom filters
 * const listPage = useListPage({
 *   defaultFilters: {
 *     category: 'all',
 *     includeArchived: false,
 *   },
 * });
 */
export function useListPage<TSortField extends string = string>(
  options: UseListPageOptions<TSortField> = {}
): UseListPageReturn<TSortField> {
  const {
    defaultSortField,
    defaultSortOrder = 'desc',
    pagination: paginationOptions,
    defaultFilters = {},
    onStateChange,
  } = options;

  // ===== Pagination =====
  const pagination = usePagination(paginationOptions);

  // ===== Filters =====
  const initialFilters = useMemo<FilterState>(() => {
    return { ...DEFAULT_FILTERS, ...defaultFilters };
  }, [defaultFilters]);

  const [filters, setFiltersState] = useState<FilterState>(initialFilters);

  const setFilter = useCallback(
    <K extends keyof FilterState>(key: K, value: FilterState[K]) => {
      setFiltersState((prev) => ({ ...prev, [key]: value }));
      pagination.reset(); // Reset to page 1 on filter change
      onStateChange?.();
    },
    [pagination, onStateChange]
  );

  const setFilters = useCallback(
    (updates: Partial<FilterState>) => {
      setFiltersState((prev) => {
        const next: FilterState = { ...prev };
        for (const [key, value] of Object.entries(updates)) {
          if (value !== undefined) {
            next[key as keyof FilterState] = value as FilterState[keyof FilterState];
          }
        }
        return next;
      });
      pagination.reset();
      onStateChange?.();
    },
    [pagination, onStateChange]
  );

  const clearFilters = useCallback(() => {
    setFiltersState(initialFilters);
    pagination.reset();
    onStateChange?.();
  }, [initialFilters, pagination, onStateChange]);

  const hasActiveFilters = useMemo(() => {
    return Object.keys(filters).some((key) => {
      const value = filters[key];
      const defaultValue = initialFilters[key];
      return value !== defaultValue && value !== '' && value !== null;
    });
  }, [filters, initialFilters]);

  const activeFilterCount = useMemo(() => {
    return Object.keys(filters).filter((key) => {
      const value = filters[key];
      const defaultValue = initialFilters[key];
      return value !== defaultValue && value !== '' && value !== null;
    }).length;
  }, [filters, initialFilters]);

  // ===== Sorting =====
  const [sortField, setSortField] = useState<TSortField>(
    defaultSortField || ('' as TSortField)
  );
  const [sortOrder, setSortOrder] = useState<SortOrder>(defaultSortOrder);

  const toggleSort = useCallback(
    (field: TSortField) => {
      if (sortField === field) {
        setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
      } else {
        setSortField(field);
        setSortOrder('desc');
      }
      onStateChange?.();
    },
    [sortField, onStateChange]
  );

  const setSort = useCallback(
    (field: TSortField, order: SortOrder) => {
      setSortField(field);
      setSortOrder(order);
      onStateChange?.();
    },
    [onStateChange]
  );

  const isSorted = useCallback(
    (field: TSortField) => sortField === field,
    [sortField]
  );

  // ===== API Params Builder =====
  const buildApiParams = useCallback(() => {
    const params: Record<string, string | number | boolean | undefined> = {
      ...pagination.getApiParams(),
    };

    // Add filters
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== '' && value !== null && value !== undefined) {
        params[key] = value;
      }
    });

    // Add sorting
    if (sortField) {
      params.sort_by = sortField;
      params.sort_order = sortOrder;
    }

    return params;
  }, [pagination, filters, sortField, sortOrder]);

  // ===== Reset All =====
  const resetAll = useCallback(() => {
    pagination.reset();
    setFiltersState(initialFilters);
    if (defaultSortField) {
      setSortField(defaultSortField);
    }
    setSortOrder(defaultSortOrder);
    onStateChange?.();
  }, [pagination, initialFilters, defaultSortField, defaultSortOrder, onStateChange]);

  // ===== Input Helpers =====
  const getFilterProps = useCallback(
    (name: string) => ({
      value: filters[name] ?? '',
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
        const value = e.target.type === 'checkbox'
          ? (e.target as HTMLInputElement).checked
          : e.target.value;
        setFilter(name, value);
      },
    }),
    [filters, setFilter]
  );

  const getSearchProps = useCallback(
    () => ({
      value: filters.search as string,
      onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
        setFilter('search', e.target.value);
      },
      placeholder: 'Search...',
    }),
    [filters.search, setFilter]
  );

  return {
    // Pagination
    pagination,

    // Filters
    filters,
    setFilter,
    setFilters,
    clearFilters,
    hasActiveFilters,
    activeFilterCount,

    // Sorting
    sortField,
    sortOrder,
    toggleSort,
    setSort,
    isSorted,

    // API params
    buildApiParams,

    // Reset
    resetAll,

    // Input helpers
    getFilterProps,
    getSearchProps,
  };
}
