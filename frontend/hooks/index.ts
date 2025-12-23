/**
 * Central hooks export
 *
 * Import commonly used hooks from this file:
 * import { useTableSort, usePeriodFilter, useSearchFilter, usePagination, useListPage } from '@/hooks';
 */

// Pagination
export {
  usePagination,
  type UsePaginationOptions,
  type UsePaginationReturn,
} from './usePagination';

// List page composite hook (combines pagination, filters, sorting)
export {
  useListPage,
  type UseListPageOptions,
  type UseListPageReturn,
  type FilterConfig,
  type FilterState,
  type SortOrder,
} from './useListPage';

// Table utilities
export { useTableSort, type UseTableSortReturn } from './useTableSort';

// Filter hooks
export {
  usePeriodFilter,
  useSearchFilter,
  useStatusFilter,
  useFilters,
  DAY_PERIOD_OPTIONS,
  MONTH_PERIOD_OPTIONS,
  type PeriodOption,
  type StatusOption,
  type UsePeriodFilterReturn,
  type UseSearchFilterReturn,
  type UseStatusFilterReturn,
  type UseFiltersReturn,
} from './useFilters';

// Picker hooks (data fetching for dropdowns)
export {
  useTeamOptions,
  useEmployeeOptions,
  useVehicleOptions,
  useAssetOptions,
  useSupportTeamOptions,
  useFieldTeamOptions,
} from './usePickers';

// Form utilities
export {
  useFormErrors,
  validateForm,
  commonRules,
  type FieldErrors,
  type ValidationRule,
  type ValidationRules,
} from './useFormErrors';

// Common utilities
export { useDebounce } from './useDebounce';
export { usePersistentState } from './usePersistentState';
export { useKeyboardShortcut } from './useKeyboardShortcut';
export { useErrorHandler } from './useErrorHandler';
export { useSWRStatus } from './useSWRStatus';

// Domain-specific hooks should be imported directly:
// import { useExpenses } from '@/hooks/useExpenses';
// import { useInbox } from '@/hooks/useInbox';
// import { usePerformance } from '@/hooks/usePerformance';
