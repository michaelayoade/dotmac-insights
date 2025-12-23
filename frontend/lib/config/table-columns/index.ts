/**
 * Table Column Registry
 *
 * Central export for all table column configurations.
 * Use column factories to get consistent table columns across pages.
 *
 * Usage:
 *   import { getSuppliersColumns, commonColumns } from '@/lib/config/table-columns';
 *
 *   // Get default columns
 *   const columns = getSuppliersColumns();
 *
 *   // Get columns with options
 *   const columns = getSuppliersColumns({
 *     exclude: ['description'],
 *     overrides: { name: { width: '300px' } }
 *   });
 *
 *   // Build custom column
 *   const columns = [
 *     commonColumns.code('id', 'ID'),
 *     commonColumns.date('created_at', 'Created'),
 *     commonColumns.currency('amount', 'Amount'),
 *     commonColumns.status(),
 *   ];
 */

// Common utilities and column builders
export {
  applyColumnOptions,
  commonColumns,
  getAccountTypeColor,
  getAccountTypeBadgeColor,
  type ColumnOptions,
} from './common';

// Accounting columns (re-export from existing file for backwards compatibility)
export {
  getTrialBalanceColumns,
  getSuppliersColumns,
  getChartOfAccountsColumns,
  getGeneralLedgerColumns,
} from '../accounting-tables';

// =============================================================================
// FUTURE COLUMN EXPORTS
// =============================================================================

// Sales columns (to be implemented)
// export { getInvoiceColumns, getCustomerColumns, getQuotationColumns } from './sales';

// Purchasing columns (to be implemented)
// export { getBillColumns, getPurchaseOrderColumns, getPaymentColumns } from './purchasing';

// Inventory columns (to be implemented)
// export { getItemColumns, getWarehouseColumns, getTransferColumns } from './inventory';

// HR columns (to be implemented)
// export { getEmployeeColumns, getLeaveColumns, getPayrollColumns } from './hr';

// Support columns (to be implemented)
// export { getTicketColumns, getAgentColumns } from './support';
