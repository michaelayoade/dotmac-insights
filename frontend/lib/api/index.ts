/**
 * API Module - Barrel Export
 *
 * This file provides backward compatibility by re-exporting everything
 * from the original api.ts file while also exposing new domain-specific APIs.
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

// Re-export everything from the original api.ts for backward compatibility
// This includes the main `api` object and all types
export * from '../api';
