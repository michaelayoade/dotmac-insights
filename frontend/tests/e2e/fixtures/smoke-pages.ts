/**
 * Auto-generated smoke test page definitions.
 * Generated on: 2025-12-27T06:53:49.034Z
 *
 * To regenerate: node scripts/generate-smoke-pages.js > tests/e2e/fixtures/smoke-pages.ts
 */

import type { Scope } from './auth';

export interface PageConfig {
  path: string;
  name: string;
  scopes: Scope[];
  skipReason?: string;
}

export const MODULE_SCOPES: Record<string, Scope[]> = {
  'home': [
    '*'
  ],
  'accounting': [
    'accounting:read'
  ],
  'admin': [
    'admin:read',
    'admin:write'
  ],
  'analytics': [
    'analytics:read'
  ],
  'assets': [
    'assets:read'
  ],
  'banking': [
    'payments:read',
    'openbanking:read'
  ],
  'books': [
    'books:read'
  ],
  'contacts': [
    'contacts:read'
  ],
  'crm': [
    'crm:read'
  ],
  'customers': [
    'customers:read'
  ],
  'expense': [
    'expenses:read'
  ],
  'expenses': [
    'expenses:read'
  ],
  'explorer': [
    'explorer:read'
  ],
  'field-service': [
    'field-service:read'
  ],
  'fleet': [
    'fleet:read'
  ],
  'hr': [
    'hr:read'
  ],
  'inbox': [
    'inbox:read'
  ],
  'insights': [
    'analytics:read'
  ],
  'inventory': [
    'inventory:read'
  ],
  'notifications': [
    '*'
  ],
  'performance': [
    'performance:read'
  ],
  'pops': [
    '*'
  ],
  'projects': [
    'projects:read'
  ],
  'purchasing': [
    'purchasing:read'
  ],
  'reports': [
    'reports:read'
  ],
  'sales': [
    'sales:read'
  ],
  'support': [
    'support:read'
  ],
  'sync': [
    'sync:read'
  ],
  'tasks': [
    '*'
  ]
};

