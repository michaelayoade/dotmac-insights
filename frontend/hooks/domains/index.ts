/**
 * Domain Hooks - Barrel Export
 *
 * Re-exports all domain-specific hooks for convenient importing.
 *
 * Usage:
 *   import { useSyncStatus, useAccountingDashboard } from '@/hooks/domains';
 */

// Sync domain
export * from './useSync';

// Note: Additional domain modules to be added incrementally:
// export * from './useAccounting';
// export * from './useSupport';
// export * from './useCustomers';
// export * from './useFinance';
// export * from './usePurchasing';
// export * from './useInventory';
// export * from './useHr';
// export * from './useTax';
// export * from './useProjects';
// export * from './useAnalytics';
// export * from './useInsights';
// export * from './useAdmin';
// export * from './useGeneric';
