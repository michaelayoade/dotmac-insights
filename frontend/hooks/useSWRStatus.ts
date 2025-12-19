/**
 * Aggregate SWR state from multiple hooks
 * Simplifies loading/error handling across dashboards
 */

import { SWRResponse } from 'swr';

export interface SWRStatusResult {
  isLoading: boolean;
  error: Error | undefined;
  retry: () => void;
}

/**
 * Combines status from multiple SWR responses into a single state object
 *
 * @example
 * const customers = useCustomers();
 * const orders = useOrders();
 * const analytics = useAnalytics();
 *
 * const { isLoading, error, retry } = useSWRStatus(customers, orders, analytics);
 *
 * if (isLoading) return <LoadingState />;
 * if (error) return <ErrorDisplay error={error} onRetry={retry} />;
 */
export function useSWRStatus(
  ...responses: SWRResponse<unknown, unknown>[]
): SWRStatusResult {
  const isLoading = responses.some((r) => r.isLoading);
  const error = responses.find((r) => r.error)?.error as Error | undefined;

  const retry = () => {
    responses.forEach((r) => {
      if (r.mutate) {
        r.mutate();
      }
    });
  };

  return { isLoading, error, retry };
}

/**
 * Alternative interface for use with destructured SWR state arrays
 * Used when you have pre-collected SWR states (like the existing swrStates pattern)
 *
 * @example
 * const swrStates = [
 *   { data: customers.data, isLoading: customers.isLoading, error: customers.error },
 *   { data: orders.data, isLoading: orders.isLoading, error: orders.error },
 * ];
 *
 * const { isLoading, error } = useSWRStatusFromArray(swrStates);
 */
export function useSWRStatusFromArray(
  states: Array<{ isLoading?: boolean; error?: Error | unknown }>
): Omit<SWRStatusResult, 'retry'> {
  const isLoading = states.some((s) => s.isLoading);
  const error = states.find((s) => s.error)?.error as Error | undefined;

  return { isLoading, error };
}