export const SMOKE_PAGES: Record<string, PageConfig[]> = {
  'accounting': [
    { path: '/accounting', name: 'Accounting', scopes: MODULE_SCOPES['accounting'] || ['*'] },
    { path: '/accounting/accounts-payable', name: 'Accounting / Accounts Payable', scopes: MODULE_SCOPES['accounting'] || ['*'] },
    { path: '/accounting/accounts-receivable', name: 'Accounting / Accounts Receivable', scopes: MODULE_SCOPES['accounting'] || ['*'] },
    { path: '/accounting/balance-sheet', name: 'Accounting / Balance Sheet', scopes: MODULE_SCOPES['accounting'] || ['*'] },
    { path: '/accounting/bank-accounts', name: 'Accounting / Bank Accounts', scopes: MODULE_SCOPES['accounting'] || ['*'] },
    { path: '/accounting/chart-of-accounts', name: 'Accounting / Chart Of Accounts', scopes: MODULE_SCOPES['accounting'] || ['*'] },
    { path: '/accounting/general-ledger', name: 'Accounting / General Ledger', scopes: MODULE_SCOPES['accounting'] || ['*'] },
    { path: '/accounting/income-statement', name: 'Accounting / Income Statement', scopes: MODULE_SCOPES['accounting'] || ['*'] },
    { path: '/accounting/journal-entries', name: 'Accounting / Journal Entries', scopes: MODULE_SCOPES['accounting'] || ['*'] },
    { path: '/accounting/suppliers', name: 'Accounting / Suppliers', scopes: MODULE_SCOPES['accounting'] || ['*'] },
    { path: '/accounting/trial-balance', name: 'Accounting / Trial Balance', scopes: MODULE_SCOPES['accounting'] || ['*'] },
  ],
  'admin': [
    { path: '/admin', name: 'Admin', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/migration', name: 'Admin / Migration', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/migration/[id]', name: 'Admin / Migration / ID', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/platform', name: 'Admin / Platform', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/roles', name: 'Admin / Roles', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/security', name: 'Admin / Security', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/settings', name: 'Admin / Settings', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/settings/[group]', name: 'Admin / Settings / GROUP', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/settings/audit', name: 'Admin / Settings / Audit', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/sync', name: 'Admin / Sync', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/sync/cursors', name: 'Admin / Sync / Cursors', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/sync/dlq', name: 'Admin / Sync / Dlq', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/sync/outbound', name: 'Admin / Sync / Outbound', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/sync/schedules', name: 'Admin / Sync / Schedules', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/webhooks', name: 'Admin / Webhooks', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/webhooks/[id]', name: 'Admin / Webhooks / ID', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/webhooks/inbound', name: 'Admin / Webhooks / Inbound', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/webhooks/inbound/events', name: 'Admin / Webhooks / Inbound / Events', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/webhooks/inbound/events/[id]', name: 'Admin / Webhooks / Inbound / Events / ID', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/webhooks/inbound/providers/[name]', name: 'Admin / Webhooks / Inbound / Providers / NAME', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/webhooks/omni', name: 'Admin / Webhooks / Omni', scopes: MODULE_SCOPES['admin'] || ['*'] },
    { path: '/admin/webhooks/omni/[id]', name: 'Admin / Webhooks / Omni / ID', scopes: MODULE_SCOPES['admin'] || ['*'] },
  ],
  'analytics': [
    { path: '/analytics', name: 'Analytics', scopes: MODULE_SCOPES['analytics'] || ['*'] },
  ],
  'assets': [
    { path: '/assets', name: 'Assets', scopes: MODULE_SCOPES['assets'] || ['*'] },
    { path: '/assets/categories', name: 'Assets / Categories', scopes: MODULE_SCOPES['assets'] || ['*'] },
    { path: '/assets/depreciation', name: 'Assets / Depreciation', scopes: MODULE_SCOPES['assets'] || ['*'] },
    { path: '/assets/depreciation/pending', name: 'Assets / Depreciation / Pending', scopes: MODULE_SCOPES['assets'] || ['*'] },
    { path: '/assets/list', name: 'Assets / List', scopes: MODULE_SCOPES['assets'] || ['*'] },
    { path: '/assets/list/[id]', name: 'Assets / List / ID', scopes: MODULE_SCOPES['assets'] || ['*'] },
    { path: '/assets/list/new', name: 'Assets / List / New', scopes: MODULE_SCOPES['assets'] || ['*'] },
    { path: '/assets/maintenance', name: 'Assets / Maintenance', scopes: MODULE_SCOPES['assets'] || ['*'] },
    { path: '/assets/maintenance/insurance', name: 'Assets / Maintenance / Insurance', scopes: MODULE_SCOPES['assets'] || ['*'] },
    { path: '/assets/maintenance/warranty', name: 'Assets / Maintenance / Warranty', scopes: MODULE_SCOPES['assets'] || ['*'] },
    { path: '/assets/settings', name: 'Assets / Settings', scopes: MODULE_SCOPES['assets'] || ['*'] },
  ],
  'banking': [
    { path: '/banking', name: 'Banking', scopes: MODULE_SCOPES['banking'] || ['*'] },
    { path: '/banking/bank-accounts', name: 'Banking / Bank Accounts', scopes: MODULE_SCOPES['banking'] || ['*'] },
    { path: '/banking/bank-transactions', name: 'Banking / Bank Transactions', scopes: MODULE_SCOPES['banking'] || ['*'] },
  ],
  'books': [
    { path: '/books', name: 'Books', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/accounts-payable', name: 'Books / Accounts Payable', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/accounts-payable/bills', name: 'Books / Accounts Payable / Bills', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/accounts-payable/bills/new', name: 'Books / Accounts Payable / Bills / New', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/accounts-payable/debit-notes', name: 'Books / Accounts Payable / Debit Notes', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/accounts-payable/debit-notes/new', name: 'Books / Accounts Payable / Debit Notes / New', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/accounts-payable/payments', name: 'Books / Accounts Payable / Payments', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/accounts-payable/suppliers', name: 'Books / Accounts Payable / Suppliers', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/accounts-receivable', name: 'Books / Accounts Receivable', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/accounts-receivable/credit', name: 'Books / Accounts Receivable / Credit', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/accounts-receivable/credit-notes', name: 'Books / Accounts Receivable / Credit Notes', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/accounts-receivable/credit-notes/new', name: 'Books / Accounts Receivable / Credit Notes / New', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/accounts-receivable/customers', name: 'Books / Accounts Receivable / Customers', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/accounts-receivable/dunning', name: 'Books / Accounts Receivable / Dunning', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/accounts-receivable/invoices', name: 'Books / Accounts Receivable / Invoices', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/accounts-receivable/invoices/new', name: 'Books / Accounts Receivable / Invoices / New', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/accounts-receivable/payments', name: 'Books / Accounts Receivable / Payments', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/accounts-receivable/payments/new', name: 'Books / Accounts Receivable / Payments / New', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/balance-sheet', name: 'Books / Balance Sheet', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/bank-accounts', name: 'Books / Bank Accounts', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/bank-transactions', name: 'Books / Bank Transactions', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/bank-transactions/[id]', name: 'Books / Bank Transactions / ID', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/bank-transactions/import', name: 'Books / Bank Transactions / Import', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/bank-transactions/new', name: 'Books / Bank Transactions / New', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/cash-flow', name: 'Books / Cash Flow', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/chart-of-accounts', name: 'Books / Chart Of Accounts', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/chart-of-accounts/[id]', name: 'Books / Chart Of Accounts / ID', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/chart-of-accounts/new', name: 'Books / Chart Of Accounts / New', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/controls', name: 'Books / Controls', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/docs', name: 'Books / Docs', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/equity-statement', name: 'Books / Equity Statement', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/gateway/banks', name: 'Books / Gateway / Banks', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/gateway/connections', name: 'Books / Gateway / Connections', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/gateway/payments', name: 'Books / Gateway / Payments', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/gateway/transfers', name: 'Books / Gateway / Transfers', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/general-ledger', name: 'Books / General Ledger', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/gl-expenses', name: 'Books / Gl Expenses', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/income-statement', name: 'Books / Income Statement', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/journal-entries', name: 'Books / Journal Entries', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/journal-entries/[id]', name: 'Books / Journal Entries / ID', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/journal-entries/new', name: 'Books / Journal Entries / New', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/purchase-invoices', name: 'Books / Purchase Invoices', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/purchase-invoices/[id]', name: 'Books / Purchase Invoices / ID', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/settings', name: 'Books / Settings', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/settings/cost-centers', name: 'Books / Settings / Cost Centers', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/settings/fiscal-years', name: 'Books / Settings / Fiscal Years', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/settings/modes-of-payment', name: 'Books / Settings / Modes Of Payment', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/suppliers', name: 'Books / Suppliers', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/suppliers/[id]', name: 'Books / Suppliers / ID', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/suppliers/new', name: 'Books / Suppliers / New', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/tax', name: 'Books / Tax', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/tax/cit', name: 'Books / Tax / Cit', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/tax/einvoice', name: 'Books / Tax / Einvoice', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/tax/filing', name: 'Books / Tax / Filing', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/tax/paye', name: 'Books / Tax / Paye', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/tax/settings', name: 'Books / Tax / Settings', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/tax/vat', name: 'Books / Tax / Vat', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/tax/wht', name: 'Books / Tax / Wht', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/taxes', name: 'Books / Taxes', scopes: MODULE_SCOPES['books'] || ['*'] },
    { path: '/books/trial-balance', name: 'Books / Trial Balance', scopes: MODULE_SCOPES['books'] || ['*'] },
  ],
  'contacts': [
    { path: '/contacts', name: 'Contacts', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/[id]', name: 'Contacts / ID', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/[id]/edit', name: 'Contacts / ID / Edit', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/all', name: 'Contacts / All', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/analytics', name: 'Contacts / Analytics', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/categories', name: 'Contacts / Categories', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/churned', name: 'Contacts / Churned', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/customers', name: 'Contacts / Customers', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/duplicates', name: 'Contacts / Duplicates', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/export', name: 'Contacts / Export', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/funnel', name: 'Contacts / Funnel', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/import', name: 'Contacts / Import', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/leads', name: 'Contacts / Leads', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/lists', name: 'Contacts / Lists', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/new', name: 'Contacts / New', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/organizations', name: 'Contacts / Organizations', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/people', name: 'Contacts / People', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/qualification', name: 'Contacts / Qualification', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/quality', name: 'Contacts / Quality', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/tags', name: 'Contacts / Tags', scopes: MODULE_SCOPES['contacts'] || ['*'] },
    { path: '/contacts/territories', name: 'Contacts / Territories', scopes: MODULE_SCOPES['contacts'] || ['*'] },
  ],
  'crm': [
    { path: '/crm', name: 'Crm', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/activities', name: 'Crm / Activities', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/activities/new', name: 'Crm / Activities / New', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/analytics', name: 'Crm / Analytics', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/contacts/[id]', name: 'Crm / Contacts / ID', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/contacts/[id]/edit', name: 'Crm / Contacts / ID / Edit', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/contacts/all', name: 'Crm / Contacts / All', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/contacts/churned', name: 'Crm / Contacts / Churned', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/contacts/customers', name: 'Crm / Contacts / Customers', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/contacts/leads', name: 'Crm / Contacts / Leads', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/contacts/new', name: 'Crm / Contacts / New', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/contacts/organizations', name: 'Crm / Contacts / Organizations', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/contacts/people', name: 'Crm / Contacts / People', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/lifecycle/funnel', name: 'Crm / Lifecycle / Funnel', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/lifecycle/qualification', name: 'Crm / Lifecycle / Qualification', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/pipeline', name: 'Crm / Pipeline', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/pipeline/opportunities', name: 'Crm / Pipeline / Opportunities', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/pipeline/opportunities/[id]', name: 'Crm / Pipeline / Opportunities / ID', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/pipeline/opportunities/new', name: 'Crm / Pipeline / Opportunities / New', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/segments/categories', name: 'Crm / Segments / Categories', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/segments/lists', name: 'Crm / Segments / Lists', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/segments/tags', name: 'Crm / Segments / Tags', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/segments/territories', name: 'Crm / Segments / Territories', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/tools/duplicates', name: 'Crm / Tools / Duplicates', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/tools/export', name: 'Crm / Tools / Export', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/tools/import', name: 'Crm / Tools / Import', scopes: MODULE_SCOPES['crm'] || ['*'] },
    { path: '/crm/tools/quality', name: 'Crm / Tools / Quality', scopes: MODULE_SCOPES['crm'] || ['*'] },
  ],
  'customers': [
    { path: '/customers', name: 'Customers', scopes: MODULE_SCOPES['customers'] || ['*'] },
    { path: '/customers/analytics', name: 'Customers / Analytics', scopes: MODULE_SCOPES['customers'] || ['*'] },
    { path: '/customers/analytics/blocked', name: 'Customers / Analytics / Blocked', scopes: MODULE_SCOPES['customers'] || ['*'] },
    { path: '/customers/blocked', name: 'Customers / Blocked', scopes: MODULE_SCOPES['customers'] || ['*'] },
    { path: '/customers/insights', name: 'Customers / Insights', scopes: MODULE_SCOPES['customers'] || ['*'] },
  ],
  'expense': [
    { path: '/expense', name: 'Expense', scopes: MODULE_SCOPES['expense'] || ['*'] },
  ],
  'expenses': [
    { path: '/expenses', name: 'Expenses', scopes: MODULE_SCOPES['expenses'] || ['*'] },
    { path: '/expenses/advances', name: 'Expenses / Advances', scopes: MODULE_SCOPES['expenses'] || ['*'] },
    { path: '/expenses/advances/[id]', name: 'Expenses / Advances / ID', scopes: MODULE_SCOPES['expenses'] || ['*'] },
    { path: '/expenses/advances/new', name: 'Expenses / Advances / New', scopes: MODULE_SCOPES['expenses'] || ['*'] },
    { path: '/expenses/approvals', name: 'Expenses / Approvals', scopes: MODULE_SCOPES['expenses'] || ['*'] },
    { path: '/expenses/card-analytics', name: 'Expenses / Card Analytics', scopes: MODULE_SCOPES['expenses'] || ['*'] },
    { path: '/expenses/cards', name: 'Expenses / Cards', scopes: MODULE_SCOPES['expenses'] || ['*'] },
    { path: '/expenses/cards/[id]', name: 'Expenses / Cards / ID', scopes: MODULE_SCOPES['expenses'] || ['*'] },
    { path: '/expenses/cards/new', name: 'Expenses / Cards / New', scopes: MODULE_SCOPES['expenses'] || ['*'] },
    { path: '/expenses/claims', name: 'Expenses / Claims', scopes: MODULE_SCOPES['expenses'] || ['*'] },
    { path: '/expenses/claims/[id]', name: 'Expenses / Claims / ID', scopes: MODULE_SCOPES['expenses'] || ['*'] },
    { path: '/expenses/claims/new', name: 'Expenses / Claims / New', scopes: MODULE_SCOPES['expenses'] || ['*'] },
    { path: '/expenses/reports', name: 'Expenses / Reports', scopes: MODULE_SCOPES['expenses'] || ['*'] },
    { path: '/expenses/settings', name: 'Expenses / Settings', scopes: MODULE_SCOPES['expenses'] || ['*'] },
    { path: '/expenses/statements', name: 'Expenses / Statements', scopes: MODULE_SCOPES['expenses'] || ['*'] },
    { path: '/expenses/statements/import', name: 'Expenses / Statements / Import', scopes: MODULE_SCOPES['expenses'] || ['*'] },
    { path: '/expenses/transactions', name: 'Expenses / Transactions', scopes: MODULE_SCOPES['expenses'] || ['*'] },
  ],
  'explorer': [
    { path: '/explorer', name: 'Explorer', scopes: MODULE_SCOPES['explorer'] || ['*'] },
  ],
  'field-service': [
    { path: '/field-service', name: 'Field Service', scopes: MODULE_SCOPES['field-service'] || ['*'] },
    { path: '/field-service/analytics', name: 'Field Service / Analytics', scopes: MODULE_SCOPES['field-service'] || ['*'] },
    { path: '/field-service/orders', name: 'Field Service / Orders', scopes: MODULE_SCOPES['field-service'] || ['*'] },
    { path: '/field-service/orders/[id]', name: 'Field Service / Orders / ID', scopes: MODULE_SCOPES['field-service'] || ['*'] },
    { path: '/field-service/orders/new', name: 'Field Service / Orders / New', scopes: MODULE_SCOPES['field-service'] || ['*'] },
    { path: '/field-service/schedule', name: 'Field Service / Schedule', scopes: MODULE_SCOPES['field-service'] || ['*'] },
    { path: '/field-service/teams', name: 'Field Service / Teams', scopes: MODULE_SCOPES['field-service'] || ['*'] },
  ],
  'fleet': [
    { path: '/fleet', name: 'Fleet', scopes: MODULE_SCOPES['fleet'] || ['*'] },
    { path: '/fleet/[id]', name: 'Fleet / ID', scopes: MODULE_SCOPES['fleet'] || ['*'] },
  ],
  'home': [
    { path: '/', name: 'Home', scopes: MODULE_SCOPES['home'] || ['*'] },
  ],
  'hr': [
    { path: '/hr', name: 'Hr', scopes: MODULE_SCOPES['hr'] || ['*'] },
    { path: '/hr/analytics', name: 'Hr / Analytics', scopes: MODULE_SCOPES['hr'] || ['*'] },
    { path: '/hr/appraisals', name: 'Hr / Appraisals', scopes: MODULE_SCOPES['hr'] || ['*'] },
    { path: '/hr/attendance', name: 'Hr / Attendance', scopes: MODULE_SCOPES['hr'] || ['*'] },
    { path: '/hr/leave', name: 'Hr / Leave', scopes: MODULE_SCOPES['hr'] || ['*'] },
    { path: '/hr/lifecycle', name: 'Hr / Lifecycle', scopes: MODULE_SCOPES['hr'] || ['*'] },
    { path: '/hr/masters', name: 'Hr / Masters', scopes: MODULE_SCOPES['hr'] || ['*'] },
    { path: '/hr/masters/departments', name: 'Hr / Masters / Departments', scopes: MODULE_SCOPES['hr'] || ['*'] },
    { path: '/hr/masters/designations', name: 'Hr / Masters / Designations', scopes: MODULE_SCOPES['hr'] || ['*'] },
    { path: '/hr/masters/employees', name: 'Hr / Masters / Employees', scopes: MODULE_SCOPES['hr'] || ['*'] },
    { path: '/hr/payroll', name: 'Hr / Payroll', scopes: MODULE_SCOPES['hr'] || ['*'] },
    { path: '/hr/payroll/payslips', name: 'Hr / Payroll / Payslips', scopes: MODULE_SCOPES['hr'] || ['*'] },
    { path: '/hr/payroll/payslips/[id]', name: 'Hr / Payroll / Payslips / ID', scopes: MODULE_SCOPES['hr'] || ['*'] },
    { path: '/hr/payroll/run', name: 'Hr / Payroll / Run', scopes: MODULE_SCOPES['hr'] || ['*'] },
    { path: '/hr/payroll/settings', name: 'Hr / Payroll / Settings', scopes: MODULE_SCOPES['hr'] || ['*'] },
    { path: '/hr/recruitment', name: 'Hr / Recruitment', scopes: MODULE_SCOPES['hr'] || ['*'] },
    { path: '/hr/settings', name: 'Hr / Settings', scopes: MODULE_SCOPES['hr'] || ['*'] },
    { path: '/hr/training', name: 'Hr / Training', scopes: MODULE_SCOPES['hr'] || ['*'] },
  ],
  'inbox': [
    { path: '/inbox', name: 'Inbox', scopes: MODULE_SCOPES['inbox'] || ['*'] },
    { path: '/inbox/analytics', name: 'Inbox / Analytics', scopes: MODULE_SCOPES['inbox'] || ['*'] },
    { path: '/inbox/analytics/agents', name: 'Inbox / Analytics / Agents', scopes: MODULE_SCOPES['inbox'] || ['*'] },
    { path: '/inbox/analytics/channels', name: 'Inbox / Analytics / Channels', scopes: MODULE_SCOPES['inbox'] || ['*'] },
    { path: '/inbox/assigned', name: 'Inbox / Assigned', scopes: MODULE_SCOPES['inbox'] || ['*'] },
    { path: '/inbox/channels', name: 'Inbox / Channels', scopes: MODULE_SCOPES['inbox'] || ['*'] },
    { path: '/inbox/channels/chat', name: 'Inbox / Channels / Chat', scopes: MODULE_SCOPES['inbox'] || ['*'] },
    { path: '/inbox/channels/email', name: 'Inbox / Channels / Email', scopes: MODULE_SCOPES['inbox'] || ['*'] },
    { path: '/inbox/channels/whatsapp', name: 'Inbox / Channels / Whatsapp', scopes: MODULE_SCOPES['inbox'] || ['*'] },
    { path: '/inbox/contacts', name: 'Inbox / Contacts', scopes: MODULE_SCOPES['inbox'] || ['*'] },
    { path: '/inbox/contacts/companies', name: 'Inbox / Contacts / Companies', scopes: MODULE_SCOPES['inbox'] || ['*'] },
    { path: '/inbox/routing', name: 'Inbox / Routing', scopes: MODULE_SCOPES['inbox'] || ['*'] },
    { path: '/inbox/routing/teams', name: 'Inbox / Routing / Teams', scopes: MODULE_SCOPES['inbox'] || ['*'] },
    { path: '/inbox/settings', name: 'Inbox / Settings', scopes: MODULE_SCOPES['inbox'] || ['*'] },
    { path: '/inbox/settings/canned', name: 'Inbox / Settings / Canned', scopes: MODULE_SCOPES['inbox'] || ['*'] },
    { path: '/inbox/settings/signatures', name: 'Inbox / Settings / Signatures', scopes: MODULE_SCOPES['inbox'] || ['*'] },
    { path: '/inbox/unassigned', name: 'Inbox / Unassigned', scopes: MODULE_SCOPES['inbox'] || ['*'] },
  ],
  'insights': [
    { path: '/insights', name: 'Insights', scopes: MODULE_SCOPES['insights'] || ['*'] },
    { path: '/insights/anomalies', name: 'Insights / Anomalies', scopes: MODULE_SCOPES['insights'] || ['*'] },
    { path: '/insights/completeness', name: 'Insights / Completeness', scopes: MODULE_SCOPES['insights'] || ['*'] },
    { path: '/insights/health', name: 'Insights / Health', scopes: MODULE_SCOPES['insights'] || ['*'] },
    { path: '/insights/overview', name: 'Insights / Overview', scopes: MODULE_SCOPES['insights'] || ['*'] },
    { path: '/insights/relationships', name: 'Insights / Relationships', scopes: MODULE_SCOPES['insights'] || ['*'] },
    { path: '/insights/segments', name: 'Insights / Segments', scopes: MODULE_SCOPES['insights'] || ['*'] },
  ],
  'inventory': [
    { path: '/inventory', name: 'Inventory', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/batches', name: 'Inventory / Batches', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/batches/new', name: 'Inventory / Batches / New', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/items', name: 'Inventory / Items', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/items/[id]', name: 'Inventory / Items / ID', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/items/new', name: 'Inventory / Items / New', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/landed-cost-vouchers', name: 'Inventory / Landed Cost Vouchers', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/landed-cost-vouchers/[id]', name: 'Inventory / Landed Cost Vouchers / ID', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/purchase-receipts', name: 'Inventory / Purchase Receipts', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/reorder', name: 'Inventory / Reorder', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/sales-issues', name: 'Inventory / Sales Issues', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/serials', name: 'Inventory / Serials', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/serials/new', name: 'Inventory / Serials / New', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/settings', name: 'Inventory / Settings', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/settings/item-groups', name: 'Inventory / Settings / Item Groups', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/stock-entries', name: 'Inventory / Stock Entries', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/stock-entries/[id]', name: 'Inventory / Stock Entries / ID', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/stock-entries/new', name: 'Inventory / Stock Entries / New', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/stock-ledger', name: 'Inventory / Stock Ledger', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/summary', name: 'Inventory / Summary', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/transfers', name: 'Inventory / Transfers', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/transfers/[id]', name: 'Inventory / Transfers / ID', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/transfers/new', name: 'Inventory / Transfers / New', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/valuation', name: 'Inventory / Valuation', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/valuation/[item_code]', name: 'Inventory / Valuation / ITEM_CODE', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/warehouses', name: 'Inventory / Warehouses', scopes: MODULE_SCOPES['inventory'] || ['*'] },
    { path: '/inventory/warehouses/new', name: 'Inventory / Warehouses / New', scopes: MODULE_SCOPES['inventory'] || ['*'] },
  ],
  'notifications': [
    { path: '/notifications', name: 'Notifications', scopes: MODULE_SCOPES['notifications'] || ['*'] },
  ],
  'performance': [
    { path: '/performance', name: 'Performance', scopes: MODULE_SCOPES['performance'] || ['*'] },
    { path: '/performance/analytics', name: 'Performance / Analytics', scopes: MODULE_SCOPES['performance'] || ['*'] },
    { path: '/performance/kpis', name: 'Performance / Kpis', scopes: MODULE_SCOPES['performance'] || ['*'] },
    { path: '/performance/kpis/new', name: 'Performance / Kpis / New', scopes: MODULE_SCOPES['performance'] || ['*'] },
    { path: '/performance/kras', name: 'Performance / Kras', scopes: MODULE_SCOPES['performance'] || ['*'] },
    { path: '/performance/kras/new', name: 'Performance / Kras / New', scopes: MODULE_SCOPES['performance'] || ['*'] },
    { path: '/performance/periods', name: 'Performance / Periods', scopes: MODULE_SCOPES['performance'] || ['*'] },
    { path: '/performance/periods/new', name: 'Performance / Periods / New', scopes: MODULE_SCOPES['performance'] || ['*'] },
    { path: '/performance/reports/bonus', name: 'Performance / Reports / Bonus', scopes: MODULE_SCOPES['performance'] || ['*'] },
    { path: '/performance/reviews', name: 'Performance / Reviews', scopes: MODULE_SCOPES['performance'] || ['*'] },
    { path: '/performance/scorecards', name: 'Performance / Scorecards', scopes: MODULE_SCOPES['performance'] || ['*'] },
    { path: '/performance/templates', name: 'Performance / Templates', scopes: MODULE_SCOPES['performance'] || ['*'] },
    { path: '/performance/templates/new', name: 'Performance / Templates / New', scopes: MODULE_SCOPES['performance'] || ['*'] },
  ],
  'pops': [
    { path: '/pops', name: 'Pops', scopes: MODULE_SCOPES['pops'] || ['*'] },
  ],
  'projects': [
    { path: '/projects', name: 'Projects', scopes: MODULE_SCOPES['projects'] || ['*'] },
    { path: '/projects/[id]', name: 'Projects / ID', scopes: MODULE_SCOPES['projects'] || ['*'] },
    { path: '/projects/[id]/gantt', name: 'Projects / ID / Gantt', scopes: MODULE_SCOPES['projects'] || ['*'] },
    { path: '/projects/analytics', name: 'Projects / Analytics', scopes: MODULE_SCOPES['projects'] || ['*'] },
    { path: '/projects/new', name: 'Projects / New', scopes: MODULE_SCOPES['projects'] || ['*'] },
    { path: '/projects/tasks', name: 'Projects / Tasks', scopes: MODULE_SCOPES['projects'] || ['*'] },
    { path: '/projects/tasks/[id]', name: 'Projects / Tasks / ID', scopes: MODULE_SCOPES['projects'] || ['*'] },
    { path: '/projects/tasks/new', name: 'Projects / Tasks / New', scopes: MODULE_SCOPES['projects'] || ['*'] },
    { path: '/projects/templates', name: 'Projects / Templates', scopes: MODULE_SCOPES['projects'] || ['*'] },
    { path: '/projects/templates/[id]', name: 'Projects / Templates / ID', scopes: MODULE_SCOPES['projects'] || ['*'] },
    { path: '/projects/templates/new', name: 'Projects / Templates / New', scopes: MODULE_SCOPES['projects'] || ['*'] },
  ],
  'purchasing': [
    { path: '/purchasing', name: 'Purchasing', scopes: MODULE_SCOPES['purchasing'] || ['*'] },
    { path: '/purchasing/aging', name: 'Purchasing / Aging', scopes: MODULE_SCOPES['purchasing'] || ['*'] },
    { path: '/purchasing/analytics', name: 'Purchasing / Analytics', scopes: MODULE_SCOPES['purchasing'] || ['*'] },
    { path: '/purchasing/bills', name: 'Purchasing / Bills', scopes: MODULE_SCOPES['purchasing'] || ['*'] },
    { path: '/purchasing/bills/[id]', name: 'Purchasing / Bills / ID', scopes: MODULE_SCOPES['purchasing'] || ['*'] },
    { path: '/purchasing/bills/new', name: 'Purchasing / Bills / New', scopes: MODULE_SCOPES['purchasing'] || ['*'] },
    { path: '/purchasing/debit-notes', name: 'Purchasing / Debit Notes', scopes: MODULE_SCOPES['purchasing'] || ['*'] },
    { path: '/purchasing/debit-notes/[id]', name: 'Purchasing / Debit Notes / ID', scopes: MODULE_SCOPES['purchasing'] || ['*'] },
    { path: '/purchasing/erpnext-expenses', name: 'Purchasing / Erpnext Expenses', scopes: MODULE_SCOPES['purchasing'] || ['*'] },
    { path: '/purchasing/erpnext-expenses/[id]', name: 'Purchasing / Erpnext Expenses / ID', scopes: MODULE_SCOPES['purchasing'] || ['*'] },
    { path: '/purchasing/expenses', name: 'Purchasing / Expenses', scopes: MODULE_SCOPES['purchasing'] || ['*'] },
    { path: '/purchasing/orders', name: 'Purchasing / Orders', scopes: MODULE_SCOPES['purchasing'] || ['*'] },
    { path: '/purchasing/orders/[id]', name: 'Purchasing / Orders / ID', scopes: MODULE_SCOPES['purchasing'] || ['*'] },
    { path: '/purchasing/orders/new', name: 'Purchasing / Orders / New', scopes: MODULE_SCOPES['purchasing'] || ['*'] },
    { path: '/purchasing/payments', name: 'Purchasing / Payments', scopes: MODULE_SCOPES['purchasing'] || ['*'] },
    { path: '/purchasing/payments/[id]', name: 'Purchasing / Payments / ID', scopes: MODULE_SCOPES['purchasing'] || ['*'] },
    { path: '/purchasing/suppliers', name: 'Purchasing / Suppliers', scopes: MODULE_SCOPES['purchasing'] || ['*'] },
    { path: '/purchasing/suppliers/[id]', name: 'Purchasing / Suppliers / ID', scopes: MODULE_SCOPES['purchasing'] || ['*'] },
    { path: '/purchasing/suppliers/new', name: 'Purchasing / Suppliers / New', scopes: MODULE_SCOPES['purchasing'] || ['*'] },
  ],
  'reports': [
    { path: '/reports', name: 'Reports', scopes: MODULE_SCOPES['reports'] || ['*'] },
    { path: '/reports/cash-position', name: 'Reports / Cash Position', scopes: MODULE_SCOPES['reports'] || ['*'] },
    { path: '/reports/expenses', name: 'Reports / Expenses', scopes: MODULE_SCOPES['reports'] || ['*'] },
    { path: '/reports/profitability', name: 'Reports / Profitability', scopes: MODULE_SCOPES['reports'] || ['*'] },
    { path: '/reports/revenue', name: 'Reports / Revenue', scopes: MODULE_SCOPES['reports'] || ['*'] },
  ],
  'sales': [
    { path: '/sales', name: 'Sales', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/activities', name: 'Sales / Activities', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/activities/new', name: 'Sales / Activities / New', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/analytics', name: 'Sales / Analytics', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/contacts', name: 'Sales / Contacts', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/contacts/new', name: 'Sales / Contacts / New', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/credit-notes', name: 'Sales / Credit Notes', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/credit-notes/[id]', name: 'Sales / Credit Notes / ID', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/credit-notes/[id]/edit', name: 'Sales / Credit Notes / ID / Edit', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/credit-notes/new', name: 'Sales / Credit Notes / New', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/customers', name: 'Sales / Customers', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/customers/[id]', name: 'Sales / Customers / ID', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/customers/[id]/edit', name: 'Sales / Customers / ID / Edit', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/customers/new', name: 'Sales / Customers / New', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/insights', name: 'Sales / Insights', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/invoices', name: 'Sales / Invoices', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/invoices/[id]', name: 'Sales / Invoices / ID', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/invoices/[id]/edit', name: 'Sales / Invoices / ID / Edit', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/invoices/new', name: 'Sales / Invoices / New', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/leads', name: 'Sales / Leads', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/leads/[id]', name: 'Sales / Leads / ID', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/leads/new', name: 'Sales / Leads / New', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/opportunities', name: 'Sales / Opportunities', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/opportunities/[id]', name: 'Sales / Opportunities / ID', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/opportunities/new', name: 'Sales / Opportunities / New', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/orders', name: 'Sales / Orders', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/orders/[id]', name: 'Sales / Orders / ID', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/orders/[id]/edit', name: 'Sales / Orders / ID / Edit', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/orders/new', name: 'Sales / Orders / New', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/payments', name: 'Sales / Payments', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/payments/[id]', name: 'Sales / Payments / ID', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/payments/[id]/edit', name: 'Sales / Payments / ID / Edit', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/payments/new', name: 'Sales / Payments / New', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/pipeline', name: 'Sales / Pipeline', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/quotations', name: 'Sales / Quotations', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/quotations/[id]', name: 'Sales / Quotations / ID', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/quotations/[id]/edit', name: 'Sales / Quotations / ID / Edit', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/quotations/new', name: 'Sales / Quotations / New', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/settings', name: 'Sales / Settings', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/settings/customer-groups', name: 'Sales / Settings / Customer Groups', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/settings/sales-persons', name: 'Sales / Settings / Sales Persons', scopes: MODULE_SCOPES['sales'] || ['*'] },
    { path: '/sales/settings/territories', name: 'Sales / Settings / Territories', scopes: MODULE_SCOPES['sales'] || ['*'] },
  ],
  'support': [
    { path: '/support', name: 'Support', scopes: MODULE_SCOPES['support'] || ['*'] },
    { path: '/support/agents', name: 'Support / Agents', scopes: MODULE_SCOPES['support'] || ['*'] },
    { path: '/support/analytics', name: 'Support / Analytics', scopes: MODULE_SCOPES['support'] || ['*'] },
    { path: '/support/automation', name: 'Support / Automation', scopes: MODULE_SCOPES['support'] || ['*'] },
    { path: '/support/canned-responses', name: 'Support / Canned Responses', scopes: MODULE_SCOPES['support'] || ['*'] },
    { path: '/support/csat', name: 'Support / Csat', scopes: MODULE_SCOPES['support'] || ['*'] },
    { path: '/support/kb', name: 'Support / Kb', scopes: MODULE_SCOPES['support'] || ['*'] },
    { path: '/support/routing', name: 'Support / Routing', scopes: MODULE_SCOPES['support'] || ['*'] },
    { path: '/support/settings', name: 'Support / Settings', scopes: MODULE_SCOPES['support'] || ['*'] },
    { path: '/support/sla', name: 'Support / Sla', scopes: MODULE_SCOPES['support'] || ['*'] },
    { path: '/support/teams', name: 'Support / Teams', scopes: MODULE_SCOPES['support'] || ['*'] },
    { path: '/support/tickets', name: 'Support / Tickets', scopes: MODULE_SCOPES['support'] || ['*'] },
    { path: '/support/tickets/[id]', name: 'Support / Tickets / ID', scopes: MODULE_SCOPES['support'] || ['*'] },
    { path: '/support/tickets/new', name: 'Support / Tickets / New', scopes: MODULE_SCOPES['support'] || ['*'] },
  ],
  'sync': [
    { path: '/sync', name: 'Sync', scopes: MODULE_SCOPES['sync'] || ['*'] },
  ],
  'tasks': [
    { path: '/tasks', name: 'Tasks', scopes: MODULE_SCOPES['tasks'] || ['*'] },
  ],
};

/**
 * Get all pages as a flat array
 */
export function getAllPages(): PageConfig[] {
  return Object.values(SMOKE_PAGES).flat();
}

/**
 * Get static pages only (no dynamic [id] routes)
 */
export function getStaticPages(): PageConfig[] {
  return getAllPages().filter(p => !p.path.includes('['));
}

/**
 * Get page count
 */
export function getPageCount(): { total: number; static: number; dynamic: number } {
  const all = getAllPages();
  const staticPages = all.filter(p => !p.path.includes('['));
  return {
    total: all.length,
    static: staticPages.length,
    dynamic: all.length - staticPages.length,
  };
}

