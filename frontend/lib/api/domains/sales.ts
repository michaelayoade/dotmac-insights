/**
 * Sales Domain API
 * Includes: Customer Groups, Territories, Sales Persons, Sales Transactions
 */

import { fetchApi } from '../core';

// =============================================================================
// TYPES - Customer Groups
// =============================================================================

export interface CustomerGroup {
  id: number;
  name: string;
  parent_customer_group?: string | null;
  is_group?: boolean;
  default_price_list?: string | null;
  default_payment_terms_template?: string | null;
  credit_limit?: number | null;
  payment_terms?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface CustomerGroupListResponse {
  items: CustomerGroup[];
  total: number;
}

export interface CustomerGroupPayload {
  name: string;
  parent_customer_group?: string | null;
  is_group?: boolean;
  default_price_list?: string | null;
  default_payment_terms_template?: string | null;
  credit_limit?: number | null;
}

// =============================================================================
// TYPES - Territories
// =============================================================================

export interface Territory {
  id: number;
  name: string;
  parent_territory?: string | null;
  is_group?: boolean;
  territory_manager?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface TerritoryListResponse {
  items: Territory[];
  total: number;
}

export interface TerritoryPayload {
  name: string;
  parent_territory?: string | null;
  is_group?: boolean;
  territory_manager?: string | null;
}

// =============================================================================
// TYPES - Sales Persons
// =============================================================================

export interface SalesPerson {
  id: number;
  name: string;
  employee?: string | null;
  employee_name?: string | null;
  parent_sales_person?: string | null;
  is_group?: boolean;
  enabled?: boolean;
  commission_rate?: number | null;
  created_at?: string;
  updated_at?: string;
}

export interface SalesPersonListResponse {
  items: SalesPerson[];
  total: number;
}

export interface SalesPersonPayload {
  name: string;
  employee?: string | null;
  parent_sales_person?: string | null;
  is_group?: boolean;
  enabled?: boolean;
  commission_rate?: number | null;
}

// =============================================================================
// API
// =============================================================================

export const salesApi = {
  // =========================================================================
  // CUSTOMER GROUPS
  // =========================================================================

  getCustomerGroups: (params?: { limit?: number; offset?: number; search?: string }) =>
    fetchApi<CustomerGroupListResponse>('/v1/sales/customer-groups', {
      params: params as Record<string, unknown>,
    }),

  getCustomerGroup: (id: number | string) =>
    fetchApi<CustomerGroup>(`/v1/sales/customer-groups/${id}`),

  createCustomerGroup: (payload: CustomerGroupPayload) =>
    fetchApi<CustomerGroup>('/v1/sales/customer-groups', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateCustomerGroup: (id: number | string, payload: Partial<CustomerGroupPayload>) =>
    fetchApi<CustomerGroup>(`/v1/sales/customer-groups/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deleteCustomerGroup: (id: number | string) =>
    fetchApi<void>(`/v1/sales/customer-groups/${id}`, {
      method: 'DELETE',
    }),

  // =========================================================================
  // TERRITORIES
  // =========================================================================

  getTerritories: (params?: { limit?: number; offset?: number; search?: string }) =>
    fetchApi<TerritoryListResponse>('/v1/sales/territories', {
      params: params as Record<string, unknown>,
    }),

  getTerritory: (id: number | string) =>
    fetchApi<Territory>(`/v1/sales/territories/${id}`),

  createTerritory: (payload: TerritoryPayload) =>
    fetchApi<Territory>('/v1/sales/territories', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateTerritory: (id: number | string, payload: Partial<TerritoryPayload>) =>
    fetchApi<Territory>(`/v1/sales/territories/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deleteTerritory: (id: number | string) =>
    fetchApi<void>(`/v1/sales/territories/${id}`, {
      method: 'DELETE',
    }),

  // =========================================================================
  // SALES PERSONS
  // =========================================================================

  getSalesPersons: (params?: { limit?: number; offset?: number; search?: string; enabled?: boolean }) =>
    fetchApi<SalesPersonListResponse>('/v1/sales/sales-persons', {
      params: params as Record<string, unknown>,
    }),

  getSalesPerson: (id: number | string) =>
    fetchApi<SalesPerson>(`/v1/sales/sales-persons/${id}`),

  createSalesPerson: (payload: SalesPersonPayload) =>
    fetchApi<SalesPerson>('/v1/sales/sales-persons', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateSalesPerson: (id: number | string, payload: Partial<SalesPersonPayload>) =>
    fetchApi<SalesPerson>(`/v1/sales/sales-persons/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deleteSalesPerson: (id: number | string) =>
    fetchApi<void>(`/v1/sales/sales-persons/${id}`, {
      method: 'DELETE',
    }),
};

export default salesApi;
