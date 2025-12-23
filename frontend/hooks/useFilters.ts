import { useState, useCallback, useMemo, useEffect } from 'react';

// =============================================================================
// PERIOD FILTER HOOK
// =============================================================================

export type PeriodUnit = 'days' | 'months';

export interface PeriodOption {
  value: string;
  label: string;
}

export interface UsePeriodFilterOptions {
  /** Initial period value */
  defaultValue?: number;
  /** Period unit (days or months) */
  unit?: PeriodUnit;
  /** Custom options array */
  options?: PeriodOption[];
}

export interface UsePeriodFilterReturn {
  /** Current period value */
  value: number;
  /** Set period value */
  setValue: (val: number) => void;
  /** Options array for Select component */
  options: PeriodOption[];
  /** String value for Select component */
  stringValue: string;
  /** Handler for Select onChange (converts string to number) */
  onChange: (val: string) => void;
}

/** Default day period options */
export const DAY_PERIOD_OPTIONS: PeriodOption[] = [
  { value: '7', label: 'Last 7 days' },
  { value: '14', label: 'Last 14 days' },
  { value: '30', label: 'Last 30 days' },
  { value: '60', label: 'Last 60 days' },
  { value: '90', label: 'Last 90 days' },
];

/** Default month period options */
export const MONTH_PERIOD_OPTIONS: PeriodOption[] = [
  { value: '1', label: 'Last month' },
  { value: '3', label: 'Last 3 months' },
  { value: '6', label: 'Last 6 months' },
  { value: '12', label: 'Last 12 months' },
];

/**
 * Hook for managing period/time range filter state.
 *
 * @example
 * const { value, options, stringValue, onChange } = usePeriodFilter({ defaultValue: 30 });
 * <Select value={stringValue} onChange={onChange} options={options} />
 */
export function usePeriodFilter(opts: UsePeriodFilterOptions = {}): UsePeriodFilterReturn {
  const { defaultValue = 7, unit = 'days', options } = opts;

  const [value, setValue] = useState(defaultValue);

  const periodOptions = useMemo(() => {
    if (options) return options;
    return unit === 'months' ? MONTH_PERIOD_OPTIONS : DAY_PERIOD_OPTIONS;
  }, [options, unit]);

  const onChange = useCallback((val: string) => {
    setValue(Number(val));
  }, []);

  return {
    value,
    setValue,
    options: periodOptions,
    stringValue: String(value),
    onChange,
  };
}

// =============================================================================
// SEARCH FILTER HOOK
// =============================================================================

export interface UseSearchFilterOptions {
  /** Initial search value */
  defaultValue?: string;
  /** Callback when search changes (for API refetch) */
  onSearch?: (value: string) => void;
  /** Use form submission pattern (Enter key to search) */
  useFormSubmit?: boolean;
}

export interface UseSearchFilterReturn {
  /** Current search value (for display) */
  inputValue: string;
  /** Committed search value (for API queries) */
  searchValue: string;
  /** Update input value */
  setInputValue: (val: string) => void;
  /** Commit search (for form submit pattern) */
  commitSearch: () => void;
  /** Clear search */
  clear: () => void;
  /** Handler for input onChange */
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  /** Handler for form onSubmit */
  onSubmit: (e: React.FormEvent) => void;
  /** Whether there's an active search */
  hasSearch: boolean;
}

/**
 * Hook for managing search filter state.
 *
 * @example
 * // Immediate search (onChange triggers API)
 * const { inputValue, searchValue, onChange } = useSearchFilter();
 *
 * // Form submit pattern (Enter key triggers API)
 * const { inputValue, onChange, onSubmit } = useSearchFilter({ useFormSubmit: true });
 */
export function useSearchFilter(opts: UseSearchFilterOptions = {}): UseSearchFilterReturn {
  const { defaultValue = '', onSearch, useFormSubmit = false } = opts;

  const [inputValue, setInputValue] = useState(defaultValue);
  const [searchValue, setSearchValue] = useState(defaultValue);

  const commitSearch = useCallback(() => {
    setSearchValue(inputValue);
    onSearch?.(inputValue);
  }, [inputValue, onSearch]);

  const onChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value;
      setInputValue(val);
      if (!useFormSubmit) {
        setSearchValue(val);
        onSearch?.(val);
      }
    },
    [useFormSubmit, onSearch]
  );

  const onSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      commitSearch();
    },
    [commitSearch]
  );

  const clear = useCallback(() => {
    setInputValue('');
    setSearchValue('');
    onSearch?.('');
  }, [onSearch]);

  return {
    inputValue,
    searchValue,
    setInputValue,
    commitSearch,
    clear,
    onChange,
    onSubmit,
    hasSearch: searchValue.length > 0,
  };
}

