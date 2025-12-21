/**
 * Assets Domain API
 * Includes: Fixed Assets, Categories, Depreciation, Maintenance, Warranty, Insurance
 */

import { fetchApi } from '../core';

// =============================================================================
// TYPES
// =============================================================================

// Asset Types
export interface Asset {
  id: number;
  erpnext_id?: string | null;
  asset_name: string;
  asset_category?: string | null;
  item_code?: string | null;
  item_name?: string | null;
  company?: string | null;
  location?: string | null;
  custodian?: string | null;
  department?: string | null;
  cost_center?: string | null;
  purchase_date?: string | null;
  gross_purchase_amount: number;
  asset_value: number;
  opening_accumulated_depreciation: number;
  status?: string | null;
  serial_no?: string | null;
  maintenance_required: boolean;
  warranty_expiry_date?: string | null;
  insured_value: number;
  created_at?: string | null;
}

export interface AssetListResponse {
  total: number;
  limit: number;
  offset: number;
  assets: Asset[];
}

export interface AssetFinanceBook {
  id: number;
  finance_book?: string | null;
  depreciation_method?: string | null;
  total_number_of_depreciations: number;
  frequency_of_depreciation: number;
  depreciation_start_date?: string | null;
  expected_value_after_useful_life: number;
  value_after_depreciation: number;
  daily_depreciation_amount: number;
  rate_of_depreciation: number;
}

export interface AssetDepreciationScheduleItem {
  id: number;
  finance_book?: string | null;
  schedule_date?: string | null;
  depreciation_amount: number;
  accumulated_depreciation_amount: number;
  journal_entry?: string | null;
  depreciation_booked: boolean;
}

export interface AssetDetail extends Asset {
  available_for_use_date?: string | null;
  supplier?: string | null;
  purchase_receipt?: string | null;
  purchase_invoice?: string | null;
  asset_quantity: number;
  docstatus: number;
  calculate_depreciation: boolean;
  is_existing_asset: boolean;
  is_composite_asset: boolean;
  next_depreciation_date?: string | null;
  disposal_date?: string | null;
  journal_entry_for_scrap?: string | null;
  insurance_start_date?: string | null;
  insurance_end_date?: string | null;
  comprehensive_insurance?: string | null;
  asset_owner?: string | null;
  description?: string | null;
  updated_at?: string | null;
  finance_books: AssetFinanceBook[];
  depreciation_schedules: AssetDepreciationScheduleItem[];
}

export interface AssetCreatePayload {
  asset_name: string;
  asset_category?: string;
  item_code?: string;
  item_name?: string;
  company?: string;
  location?: string;
  custodian?: string;
  department?: string;
  cost_center?: string;
  purchase_date?: string;
  available_for_use_date?: string;
  gross_purchase_amount?: number;
  supplier?: string;
  asset_quantity?: number;
  calculate_depreciation?: boolean;
  description?: string;
  serial_no?: string;
  finance_books?: Array<{
    finance_book?: string;
    depreciation_method?: string;
    total_number_of_depreciations?: number;
    frequency_of_depreciation?: number;
    depreciation_start_date?: string;
    expected_value_after_useful_life?: number;
    rate_of_depreciation?: number;
  }>;
}

export interface AssetUpdatePayload {
  asset_name?: string;
  asset_category?: string;
  location?: string;
  custodian?: string;
  department?: string;
  cost_center?: string;
  maintenance_required?: boolean;
  description?: string;
  insured_value?: number;
  insurance_start_date?: string;
  insurance_end_date?: string;
}

export interface AssetSummaryResponse {
  totals: {
    count: number;
    book_value: number;
    purchase_value: number;
    accumulated_depreciation: number;
    pending_entries?: number;
    disposed_count?: number;
  };
  by_status: Array<{
    status: string;
    count: number;
    total_value: number;
    purchase_value: number;
  }>;
  by_category: Array<{
    category: string;
    count: number;
    total_value: number;
  }>;
  by_location: Array<{
    location: string;
    count: number;
    total_value: number;
  }>;
  maintenance_required: number;
  warranty_expiring_soon: number;
  insurance_expiring_soon?: number;
  expiring_warranty_assets?: WarrantyExpiringAsset[];
  expiring_insurance_assets?: InsuranceExpiringAsset[];
}

// Asset Category Types
export interface AssetCategory {
  id: number;
  erpnext_id?: string | null;
  asset_category_name: string;
  enable_cwip_accounting: boolean;
  finance_books: Array<{
    finance_book?: string | null;
    depreciation_method?: string | null;
    total_number_of_depreciations: number;
    frequency_of_depreciation: number;
    fixed_asset_account?: string | null;
    accumulated_depreciation_account?: string | null;
    depreciation_expense_account?: string | null;
  }>;
}

