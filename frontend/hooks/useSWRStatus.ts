/**
 * Aggregate SWR state from multiple hooks
 * Simplifies loading/error handling across dashboards
 */

import { SWRResponse } from 'swr';

export interface SWRStatusResult {
  /** True if any hook is in initial loading state */
  isLoading: boolean;
  /** True if any hook is revalidating (background refresh) */
  isValidating: boolean;
  /** First error encountered, if any */
  error: Error | undefined;
  /** True if all hooks have returned data */
  hasData: boolean;
  /** True if all data arrays/objects are empty */
  isEmpty: boolean;
  /** Retry all hooks */
  retry: () => void;
  /** Retry only hooks that have errors */
  retryFailed: () => void;
}

/**
 * Check if a data value is "empty"
 */
function isDataEmpty(data: unknown): boolean {
  if (data === undefined || data === null) return true;
  if (Array.isArray(data)) return data.length === 0;
  if (typeof data === 'object') {
    // Check for common response patterns
    const obj = data as Record<string, unknown>;
    if ('items' in obj && Array.isArray(obj.items)) return obj.items.length === 0;
    if ('data' in obj && Array.isArray(obj.data)) return obj.data.length === 0;
    if ('results' in obj && Array.isArray(obj.results)) return obj.results.length === 0;
    // Empty object
    return Object.keys(obj).length === 0;
  }
  return false;
}

/**
 * Combines status from multiple SWR responses into a single state object
 *
 * @example
 * const customers = useCustomers();
 * const orders = useOrders();
 * const analytics = useAnalytics();
 *
 * const { isLoading, error, retry, hasData, isEmpty } = useSWRStatus(customers, orders, analytics);
 *
 * if (isLoading) return <LoadingState />;
 * if (error) return <ErrorDisplay error={error} onRetry={retry} />;
 * if (isEmpty) return <EmptyState />;
 */
export function useSWRStatus(
  ...responses: SWRResponse<unknown, unknown>[]
): SWRStatusResult {
  const isLoading = responses.some((r) => r.isLoading);
  const isValidating = responses.some((r) => r.isValidating);
  const error = responses.find((r) => r.error)?.error as Error | undefined;
  const hasData = responses.every((r) => r.data !== undefined);
  const isEmpty = hasData && responses.every((r) => isDataEmpty(r.data));

  const retry = () => {
    responses.forEach((r) => {
      if (r.mutate) {
        r.mutate();
      }
    });
  };

  const retryFailed = () => {
    responses
      .filter((r) => r.error)
      .forEach((r) => {
        if (r.mutate) {
          r.mutate();
        }
      });
  };

  return { isLoading, isValidating, error, hasData, isEmpty, retry, retryFailed };
}

/**
 * Alternative interface for use with destructured SWR state arrays
 * Used when you have pre-collected SWR states (like the existing swrStates pattern)
 *
 * @example
 * const swrStates = [
 *   { data: customers.data, isLoading: customers.isLoading, error: customers.error, mutate: customers.mutate },
 *   { data: orders.data, isLoading: orders.isLoading, error: orders.error, mutate: orders.mutate },
 * ];
 *
 * const { isLoading, error, retry } = useSWRStatusFromArray(swrStates);
 */
export interface SWRStateItem {
  data?: unknown;
  isLoading?: boolean;
  isValidating?: boolean;
  error?: Error | unknown;
  mutate?: () => void;
}

export function useSWRStatusFromArray(states: SWRStateItem[]): SWRStatusResult {
  const isLoading = states.some((s) => s.isLoading);
  const isValidating = states.some((s) => s.isValidating);
  const error = states.find((s) => s.error)?.error as Error | undefined;
  const hasData = states.every((s) => s.data !== undefined);
  const isEmpty = hasData && states.every((s) => isDataEmpty(s.data));

  const retry = () => {
    states.forEach((s) => {
      if (s.mutate) {
        s.mutate();
      }
    });
  };

  const retryFailed = () => {
    states
      .filter((s) => s.error)
      .forEach((s) => {
        if (s.mutate) {
          s.mutate();
        }
      });
  };

  return { isLoading, isValidating, error, hasData, isEmpty, retry, retryFailed };
}
