/**
 * Custom render utility for testing React components
 *
 * Wraps components with necessary providers (QueryClient, etc.)
 * to ensure tests have access to the same context as the app.
 */
import React, { ReactElement } from 'react';
import { render, RenderOptions, RenderResult } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// =============================================================================
// TEST QUERY CLIENT
// =============================================================================

/**
 * Create a fresh QueryClient for testing.
 * Disables retries and caching for predictable test behavior.
 */
function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
        staleTime: 0,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

// =============================================================================
// CUSTOM RENDER OPTIONS
// =============================================================================

interface CustomRenderOptions extends Omit<RenderOptions, 'wrapper'> {
  /**
   * Custom QueryClient instance. If not provided, a fresh one is created.
   */
  queryClient?: QueryClient;
  /**
   * Initial route for testing navigation (requires router mock setup)
   */
  route?: string;
}

// =============================================================================
// ALL PROVIDERS WRAPPER
// =============================================================================

interface AllProvidersProps {
  children: React.ReactNode;
  queryClient: QueryClient;
}

function AllProviders({ children, queryClient }: AllProvidersProps): JSX.Element {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}

// =============================================================================
// CUSTOM RENDER FUNCTION
// =============================================================================

/**
 * Custom render function that wraps components with all necessary providers.
 *
 * @example
 * ```tsx
 * import { render, screen } from '@/tests/utils/render';
 *
 * test('renders component', () => {
 *   render(<MyComponent />);
 *   expect(screen.getByText('Hello')).toBeInTheDocument();
 * });
 * ```
 */
function customRender(
  ui: ReactElement,
  options: CustomRenderOptions = {}
): RenderResult {
  const { queryClient = createTestQueryClient(), ...renderOptions } = options;

  function Wrapper({ children }: { children: React.ReactNode }): JSX.Element {
    return <AllProviders queryClient={queryClient}>{children}</AllProviders>;
  }

  return render(ui, { wrapper: Wrapper, ...renderOptions });
}

// =============================================================================
// EXPORTS
// =============================================================================

// Re-export everything from @testing-library/react
export * from '@testing-library/react';

// Export userEvent for interaction testing
export { default as userEvent } from '@testing-library/user-event';

// Override render with our custom version
export { customRender as render };

// Export utility functions
export { createTestQueryClient };

// =============================================================================
// TEST HELPERS
// =============================================================================

/**
 * Wait for a condition to be true.
 * Useful for waiting for async operations in tests.
 */
export async function waitForCondition(
  condition: () => boolean,
  timeout = 5000,
  interval = 100
): Promise<void> {
  const startTime = Date.now();
  while (!condition()) {
    if (Date.now() - startTime > timeout) {
      throw new Error(`Condition not met within ${timeout}ms`);
    }
    await new Promise((resolve) => setTimeout(resolve, interval));
  }
}

/**
 * Create a deferred promise for testing async behavior.
 */
export function createDeferred<T>(): {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
} {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

/**
 * Mock a successful API response.
 */
export function mockApiSuccess<T>(data: T): Promise<{ data: T }> {
  return Promise.resolve({ data });
}

/**
 * Mock a failed API response.
 */
export function mockApiError(message: string, status = 400): Promise<never> {
  const error = new Error(message) as Error & { status: number };
  error.status = status;
  return Promise.reject(error);
}
