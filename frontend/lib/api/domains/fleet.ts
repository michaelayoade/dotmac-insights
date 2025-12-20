/**
 * Fleet Management API
 *
 * Provides endpoints for managing fleet vehicles, driver assignments,
 * insurance tracking, and vehicle lifecycle management.
 */

import { fetchApi } from '../core';

// =============================================================================
// TYPES
// =============================================================================

export interface Vehicle {
  id: number;
  erpnext_id: string | null;
  license_plate: string;
  make: string | null;
  model: string | null;
  model_year: number | null;
  chassis_no: string | null;
  color: string | null;
  doors: number | null;
  wheels: number | null;
  vehicle_value: number;
  acquisition_date: string | null;
  fuel_type: string | null;
  fuel_uom: string | null;
  odometer_value: number;
  last_odometer_date: string | null;
  uom: string | null;
  insurance_company: string | null;
  policy_no: string | null;
  insurance_start_date: string | null;
  insurance_end_date: string | null;
  employee: string | null;
  employee_id: number | null;
  driver_name: string | null;
  location: string | null;
  company: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface VehicleListResponse {
  items: Vehicle[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface VehicleSummary {
  total_vehicles: number;
  active_vehicles: number;
  inactive_vehicles: number;
  by_fuel_type: Record<string, number>;
  by_make: Record<string, number>;
  insurance_expiring_soon: number;
  total_value: number;
  avg_odometer: number;
}

export interface VehicleUpdatePayload {
  license_plate?: string;
  make?: string;
  model?: string;
  model_year?: number | null;
  color?: string;
  odometer_value?: number;
  acquisition_date?: string | null;
  fuel_uom?: string | null;
  location?: string;
  company?: string | null;
  employee_id?: number | null;
  is_active?: boolean;
  insurance_company?: string;
  policy_no?: string;
  insurance_start_date?: string;
  insurance_end_date?: string;
}

export interface VehicleListParams {
  page?: number;
  page_size?: number;
  search?: string;
  make?: string;
  model?: string;
  fuel_type?: string;
  employee_id?: number;
  is_active?: boolean;
  sort_by?: 'license_plate' | 'make' | 'model' | 'acquisition_date' | 'vehicle_value' | 'odometer_value';
  sort_order?: 'asc' | 'desc';
}

// =============================================================================
// API
// =============================================================================

export const fleetApi = {
  // List vehicles with filtering and pagination
  getVehicles: (params?: VehicleListParams) =>
    fetchApi<VehicleListResponse>('/v1/vehicles', { params }),

  // Get fleet summary statistics
  getVehicleSummary: () =>
    fetchApi<VehicleSummary>('/v1/vehicles/summary'),

  // Get single vehicle by ID
  getVehicle: (id: number | string) =>
    fetchApi<Vehicle>(`/v1/vehicles/${id}`),

  // Update vehicle
  updateVehicle: (id: number | string, body: VehicleUpdatePayload) =>
    fetchApi<Vehicle>(`/v1/vehicles/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  // Get vehicles with expiring insurance
  getVehiclesInsuranceExpiring: (days = 30) =>
    fetchApi<Vehicle[]>('/v1/vehicles/insurance/expiring', { params: { days } }),

  // Get all distinct vehicle makes
  getVehicleMakes: () =>
    fetchApi<string[]>('/v1/vehicles/makes'),

  // Get all distinct fuel types
  getFuelTypes: () =>
    fetchApi<string[]>('/v1/vehicles/fuel-types'),

  // Get vehicles by driver
  getVehiclesByDriver: (employeeId: number) =>
    fetchApi<Vehicle[]>(`/v1/vehicles/by-driver/${employeeId}`),
};