// =============================================================================
// STATUS FILTER HOOK
// =============================================================================

export interface StatusOption {
  value: string;
  label: string;
}

export interface UseStatusFilterOptions<T extends string = string> {
  /** Initial status value (empty string = all) */
  defaultValue?: T | '';
  /** Available status options */
  options: StatusOption[];
  /** Label for "all" option */
  allLabel?: string;
}

export interface UseStatusFilterReturn<T extends string = string> {
  /** Current status value */
  value: T | '';
  /** Set status value */
  setValue: (val: T | '') => void;
  /** Options array including "All" option */
  options: StatusOption[];
  /** Handler for Select onChange */
  onChange: (val: string) => void;
  /** Whether a status is actively filtered */
  hasFilter: boolean;
  /** Clear filter (set to all) */
  clear: () => void;
}

/**
 * Hook for managing status filter state.
 *
 * @example
 * const STATUS_OPTIONS = [
 *   { value: 'active', label: 'Active' },
 *   { value: 'inactive', label: 'Inactive' },
 * ];
 * const { value, options, onChange } = useStatusFilter({ options: STATUS_OPTIONS });
 */
export function useStatusFilter<T extends string = string>(
  opts: UseStatusFilterOptions<T>
): UseStatusFilterReturn<T> {
  const { defaultValue = '', options, allLabel = 'All' } = opts;

  const [value, setValue] = useState<T | ''>(defaultValue);

  const optionsWithAll = useMemo(
    () => [{ value: '', label: allLabel }, ...options],
    [options, allLabel]
  );

  const onChange = useCallback((val: string) => {
    setValue(val as T | '');
  }, []);

  const clear = useCallback(() => {
    setValue('');
  }, []);

  return {
    value,
    setValue,
    options: optionsWithAll,
    onChange,
    hasFilter: value !== '',
    clear,
  };
}

// =============================================================================
// COMBINED FILTERS HOOK
// =============================================================================

export interface FilterState {
  search: string;
  status: string;
  period: number;
  [key: string]: string | number;
}

export interface UseFiltersOptions {
  /** Initial filter values */
  defaultValues?: Partial<FilterState>;
  /** Callback when any filter changes */
  onFilterChange?: (filters: FilterState) => void;
}

export interface UseFiltersReturn {
  /** Current filter state */
  filters: FilterState;
  /** Update a single filter */
  setFilter: <K extends keyof FilterState>(key: K, value: FilterState[K]) => void;
  /** Reset all filters to defaults */
  resetFilters: () => void;
  /** Whether any filters are active */
  hasActiveFilters: boolean;
}

const DEFAULT_FILTERS: FilterState = {
  search: '',
  status: '',
  period: 30,
};

/**
 * Combined hook for managing multiple filters together.
 *
 * @example
 * const { filters, setFilter, resetFilters, hasActiveFilters } = useFilters();
 */
export function useFilters(opts: UseFiltersOptions = {}): UseFiltersReturn {
  const { defaultValues = {}, onFilterChange } = opts;

  const initialFilters = useMemo<FilterState>(() => {
    const merged: FilterState = { ...DEFAULT_FILTERS };
    Object.entries(defaultValues).forEach(([key, value]) => {
      if (value !== undefined) {
        merged[key] = value as FilterState[keyof FilterState];
      }
    });
    return merged;
  }, [defaultValues]);

  const [filters, setFilters] = useState<FilterState>(initialFilters);

  useEffect(() => {
    setFilters(initialFilters);
  }, [initialFilters]);

  const setFilter = useCallback(
    <K extends keyof FilterState>(key: K, value: FilterState[K]) => {
      setFilters((prev) => {
        const next = { ...prev, [key]: value };
        onFilterChange?.(next);
        return next;
      });
    },
    [onFilterChange]
  );

  const resetFilters = useCallback(() => {
    setFilters(initialFilters);
    onFilterChange?.(initialFilters);
  }, [initialFilters, onFilterChange]);

  const hasActiveFilters = useMemo(() => {
    return Object.keys(filters).some((key) => {
      const typedKey = key as keyof FilterState;
      return filters[typedKey] !== initialFilters[typedKey];
    });
  }, [filters, initialFilters]);

  return {
    filters,
    setFilter,
    resetFilters,
    hasActiveFilters,
  };
}
