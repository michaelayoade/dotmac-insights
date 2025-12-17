import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Hook that returns a debounced version of the provided value.
 * Useful for delaying API calls until user stops typing.
 *
 * @example
 * const [search, setSearch] = useState('');
 * const debouncedSearch = useDebounce(search, 300);
 *
 * useEffect(() => {
 *   if (debouncedSearch) {
 *     fetchResults(debouncedSearch);
 *   }
 * }, [debouncedSearch]);
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}

/**
 * Hook that returns a debounced callback function.
 * The callback will only execute after the specified delay has passed
 * since the last invocation.
 *
 * @example
 * const debouncedSave = useDebouncedCallback(
 *   (value: string) => saveToServer(value),
 *   500
 * );
 */
export function useDebouncedCallback<T extends (...args: unknown[]) => unknown>(
  callback: T,
  delay: number
): (...args: Parameters<T>) => void {
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const callbackRef = useRef(callback);

  // Keep callback ref updated
  useEffect(() => {
    callbackRef.current = callback;
  }, [callback]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return useCallback(
    (...args: Parameters<T>) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      timeoutRef.current = setTimeout(() => {
        callbackRef.current(...args);
      }, delay);
    },
    [delay]
  );
}

/**
 * Hook that provides both immediate and debounced values.
 * Useful when you need to show immediate feedback while debouncing API calls.
 *
 * @example
 * const { value, debouncedValue, setValue } = useDebouncedState('', 300);
 * // value updates immediately for UI
 * // debouncedValue updates after delay for API calls
 */
export function useDebouncedState<T>(
  initialValue: T,
  delay: number
): {
  value: T;
  debouncedValue: T;
  setValue: (value: T) => void;
} {
  const [value, setValue] = useState<T>(initialValue);
  const debouncedValue = useDebounce(value, delay);

  return { value, debouncedValue, setValue };
}

export default useDebounce;
