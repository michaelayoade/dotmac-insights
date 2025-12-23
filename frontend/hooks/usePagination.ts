import { useState, useCallback, useMemo } from 'react';

// =============================================================================
// PAGINATION HOOK
// =============================================================================

export interface UsePaginationOptions {
  /** Initial page size (default: 20) */
  initialPageSize?: number;
  /** Available page size options */
  pageSizeOptions?: number[];
  /** Persist state key (for URL sync - future enhancement) */
  persistKey?: string;
}

export interface UsePaginationReturn {
  // Current state
  /** Current page number (1-indexed) */
  page: number;
  /** Current page size */
  pageSize: number;
  /** Current offset (0-indexed, calculated from page * pageSize) */
  offset: number;

  // API helpers
  /** Get params for API calls: { limit, offset } */
  getApiParams: () => { limit: number; offset: number };
  /** Calculate total pages from total items */
  getTotalPages: (total: number) => number;

  // State setters
  /** Set current page (1-indexed) */
  setPage: (page: number) => void;
  /** Set page size (resets to page 1) */
  setPageSize: (size: number) => void;

  // Pagination component handlers (offset-based for compatibility)
  /** Handler for Pagination onPageChange (receives offset) */
  onPageChange: (offset: number) => void;
  /** Handler for Pagination onLimitChange */
  onLimitChange: (limit: number) => void;

  // Utilities
  /** Reset to first page */
  reset: () => void;
  /** Go to first page */
  goToFirst: () => void;
  /** Go to last page (requires total) */
  goToLast: (total: number) => void;
  /** Check if there's a next page */
  hasNextPage: (total: number) => boolean;
  /** Check if there's a previous page */
  hasPrevPage: () => boolean;
  /** Go to next page */
  nextPage: () => void;
  /** Go to previous page */
  prevPage: () => void;

  // Page size options for UI
  pageSizeOptions: number[];
}

const DEFAULT_PAGE_SIZE = 20;
const DEFAULT_PAGE_SIZE_OPTIONS = [20, 50, 100];

/**
 * Hook for managing pagination state.
 *
 * Provides both page-based state management and offset-based handlers
 * for compatibility with the existing Pagination component.
 *
 * @example
 * // Basic usage
 * const pagination = usePagination();
 * const { data } = useMyData(pagination.getApiParams());
 *
 * <Pagination
 *   total={data?.total || 0}
 *   limit={pagination.pageSize}
 *   offset={pagination.offset}
 *   onPageChange={pagination.onPageChange}
 *   onLimitChange={pagination.onLimitChange}
 * />
 *
 * @example
 * // Custom page size
 * const pagination = usePagination({ initialPageSize: 50 });
 *
 * @example
 * // Custom page size options
 * const pagination = usePagination({
 *   initialPageSize: 25,
 *   pageSizeOptions: [25, 50, 100, 200]
 * });
 */
export function usePagination(options: UsePaginationOptions = {}): UsePaginationReturn {
  const {
    initialPageSize = DEFAULT_PAGE_SIZE,
    pageSizeOptions = DEFAULT_PAGE_SIZE_OPTIONS,
  } = options;

  const [page, setPageState] = useState(1);
  const [pageSize, setPageSizeState] = useState(initialPageSize);

  // Calculate offset from page and pageSize
  const offset = useMemo(() => (page - 1) * pageSize, [page, pageSize]);

  // API params helper
  const getApiParams = useCallback(() => {
    return { limit: pageSize, offset };
  }, [pageSize, offset]);

  // Calculate total pages
  const getTotalPages = useCallback(
    (total: number) => Math.max(1, Math.ceil(total / pageSize)),
    [pageSize]
  );

  // Set page with bounds checking
  const setPage = useCallback((newPage: number) => {
    setPageState(Math.max(1, newPage));
  }, []);

  // Set page size and reset to page 1
  const setPageSize = useCallback((size: number) => {
    setPageSizeState(size);
    setPageState(1);
  }, []);

  // Handler for Pagination component (offset-based)
  const onPageChange = useCallback(
    (newOffset: number) => {
      const newPage = Math.floor(newOffset / pageSize) + 1;
      setPageState(newPage);
    },
    [pageSize]
  );

  // Handler for Pagination limit change
  const onLimitChange = useCallback((limit: number) => {
    setPageSizeState(limit);
    setPageState(1);
  }, []);

  // Utility functions
  const reset = useCallback(() => {
    setPageState(1);
  }, []);

  const goToFirst = useCallback(() => {
    setPageState(1);
  }, []);

  const goToLast = useCallback(
    (total: number) => {
      const lastPage = getTotalPages(total);
      setPageState(lastPage);
    },
    [getTotalPages]
  );

  const hasNextPage = useCallback(
    (total: number) => {
      return page < getTotalPages(total);
    },
    [page, getTotalPages]
  );

  const hasPrevPage = useCallback(() => {
    return page > 1;
  }, [page]);

  const nextPage = useCallback(() => {
    setPageState((p) => p + 1);
  }, []);

  const prevPage = useCallback(() => {
    setPageState((p) => Math.max(1, p - 1));
  }, []);

  return {
    // State
    page,
    pageSize,
    offset,

    // API helpers
    getApiParams,
    getTotalPages,

    // Setters
    setPage,
    setPageSize,

    // Pagination component handlers
    onPageChange,
    onLimitChange,

    // Utilities
    reset,
    goToFirst,
    goToLast,
    hasNextPage,
    hasPrevPage,
    nextPage,
    prevPage,

    // Options
    pageSizeOptions,
  };
}