export interface AssetCategoryListResponse {
  total: number;
  categories: AssetCategory[];
}

export interface AssetCategoryCreatePayload {
  asset_category_name: string;
  enable_cwip_accounting?: boolean;
}

// Depreciation Types
export interface DepreciationScheduleEntry {
  id: number;
  asset_id: number;
  asset_name?: string | null;
  finance_book?: string | null;
  schedule_date?: string | null;
  depreciation_amount: number;
  accumulated_depreciation_amount: number;
  journal_entry?: string | null;
  depreciation_booked: boolean;
}

export interface DepreciationScheduleListResponse {
  total: number;
  limit: number;
  offset: number;
  schedules: DepreciationScheduleEntry[];
}

export interface PendingDepreciationEntry {
  id: number;
  asset_id: number;
  asset_name?: string | null;
  asset_category?: string | null;
  finance_book?: string | null;
  schedule_date?: string | null;
  depreciation_amount: number;
}

export interface PendingDepreciationResponse {
  pending_entries: PendingDepreciationEntry[];
  total_pending_amount: number;
  count: number;
  as_of_date: string;
}

// Maintenance Types
export interface MaintenanceDueAsset {
  id: number;
  asset_name: string;
  asset_category?: string | null;
  location?: string | null;
  custodian?: string | null;
  serial_no?: string | null;
  purchase_date?: string | null;
  asset_value: number;
}

export interface MaintenanceDueResponse {
  assets: MaintenanceDueAsset[];
  count: number;
}

// Warranty Types
export interface WarrantyExpiringAsset {
  id: number;
  asset_name: string;
  asset_category?: string | null;
  serial_no?: string | null;
  supplier?: string | null;
  warranty_expiry_date?: string | null;
  days_remaining?: number | null;
}

export interface WarrantyExpiringResponse {
  assets: WarrantyExpiringAsset[];
  count: number;
}

// Insurance Types
export interface InsuranceExpiringAsset {
  id: number;
  asset_name: string;
  asset_category?: string | null;
  serial_no?: string | null;
  insured_value: number;
  insurance_end_date?: string | null;
  days_remaining?: number | null;
  comprehensive_insurance?: string | null;
}

export interface InsuranceExpiringResponse {
  assets: InsuranceExpiringAsset[];
  count: number;
}

// Asset Settings Types
export interface AssetSettings {
  id: number;
  company?: string | null;
  default_depreciation_method: string;
  default_finance_book?: string | null;
  depreciation_posting_date: string;
  auto_post_depreciation: boolean;
  enable_cwip_by_default: boolean;
  maintenance_alert_days: number;
  warranty_alert_days: number;
  insurance_alert_days: number;
}

export interface AssetSettingsUpdate {
  default_depreciation_method?: string;
  default_finance_book?: string | null;
  depreciation_posting_date?: string;
  auto_post_depreciation?: boolean;
  enable_cwip_by_default?: boolean;
  maintenance_alert_days?: number;
  warranty_alert_days?: number;
  insurance_alert_days?: number;
}

// =============================================================================
// ASSETS API
// =============================================================================

