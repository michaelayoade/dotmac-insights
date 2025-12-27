/**
 * Sales Domain API
 * Includes: Customer Groups, Territories, Sales Persons
 *
 * NOTE: These endpoints now live under /crm/config/ in the backend.
 * This module provides backward compatibility - prefer using crmApi.config.* instead.
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
  // CUSTOMER GROUPS (now at /crm/customer-groups)
  // =========================================================================

  getCustomerGroups: (params?: { limit?: number; offset?: number; search?: string }) =>
    fetchApi<CustomerGroupListResponse>('/crm/customer-groups', {
      params: params as Record<string, unknown>,
    }),

  getCustomerGroup: (id: number | string) =>
    fetchApi<CustomerGroup>(`/crm/customer-groups/${id}`),

  createCustomerGroup: (payload: CustomerGroupPayload) =>
    fetchApi<CustomerGroup>('/crm/customer-groups', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateCustomerGroup: (id: number | string, payload: Partial<CustomerGroupPayload>) =>
    fetchApi<CustomerGroup>(`/crm/customer-groups/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deleteCustomerGroup: (id: number | string) =>
    fetchApi<void>(`/crm/customer-groups/${id}`, {
      method: 'DELETE',
    }),

  // =========================================================================
  // TERRITORIES (now at /crm/territories)
  // =========================================================================

  getTerritories: (params?: { limit?: number; offset?: number; search?: string }) =>
    fetchApi<TerritoryListResponse>('/crm/territories', {
      params: params as Record<string, unknown>,
    }),

  getTerritory: (id: number | string) =>
    fetchApi<Territory>(`/crm/territories/${id}`),

  createTerritory: (payload: TerritoryPayload) =>
    fetchApi<Territory>('/crm/territories', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateTerritory: (id: number | string, payload: Partial<TerritoryPayload>) =>
    fetchApi<Territory>(`/crm/territories/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deleteTerritory: (id: number | string) =>
    fetchApi<void>(`/crm/territories/${id}`, {
      method: 'DELETE',
    }),

  // =========================================================================
  // SALES PERSONS (now at /crm/sales-persons)
  // =========================================================================

  getSalesPersons: (params?: { limit?: number; offset?: number; search?: string; enabled?: boolean }) =>
    fetchApi<SalesPersonListResponse>('/crm/sales-persons', {
      params: params as Record<string, unknown>,
    }),

  getSalesPerson: (id: number | string) =>
    fetchApi<SalesPerson>(`/crm/sales-persons/${id}`),

  createSalesPerson: (payload: SalesPersonPayload) =>
    fetchApi<SalesPerson>('/crm/sales-persons', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateSalesPerson: (id: number | string, payload: Partial<SalesPersonPayload>) =>
    fetchApi<SalesPerson>(`/crm/sales-persons/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  deleteSalesPerson: (id: number | string) =>
    fetchApi<void>(`/crm/sales-persons/${id}`, {
      method: 'DELETE',
    }),
};

export default salesApi;
