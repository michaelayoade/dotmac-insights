/**
 * API Module - Barrel Export
 *
 * This file provides backward compatibility by re-exporting everything
 * from domain-specific modules while also exposing the unified `api` object.
 *
 * Usage (unchanged):
 *   import { api, Customer, fetchApi } from '@/lib/api';
 *   const customers = await api.getCustomers();
 *
 * New usage (domain-specific):
 *   import { customersApi, crmApi } from '@/lib/api';
 *   const customers = await customersApi.getCustomers();
 *   const leads = await crmApi.getLeads();
 */

// Re-export core utilities
export * from './core';

// Re-export common types
export * from './types';

// Re-export domain APIs and types
export * from './domains';

// Re-export the unified api object from original api.ts for backward compatibility
// Note: Domain types are now exported from ./domains, not ../api
export { api } from '../api';