export const assetsApi = {
  // -------------------------------------------------------------------------
  // Assets
  // -------------------------------------------------------------------------

  /** List assets with optional filters */
  getAssets: (params?: {
    status?: string;
    category?: string;
    location?: string;
    custodian?: string;
    department?: string;
    search?: string;
    min_value?: number;
    max_value?: number;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<AssetListResponse>('/assets', { params }),

  /** Get asset detail */
  getAsset: (id: number | string) =>
    fetchApi<AssetDetail>(`/assets/${id}`),

  /** Create an asset */
  createAsset: (body: AssetCreatePayload) =>
    fetchApi<{ id: number; message: string }>('/assets', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** Update an asset */
  updateAsset: (id: number | string, body: AssetUpdatePayload) =>
    fetchApi<{ id: number; message: string }>(`/assets/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  /** Submit an asset */
  submitAsset: (id: number | string) =>
    fetchApi<{ id: number; message: string }>(`/assets/${id}/submit`, {
      method: 'POST',
    }),

  /** Scrap an asset */
  scrapAsset: (id: number | string, scrapDate?: string) =>
    fetchApi<{ id: number; message: string }>(`/assets/${id}/scrap`, {
      method: 'POST',
      params: scrapDate ? { scrap_date: scrapDate } : undefined,
    }),

  /** Get assets summary */
  getSummary: () =>
    fetchApi<AssetSummaryResponse>('/assets/summary'),

  // -------------------------------------------------------------------------
  // Asset Categories
  // -------------------------------------------------------------------------

  /** List asset categories */
  getCategories: (params?: { limit?: number; offset?: number }) =>
    fetchApi<AssetCategoryListResponse>('/assets/categories/', { params }),

  /** Create an asset category */
  createCategory: (body: AssetCategoryCreatePayload) =>
    fetchApi<{ id: number; message: string }>('/assets/categories/', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  // -------------------------------------------------------------------------
  // Depreciation
  // -------------------------------------------------------------------------

  /** Get depreciation schedule */
  getDepreciationSchedule: (params?: {
    asset_id?: number;
    finance_book?: string;
    from_date?: string;
    to_date?: string;
    pending_only?: boolean;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<DepreciationScheduleListResponse>('/assets/depreciation-schedule', { params }),

  /** Get pending depreciation entries */
  getPendingDepreciation: (asOfDate?: string) =>
    fetchApi<PendingDepreciationResponse>('/assets/pending-depreciation', {
      params: asOfDate ? { as_of_date: asOfDate } : undefined,
    }),

  // -------------------------------------------------------------------------
  // Maintenance
  // -------------------------------------------------------------------------

  /** Get assets with maintenance due */
  getMaintenanceDue: () =>
    fetchApi<MaintenanceDueResponse>('/assets/maintenance/due'),

  /** Mark asset for maintenance */
  markForMaintenance: (id: number | string) =>
    fetchApi<{ id: number; message: string }>(`/assets/${id}/mark-maintenance`, {
      method: 'POST',
    }),

  /** Complete maintenance for asset */
  completeMaintenance: (id: number | string) =>
    fetchApi<{ id: number; message: string }>(`/assets/${id}/complete-maintenance`, {
      method: 'POST',
    }),

  // -------------------------------------------------------------------------
  // Warranty
  // -------------------------------------------------------------------------

  /** Get assets with expiring warranty */
  getWarrantyExpiring: (days?: number) =>
    fetchApi<WarrantyExpiringResponse>('/assets/warranty/expiring', {
      params: days ? { days } : undefined,
    }),

  // -------------------------------------------------------------------------
  // Insurance
  // -------------------------------------------------------------------------

  /** Get assets with expiring insurance */
  getInsuranceExpiring: (days?: number) =>
    fetchApi<InsuranceExpiringResponse>('/assets/insurance/expiring', {
      params: days ? { days } : undefined,
    }),

  // -------------------------------------------------------------------------
  // Settings
  // -------------------------------------------------------------------------

  /** Get asset settings */
  getSettings: (company?: string) =>
    fetchApi<AssetSettings>('/assets/settings', {
      params: company ? { company } : undefined,
    }),

  /** Update asset settings */
  updateSettings: (body: AssetSettingsUpdate, company?: string) =>
    fetchApi<AssetSettings>('/assets/settings', {
      method: 'PATCH',
      body: JSON.stringify(body),
      params: company ? { company } : undefined,
    }),
};

// =============================================================================
// STANDALONE EXPORTS (for backward compatibility)
// =============================================================================

// Assets
export const getAssets = assetsApi.getAssets;
export const getAsset = assetsApi.getAsset;
export const createAsset = assetsApi.createAsset;
export const updateAsset = assetsApi.updateAsset;
export const submitAsset = assetsApi.submitAsset;
export const scrapAsset = assetsApi.scrapAsset;
export const getAssetsSummary = assetsApi.getSummary;

// Categories
export const getAssetCategories = assetsApi.getCategories;
export const createAssetCategory = assetsApi.createCategory;

// Depreciation
export const getDepreciationSchedule = assetsApi.getDepreciationSchedule;
export const getPendingDepreciation = assetsApi.getPendingDepreciation;

// Maintenance
export const getMaintenanceDue = assetsApi.getMaintenanceDue;
export const markAssetForMaintenance = assetsApi.markForMaintenance;
export const completeAssetMaintenance = assetsApi.completeMaintenance;

// Warranty
export const getWarrantyExpiring = assetsApi.getWarrantyExpiring;

// Insurance
export const getInsuranceExpiring = assetsApi.getInsuranceExpiring;

// Settings
export const getAssetSettings = assetsApi.getSettings;
export const updateAssetSettings = assetsApi.updateSettings;
