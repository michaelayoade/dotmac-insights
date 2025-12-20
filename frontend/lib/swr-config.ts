/**
 * SWR Configuration Presets
 *
 * Standardized SWR configurations for different data access patterns.
 * Use these presets to ensure consistent caching behavior across the app.
 */

import { SWRConfiguration } from 'swr';

/**
 * REALTIME_CONFIG
 *
 * For frequently-changing data that users expect to be fresh.
 * Examples: dashboards, sync status, live metrics, notifications
 *
 * - Refreshes every 30 seconds
 * - Short deduping interval (5s)
 * - Revalidates when user returns to tab
 */
export const REALTIME_CONFIG: SWRConfiguration = {
  refreshInterval: 30000,
  dedupingInterval: 5000,
  revalidateOnFocus: true,
  revalidateOnReconnect: true,
};

/**
 * STANDARD_CONFIG
 *
 * For moderately-changing data like lists and reports.
 * Examples: customer lists, invoice lists, reports, analytics
 *
 * - Refreshes every 60 seconds
 * - Moderate deduping interval (30s)
 * - Does not revalidate on focus (reduces unnecessary requests)
 */
export const STANDARD_CONFIG: SWRConfiguration = {
  refreshInterval: 60000,
  dedupingInterval: 30000,
  revalidateOnFocus: false,
  revalidateOnReconnect: true,
};

/**
 * STATIC_CONFIG
 *
 * For rarely-changing data like settings and configurations.
 * Examples: user settings, company profile, tax rates, chart of accounts
 *
 * - No automatic refresh
 * - Long deduping interval (5 minutes)
 * - Does not revalidate on focus
 */
export const STATIC_CONFIG: SWRConfiguration = {
  refreshInterval: 0,
  dedupingInterval: 300000,
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
  revalidateIfStale: false,
};

/**
 * ON_DEMAND_CONFIG
 *
 * For user-triggered data that shouldn't auto-refresh.
 * Examples: search results, filtered lists, form lookups
 *
 * - No automatic refresh
 * - Short deduping interval (1s)
 * - Does not revalidate on focus
 */
export const ON_DEMAND_CONFIG: SWRConfiguration = {
  refreshInterval: 0,
  dedupingInterval: 1000,
  revalidateOnFocus: false,
  revalidateOnReconnect: false,
  revalidateIfStale: false,
};

/**
 * DETAIL_CONFIG
 *
 * For detail views that may be edited by the user.
 * Examples: invoice detail, customer detail, ticket detail
 *
 * - No automatic refresh (user controls when to reload)
 * - Moderate deduping interval (30s)
 * - Revalidates on focus (catch updates from other tabs)
 */
export const DETAIL_CONFIG: SWRConfiguration = {
  refreshInterval: 0,
  dedupingInterval: 30000,
  revalidateOnFocus: true,
  revalidateOnReconnect: true,
};

/**
 * SYNC_CONFIG
 *
 * For sync status and background job monitoring.
 * Examples: sync status, task progress, job queues
 *
 * - Refreshes every 10 seconds
 * - Short deduping interval (5s)
 * - Does not revalidate on focus (already refreshing frequently)
 */
export const SYNC_CONFIG: SWRConfiguration = {
  refreshInterval: 10000,
  dedupingInterval: 5000,
  revalidateOnFocus: false,
  revalidateOnReconnect: true,
};

/**
 * Helper to create a paused SWR config based on authentication state.
 * Use this to prevent requests before auth is confirmed.
 *
 * @param isAuthenticated - Whether the user is authenticated
 * @param baseConfig - The base SWR configuration to extend
 * @returns SWR configuration with isPaused set appropriately
 */
export function createAuthGuardedConfig(
  isAuthenticated: boolean,
  baseConfig: SWRConfiguration = {}
): SWRConfiguration {
  return {
    ...baseConfig,
    isPaused: () => !isAuthenticated,
  };
}

/**
 * Helper to merge a preset with custom overrides.
 *
 * @param preset - The base preset configuration
 * @param overrides - Custom overrides to apply
 * @returns Merged SWR configuration
 */
export function withOverrides(
  preset: SWRConfiguration,
  overrides: SWRConfiguration
): SWRConfiguration {
  return { ...preset, ...overrides };
}
