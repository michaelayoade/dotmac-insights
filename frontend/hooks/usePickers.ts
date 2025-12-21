/**
 * Picker Hooks - Centralized data fetching for picker/selector components
 *
 * These hooks provide easy access to common entity lists used in dropdowns,
 * with caching via SWR and standardized error handling.
 */

import useSWR from 'swr';
import { fetchApi } from '@/lib/api/core';

// =============================================================================
// TYPES
// =============================================================================

export interface TeamOption {
  id: number;
  name: string;
  description?: string;
  domain?: string;
  is_active?: boolean;
}

export interface EmployeeOption {
  id: number;
  name: string;
  email?: string;
  department?: string;
  designation?: string;
  status?: string;
}

export interface VehicleOption {
  id: number;
  license_plate: string;
  make?: string;
  model?: string;
  driver_name?: string;
  is_active?: boolean;
}

export interface AssetOption {
  id: number;
  asset_name: string;
  asset_code?: string;
  asset_category?: string;
  location?: string;
  status?: string;
}

// =============================================================================
// HOOKS
// =============================================================================

/**
 * Fetch all teams (combines support teams and field teams)
 */
export function useTeamOptions() {
  const { data, error, isLoading, mutate } = useSWR<{ teams: TeamOption[] }>(
    '/admin/teams',
    () => fetchApi<{ teams: TeamOption[] }>('/admin/teams'),
    {
      revalidateOnFocus: false,
      dedupingInterval: 30000, // 30 seconds cache
    }
  );

  return {
    teams: data?.teams || [],
    isLoading,
    error,
    refresh: mutate,
  };
}

/**
 * Fetch all active employees for picker
 */
export function useEmployeeOptions(filter?: { department?: string; status?: string }) {
  const params = new URLSearchParams();
  if (filter?.department) params.set('department', filter.department);
  if (filter?.status) params.set('status', filter.status);
  params.set('limit', '500'); // Get all for picker

  const queryString = params.toString();
  const url = `/hr/employees${queryString ? `?${queryString}` : ''}`;

  const { data, error, isLoading, mutate } = useSWR<{ items: EmployeeOption[] }>(
    url,
    () => fetchApi<{ items: EmployeeOption[] }>(url),
    {
      revalidateOnFocus: false,
      dedupingInterval: 30000,
    }
  );

  return {
    employees: data?.items || [],
    isLoading,
    error,
    refresh: mutate,
  };
}

/**
 * Fetch all active vehicles for picker
 */
export function useVehicleOptions(filter?: { is_active?: boolean }) {
  const params = new URLSearchParams();
  if (filter?.is_active !== undefined) {
    params.set('is_active', String(filter.is_active));
  }
  params.set('page_size', '500'); // Get all for picker

  const queryString = params.toString();
  const url = `/v1/vehicles${queryString ? `?${queryString}` : ''}`;

  const { data, error, isLoading, mutate } = useSWR<{ items: VehicleOption[] }>(
    url,
    () => fetchApi<{ items: VehicleOption[] }>(url),
    {
      revalidateOnFocus: false,
      dedupingInterval: 30000,
    }
  );

  return {
    vehicles: data?.items || [],
    isLoading,
    error,
    refresh: mutate,
  };
}

/**
 * Fetch all assets for picker
 */
export function useAssetOptions(filter?: { category?: string; status?: string }) {
  const params = new URLSearchParams();
  if (filter?.category) params.set('category', filter.category);
  if (filter?.status) params.set('status', filter.status);
  params.set('limit', '500'); // Get all for picker

  const queryString = params.toString();
  const url = `/assets${queryString ? `?${queryString}` : ''}`;

  const { data, error, isLoading, mutate } = useSWR<{ items: AssetOption[] }>(
    url,
    () => fetchApi<{ items: AssetOption[] }>(url),
    {
      revalidateOnFocus: false,
      dedupingInterval: 30000,
    }
  );

  return {
    assets: data?.items || [],
    isLoading,
    error,
    refresh: mutate,
  };
}

/**
 * Fetch support teams specifically
 */
export function useSupportTeamOptions() {
  const { data, error, isLoading, mutate } = useSWR<{ teams: TeamOption[] }>(
    '/support/teams',
    () => fetchApi<{ teams: TeamOption[] }>('/support/teams'),
    {
      revalidateOnFocus: false,
      dedupingInterval: 30000,
    }
  );

  return {
    teams: data?.teams || [],
    isLoading,
    error,
    refresh: mutate,
  };
}

/**
 * Fetch field service teams specifically
 */
export function useFieldTeamOptions() {
  const { data, error, isLoading, mutate } = useSWR<{ data: TeamOption[] }>(
    '/field-service/teams',
    () => fetchApi<{ data: TeamOption[] }>('/field-service/teams'),
    {
      revalidateOnFocus: false,
      dedupingInterval: 30000,
    }
  );

  return {
    teams: data?.data || [],
    isLoading,
    error,
    refresh: mutate,
  };
}
