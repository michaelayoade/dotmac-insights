/**
 * Accounting Domain API
 * Includes: GL, Journals, Bank Transactions, Financial Statements, Tax
 */

import { fetchApi, fetchApiFormData } from '../core';

// =============================================================================
// IFRS COMPLIANCE TYPES
// =============================================================================

export interface ValidationIssue {
  code: string;
  message: string;
  field?: string | null;
  expected?: number | string | null;
  actual?: number | string | null;
}

export interface ValidationResult {
  is_valid: boolean;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
}

export interface FXMetadata {
  functional_currency: string;
  presentation_currency: string;
  is_same_currency: boolean;
  average_rate?: number;
  closing_rate?: number;
}

export interface ComparativePeriod {
  start_date?: string;
  end_date?: string;
  as_of_date?: string;
}

export interface EarningsPerShare {
  basic_eps?: number;
  diluted_eps?: number;
  weighted_average_shares_basic?: number;
  weighted_average_shares_diluted?: number;
  dilutive_instruments?: Array<{
    instrument_type: string;
    shares_equivalent: number;
    dilutive_effect: number;
  }>;
  note?: string;
}

export interface TaxReconciliation {
  profit_before_tax: number;
  statutory_rate: number;
  tax_at_statutory_rate: number;
  reconciling_items: Array<{
    description: string;
    amount: number;
    rate_effect?: number;
  }>;
  effective_tax_expense: number;
  effective_tax_rate: number;
}

export interface OCIComponent {
  description: string;
  amount: number;
  may_be_reclassified: boolean;
  reclassification_adjustment?: number;
}

export interface OtherComprehensiveIncome {
  items_may_be_reclassified: OCIComponent[];
  items_not_reclassified: OCIComponent[];
  total_may_be_reclassified: number;
  total_not_reclassified: number;
  total_oci: number;
}

export type NonCashTransactionType =
  | 'lease_inception'
  | 'debt_conversion'
  | 'asset_exchange'
  | 'barter'
  | 'share_based_payment'
  | 'other';

export interface NonCashTransaction {
  transaction_type: NonCashTransactionType;
  description: string;
  amount: number;
  debit_account?: string;
  credit_account?: string;
}

export interface CashFlowClassificationPolicy {
  interest_paid: 'operating' | 'investing' | 'financing';
  interest_received: 'operating' | 'investing' | 'financing';
  dividends_paid: 'operating' | 'investing' | 'financing';
  dividends_received: 'operating' | 'investing' | 'financing';
  taxes_paid: 'operating' | 'investing' | 'financing';
}

// =============================================================================
// DASHBOARD & ACCOUNTS
// =============================================================================

export interface AccountingDashboard {
  summary: {
    total_assets: number;
    total_liabilities: number;
    total_equity: number;
    net_income_ytd: number;
    cash_balance: number;
    accounts_receivable: number;
    accounts_payable: number;
  };
  kpis: {
    current_ratio?: number;
    quick_ratio?: number;
    debt_to_equity?: number;
    gross_margin?: number;
    net_margin?: number;
  };
  recent_transactions?: AccountingGeneralLedgerEntry[];
  period?: { start: string; end: string };
  currency?: string;
}

export interface AccountingAccount {
  id: number;
  account_number: string;
  account_name: string;
  account_type: string;
  parent_account?: string | null;
  balance: number;
  is_group: boolean;
  root_type?: string | null;
  report_type?: string | null;
  currency?: string | null;
}

export interface AccountingAccountTreeNode {
  account_number: string;
  account_name: string;
  account_type: string;
  balance: number;
  is_group: boolean;
  children: AccountingAccountTreeNode[];
}

export interface AccountingChartOfAccounts {
  accounts: AccountingAccount[];
  tree: AccountingAccountTreeNode[];
  total_accounts: number;
  total?: number;
}

export interface AccountingAccountDetail extends AccountingAccount {
  ledger?: AccountingGeneralLedgerEntry[];
}

// =============================================================================
// GENERAL LEDGER
// =============================================================================

export interface AccountingGeneralLedgerEntry {
  id: number | string;
  posting_date: string | null;
  account: string;
  account_name?: string | null;
  party_type?: string | null;
  party?: string | null;
  voucher_no?: string | null;
  voucher_type?: string | null;
  cost_center?: string | null;
  fiscal_year?: string | null;
  remarks?: string | null;
  debit?: number | null;
  credit?: number | null;
  balance?: number | null;
}

export interface AccountingGeneralLedgerResponse {
  entries: AccountingGeneralLedgerEntry[];
  total: number;
  limit: number;
  offset: number;
  summary?: {
    total_debit?: number;
    total_credit?: number;
    opening_balance?: number;
    closing_balance?: number;
  };
}

// =============================================================================
// JOURNAL ENTRIES
// =============================================================================

export interface AccountingJournalEntryLine {
  account: string;
  debit: number;
  credit: number;
  party_type?: string | null;
  party?: string | null;
  cost_center?: string | null;
}

export type AccountingJournalEntryPayload = {
  id?: number | string;
  name?: string | null;
  posting_date: string;
  reference?: string | null;
  remarks?: string | null;
  currency?: string | null;
  accounts: AccountingJournalEntryLine[];
  status?: string | null;
};

export interface AccountingJournalEntry {
  id: number;
  voucher_type: string;
  voucher_no: string;
  posting_date: string;
  total_debit: number;
  total_credit: number;
  user_remark?: string | null;
  is_opening?: boolean;
  docstatus?: number;
  entries?: Array<{
    account: string;
    debit: number;
    credit: number;
    party_type?: string | null;
    party?: string | null;
    cost_center?: string | null;
  }>;
  accounts?: Array<{
    id?: number;
    account?: string;
    account_type?: string | null;
    party_type?: string | null;
    party?: string | null;
    debit?: number;
    credit?: number;
    debit_in_account_currency?: number;
    credit_in_account_currency?: number;
    exchange_rate?: number;
    reference_type?: string | null;
    reference_name?: string | null;
    reference_due_date?: string | null;
    cost_center?: string | null;
    project?: string | null;
    bank_account?: string | null;
    cheque_no?: string | null;
    cheque_date?: string | null;
    user_remark?: string | null;
    idx?: number;
  }>;
}

export interface AccountingJournalEntryListResponse {
  entries: AccountingJournalEntry[];
  total: number;
  limit: number;
  offset: number;
}

// =============================================================================
// FINANCIAL STATEMENTS
// =============================================================================

export interface AccountingTrialBalance {
  total_debit: number;
  total_credit: number;
  is_balanced: boolean;
  difference: number;
  accounts: Array<{
    account_number: string;
    account_name: string;
    account_type: string;
    debit: number;
    credit: number;
    balance: number;
  }>;
  as_of_date?: string;
  validation?: ValidationResult;
  fx_metadata?: FXMetadata;
}

export interface AccountingBalanceSheet {
  assets: {
    current_assets: Array<{ account: string; balance: number }>;
    fixed_assets: Array<{ account: string; balance: number }>;
    other_assets: Array<{ account: string; balance: number }>;
    accounts?: Array<{ account: string; balance: number; account_type?: string; pct_of_total?: number }>;
    total: number;
  };
  liabilities: {
    current_liabilities: Array<{ account: string; balance: number }>;
    long_term_liabilities: Array<{ account: string; balance: number }>;
    accounts?: Array<{ account: string; balance: number; account_type?: string; pct_of_total?: number }>;
    total: number;
  };
  equity: {
    items: Array<{ account: string; balance: number }>;
    retained_earnings: number;
    accounts?: Array<{ account: string; balance: number }>;
    total: number;
  };
  assets_classified?: {
    current_assets: { accounts: Array<{ account: string; balance: number; pct_of_total?: number }>; total: number };
    non_current_assets: { accounts: Array<{ account: string; balance: number; pct_of_total?: number }>; total: number };
    right_of_use_assets?: { accounts: Array<{ account: string; balance: number }>; total: number };
    deferred_tax_assets?: { accounts: Array<{ account: string; balance: number }>; total: number };
    total: number;
  };
  liabilities_classified?: {
    current_liabilities: { accounts: Array<{ account: string; balance: number; pct_of_total?: number }>; total: number };
    non_current_liabilities: { accounts: Array<{ account: string; balance: number; pct_of_total?: number }>; total: number };
    lease_liabilities?: { current: number; non_current: number; total: number };
    deferred_tax_liabilities?: { accounts: Array<{ account: string; balance: number }>; total: number };
    provisions?: { accounts: Array<{ account: string; balance: number }>; total: number };
    total: number;
  };
  equity_classified?: {
    share_capital?: { accounts: Array<{ account: string; balance: number }>; total: number };
    share_premium?: { accounts: Array<{ account: string; balance: number }>; total: number };
    reserves?: { accounts: Array<{ account: string; balance: number }>; total: number };
    other_comprehensive_income?: { accounts: Array<{ account: string; balance: number }>; total: number };
    retained_earnings?: { accounts: Array<{ account: string; balance: number }>; from_equity_accounts?: number; current_period_profit?: number; total: number };
    treasury_shares?: { accounts: Array<{ account: string; balance: number }>; total: number };
    share_based_payments?: { accounts: Array<{ account: string; balance: number }>; total: number };
    total: number;
  };
  total_assets?: number;
  total_current_assets?: number;
  total_non_current_assets?: number;
  total_liabilities?: number;
  total_current_liabilities?: number;
  total_non_current_liabilities?: number;
  total_equity?: number;
  total_liabilities_equity: number;
  working_capital?: number;
  retained_earnings?: number;
  difference?: number;
  is_balanced: boolean;
  as_of_date?: string;
  currency?: string | null;
  prior_period?: {
    as_of_date: string;
    total_assets: number;
    total_liabilities: number;
    total_equity: number;
  };
  variance?: {
    total_assets: { variance: number; variance_pct: number };
    total_liabilities: { variance: number; variance_pct: number };
    total_equity: { variance: number; variance_pct: number };
  };
  validation?: ValidationResult;
  fx_metadata?: FXMetadata;
  reclassified_accounts?: Array<{
    account: string;
    original_root_type: string;
    effective_root_type: string;
    account_type: string;
  }>;
}

export interface AccountingIncomeStatement {
  revenue: {
    items: Array<{ account: string; amount: number; prior_amount?: number; variance?: number; variance_pct?: number }>;
    total: number;
    accounts?: Array<{ account: string; amount: number }>;
  };
  cost_of_goods_sold: {
    items: Array<{ account: string; amount: number; prior_amount?: number; variance?: number; variance_pct?: number }>;
    total: number;
    accounts?: Array<{ account: string; amount: number }>;
  };
  gross_profit: number;
  gross_margin?: number;
  operating_expenses: {
    items: Array<{ account: string; amount: number; prior_amount?: number; variance?: number; variance_pct?: number }>;
    total: number;
    accounts?: Array<{ account: string; amount: number }>;
  };
  depreciation_amortization?: number;
  operating_income: number;
  operating_margin?: number;
  ebit?: number;
  ebitda?: number;
  ebitda_margin?: number;
  finance_income?: {
    accounts: Array<{ account: string; amount: number }>;
    total: number;
  };
  finance_costs?: {
    accounts: Array<{ account: string; amount: number }>;
    total: number;
  };
  net_finance_income?: number;
  profit_before_tax?: number;
  ebt?: number;
  tax_expense?: {
    accounts: Array<{ account: string; amount: number }>;
    total: number;
  };
  effective_tax_rate?: number;
  tax_reconciliation?: TaxReconciliation;
  profit_after_tax?: number;
  other_income: {
    items: Array<{ account: string; amount: number }>;
    total: number;
  };
  other_expenses: {
    items: Array<{ account: string; amount: number }>;
    total: number;
  };
  net_income: number;
  net_margin?: number;
  other_comprehensive_income?: OtherComprehensiveIncome;
  total_comprehensive_income?: number;
  earnings_per_share?: EarningsPerShare;
  period?: { start: string; end: string; start_date?: string; end_date?: string; fiscal_year?: string };
  classification_basis?: 'by_nature' | 'by_function';
  basis?: 'accrual' | 'cash';
  currency?: string;
  prior_period?: {
    start_date: string;
    end_date: string;
    revenue: number;
    gross_profit: number;
    operating_income: number;
    net_income: number;
  };
  variance?: {
    revenue: { variance: number; variance_pct: number };
    gross_profit: { variance: number; variance_pct: number };
    operating_income: { variance: number; variance_pct: number };
    net_income: { variance: number; variance_pct: number };
  };
  ytd_period?: { start_date: string; end_date: string };
  ytd_revenue?: number;
  ytd_gross_profit?: number;
  ytd_operating_income?: number;
  ytd_net_income?: number;
  validation?: ValidationResult;
  fx_metadata?: FXMetadata;
}

export interface AccountingCashFlow {
  period?: { start_date: string; end_date: string; fiscal_year?: string };
  currency?: string;
  method?: 'indirect' | 'direct';
  operating_activities: {
    net_income?: number;
    adjustments?: {
      depreciation_amortization?: number;
      impairment?: number;
      provisions?: number;
      unrealized_fx?: number;
      other?: number;
    };
    working_capital_changes?: {
      accounts_receivable?: number;
      inventory?: number;
      prepaid_expenses?: number;
      accounts_payable?: number;
      accrued_liabilities?: number;
      other?: number;
      total?: number;
    };
    items?: Array<{ description: string; amount: number }>;
    net: number;
  };
  investing_activities: {
    fixed_asset_purchases?: number;
    fixed_asset_sales?: number;
    investments?: number;
    acquisition_of_subsidiaries?: number;
    disposal_of_subsidiaries?: number;
    items?: Array<{ description: string; amount: number }>;
    net: number;
  };
  financing_activities: {
    debt_proceeds?: number;
    debt_repayments?: number;
    equity_proceeds?: number;
    dividends_paid?: number;
    lease_payments?: number;
    treasury_share_transactions?: number;
    items?: Array<{ description: string; amount: number }>;
    net: number;
  };
  supplementary_disclosures?: {
    interest_paid: number;
    interest_received: number;
    dividends_paid: number;
    dividends_received: number;
    income_taxes_paid: number;
    classification_policy?: CashFlowClassificationPolicy;
  };
  non_cash_transactions?: {
    note: string;
    examples: string[];
    items?: NonCashTransaction[];
  };
  fx_effect_on_cash?: number;
  total_cash_flow?: number;
  net_change_in_cash: number;
  opening_cash: number;
  closing_cash: number;
  reconciliation_difference?: number;
  is_reconciled?: boolean;
  bank_summary?: {
    deposits: number;
    withdrawals: number;
  };
  cfo_reconciliation?: {
    net_income: number;
    add_depreciation_amortization: number;
    add_working_capital_changes: number;
    add_other_adjustments: number;
    equals_cash_from_operations: number;
    is_reconciled: boolean;
  };
  prior_period?: {
    start_date: string;
    end_date: string;
    operating_activities_net: number;
    investing_activities_net: number;
    financing_activities_net: number;
    net_change_in_cash: number;
  };
  variance?: {
    operating: { variance: number; variance_pct: number };
    investing: { variance: number; variance_pct: number };
    financing: { variance: number; variance_pct: number };
    net_change: { variance: number; variance_pct: number };
  };
  validation?: ValidationResult;
  fx_metadata?: FXMetadata;
}

export interface AccountingEquityStatement {
  period: { start_date: string; end_date: string; fiscal_year?: string };
  currency: string;
  components: Array<{
    component: string;
    opening_balance: number;
    profit_loss: number;
    other_comprehensive_income: number;
    dividends: number;
    share_transactions: number;
    share_based_payments: number;
    fx_translation_reserve: number;
    transfers: number;
    other_movements: number;
    closing_balance: number;
    accounts?: Record<string, number>;
  }>;
  oci_breakdown?: {
    items_may_be_reclassified: Array<{
      component: string;
      description: string;
      amount: number;
      reclassification_adjustment?: number;
    }>;
    items_not_reclassified: Array<{
      component: string;
      description: string;
      amount: number;
    }>;
    total_may_be_reclassified: number;
    total_not_reclassified: number;
    total_oci: number;
  };
  summary: {
    total_opening_equity: number;
    total_comprehensive_income: number;
    profit_for_period: number;
    other_comprehensive_income: number;
    transactions_with_owners: {
      dividends_paid: number;
      share_issues: number;
      treasury_share_transactions: number;
      share_based_payments: number;
    };
    total_closing_equity: number;
    change_in_equity: number;
  };
  reconciliation: {
    opening_equity: number;
    add_profit_for_period: number;
    add_other_comprehensive_income: number;
    less_dividends: number;
    add_share_issues: number;
    add_share_based_payments: number;
    less_treasury_shares: number;
    other_movements: number;
    closing_equity: number;
    is_reconciled: boolean;
  };
  prior_period?: {
    start_date: string;
    end_date: string;
    total_opening_equity: number;
    total_closing_equity: number;
    profit_for_period: number;
    total_comprehensive_income: number;
  };
  variance?: {
    opening_equity: { variance: number; variance_pct: number };
    closing_equity: { variance: number; variance_pct: number };
    comprehensive_income: { variance: number; variance_pct: number };
  };
  validation?: ValidationResult;
  fx_metadata?: FXMetadata;
}

export interface AccountingFinancialRatios {
  as_of_date: string;
  period: { start_date: string; end_date: string; days: number };
  liquidity_ratios: {
    current_ratio: { value: number; interpretation: string; status: string; benchmark: string };
    quick_ratio: { value: number; interpretation: string; status: string; benchmark: string };
    cash_ratio: { value: number; interpretation: string; status: string; benchmark: string };
    working_capital: { value: number; interpretation: string; status: string };
  };
  solvency_ratios: {
    debt_to_equity: { value: number; interpretation: string; status: string; benchmark: string };
    debt_to_assets: { value: number; interpretation: string; status: string; benchmark: string };
    equity_ratio: { value: number; interpretation: string; status: string; benchmark: string };
  };
  efficiency_ratios: {
    receivables_turnover: { value: number; days: number; interpretation: string; status: string; benchmark: string };
    payables_turnover: { value: number; days: number; interpretation: string; status: string; benchmark: string };
    inventory_turnover: { value: number; days: number; interpretation: string; status: string; benchmark: string };
    asset_turnover: { value: number; interpretation: string; status: string; benchmark: string };
    cash_conversion_cycle: { value: number; interpretation: string; status: string; benchmark: string };
  };
  profitability_ratios: {
    gross_margin: { value: number; interpretation: string; status: string; benchmark: string };
    operating_margin: { value: number; interpretation: string; status: string; benchmark: string };
    net_margin: { value: number; interpretation: string; status: string; benchmark: string };
    return_on_assets: { value: number; interpretation: string; status: string; benchmark: string };
    return_on_equity: { value: number; interpretation: string; status: string; benchmark: string };
  };
  components: {
    current_assets: number;
    current_liabilities: number;
    total_assets: number;
    total_liabilities: number;
    shareholders_equity: number;
    revenue: number;
    cogs: number;
    gross_profit: number;
    operating_income: number;
    net_income: number;
    cash: number;
    receivables: number;
    inventory: number;
    payables: number;
  };
}

// =============================================================================
// ACCOUNTS PAYABLE & RECEIVABLE
// =============================================================================

export interface AccountingPayable {
  supplier_id: number;
  supplier_name: string;
  total_payable: number;
  current: number;
  overdue_1_30: number;
  overdue_31_60: number;
  overdue_61_90: number;
  overdue_over_90: number;
  invoice_count: number;
  oldest_invoice_date?: string | null;
  currency?: string | null;
}

export interface AccountingPayableResponse {
  total_payable: number;
  total_invoices?: number;
  aging?: {
    current: number;
    '1_30': number;
    '31_60': number;
    '61_90': number;
    over_90: number;
  };
  suppliers?: AccountingPayable[];
  currency?: string;
  items?: AccountingPayable[];
  data?: AccountingPayable[];
  total?: number;
}

export interface AccountingReceivable {
  customer_id: number;
  customer_name: string;
  total_receivable: number;
  current: number;
  overdue_1_30: number;
  overdue_31_60: number;
  overdue_61_90: number;
  overdue_over_90: number;
  invoice_count: number;
  oldest_invoice_date?: string | null;
  currency?: string | null;
}

export interface AccountingReceivableResponse {
  total_receivable: number;
  total_invoices?: number;
  aging?: {
    current: number;
    '1_30': number;
    '31_60': number;
    '61_90': number;
    over_90: number;
  };
  customers?: AccountingReceivable[];
  currency?: string;
}

export interface AccountingOutstandingSummary {
  total?: number;
  top?: Array<{
    id?: number | string;
    name?: string;
    amount?: number;
    currency?: string | null;
  }>;
  currency?: string | null;
}

// =============================================================================
// SUPPLIERS
// =============================================================================

export interface AccountingSupplier {
  id: number;
  name: string;
  supplier_name?: string;
  code?: string | null;
  supplier_code?: string | null;
  supplier_type?: string | null;
  supplier_group?: string | null;
  country?: string | null;
  default_currency?: string | null;
  payment_terms?: string | null;
  tax_id?: string | null;
  email?: string | null;
  phone?: string | null;
  is_internal?: boolean;
  is_active?: boolean;
  disabled?: boolean;
  total_outstanding?: number;
  total_invoices?: number;
  total_purchases?: number;
  outstanding_balance?: number;
  balance?: number;
  status?: string | null;
  banks?: Array<{
    bank_name?: string | null;
    account_number?: string | null;
    account_name?: string | null;
    currency?: string | null;
  }>;
  items?: Array<{
    item_code?: string | null;
    item_name?: string | null;
    item_group?: string | null;
    description?: string | null;
  }>;
}

export interface AccountingSupplierListResponse {
  suppliers: AccountingSupplier[];
  total: number;
  limit: number;
  offset: number;
  active?: number;
  by_status?: Record<string, number>;
  total_outstanding?: number;
  outstanding?: number;
  total_purchases?: number;
  total_invoices?: number;
  currency?: string;
}

// =============================================================================
// BANK ACCOUNTS & TRANSACTIONS
// =============================================================================

export interface AccountingBankAccount {
  id: number;
  name: string;
  account_name: string;
  bank?: string | null;
  account_number?: string | null;
  account_type?: string | null;
  currency?: string | null;
  balance?: number;
  is_default?: boolean;
  is_company_account?: boolean;
  last_integration_date?: string | null;
}

export interface AccountingBankAccountListResponse {
  accounts: AccountingBankAccount[];
  total: number;
}

export interface AccountingBankTransaction {
  id: number;
  erpnext_id?: string | null;
  account: string;
  company?: string | null;
  status: string;
  amount: number;
  currency?: string | null;
  transaction_date: string | null;
  description?: string | null;
  reference?: string | null;
  reference_number?: string | null;
  transaction_id?: string | null;
  transaction_type?: string | null;
  deposit?: number | null;
  withdrawal?: number | null;
  allocated_amount?: number | null;
  unallocated_amount?: number | null;
  party_type?: string | null;
  party?: string | null;
  bank_party_name?: string | null;
  bank_party_account_number?: string | null;
  bank_party_iban?: string | null;
  docstatus?: number | null;
}

export interface AccountingBankTransactionListResponse {
  transactions: AccountingBankTransaction[];
  total: number;
  page: number;
  page_size: number;
}

export interface AccountingBankTransactionPayment {
  id?: number;
  erpnext_id?: string | null;
  payment_document?: string | null;
  payment_entry?: string | null;
  allocated_amount?: number | null;
  idx?: number | null;
}

export interface AccountingBankTransactionDetail extends AccountingBankTransaction {
  payments?: AccountingBankTransactionPayment[];
}

export interface BankTransactionCreatePayload {
  account: string;
  transaction_date: string;
  amount: number;
  transaction_type: 'deposit' | 'withdrawal';
  description?: string;
  reference_number?: string;
  party_type?: 'Customer' | 'Supplier' | null;
  party?: string;
  currency?: string;
}

export interface BankTransactionCreateResponse {
  id: number;
  erpnext_id?: string;
  status: string;
  message?: string;
}

export interface BankTransactionImportResponse {
  imported_count: number;
  skipped_count: number;
  errors: Array<{ row: number; error: string }>;
  transaction_ids: number[];
}

export interface ReconciliationSuggestion {
  document_type: string;
  document_id: number | string;
  document_name: string;
  party: string;
  party_name: string;
  outstanding_amount: number;
  due_date: string;
  posting_date: string;
  match_score: number;
  match_reasons: string[];
}

export interface BankTransactionSuggestionsResponse {
  transaction_amount: number;
  unallocated_amount: number;
  suggestions: ReconciliationSuggestion[];
}

export interface ReconcilePayload {
  allocations: Array<{
    document_type: string;
    document_id: number | string;
    allocated_amount: number;
  }>;
  create_payment_entry?: boolean;
}

export interface ReconcileResponse {
  success: boolean;
  allocated_amount: number;
  remaining_unallocated: number;
  payment_entry_id?: string;
  allocations: Array<{
    document_type: string;
    document_id: string;
    allocated_amount: number;
  }>;
}

// =============================================================================
// PURCHASE INVOICES (Accounting View)
// =============================================================================

export interface AccountingPurchaseInvoice {
  id: number;
  invoice_number: string | null;
  supplier_id: number | null;
  supplier_name?: string | null;
  status: string;
  total_amount: number;
  balance?: number | null;
  currency?: string | null;
  invoice_date: string | null;
  due_date: string | null;
  description?: string | null;
}

export interface AccountingPurchaseInvoiceDetail extends AccountingPurchaseInvoice {
  lines?: Array<{
    item?: string | null;
    description?: string | null;
    quantity?: number;
    rate?: number;
    amount?: number;
  }>;
  payments?: Array<{
    id: number;
    amount: number;
    status: string;
    payment_date: string | null;
    method?: string | null;
  }>;
}

export interface AccountingPurchaseInvoiceListResponse {
  purchase_invoices: AccountingPurchaseInvoice[];
  total: number;
  page: number;
  page_size: number;
}

// =============================================================================
// FISCAL YEARS & COST CENTERS
// =============================================================================

export interface AccountingFiscalYear {
  id: number;
  name: string;
  year_start_date: string;
  year_end_date: string;
  is_closed: boolean;
  disabled: boolean;
}

export interface AccountingFiscalYearListResponse {
  fiscal_years: AccountingFiscalYear[];
  current_fiscal_year?: AccountingFiscalYear;
  total: number;
}

export interface AccountingCostCenter {
  id: number;
  name: string;
  cost_center_name: string;
  parent_cost_center?: string | null;
  is_group: boolean;
  disabled: boolean;
  company?: string | null;
}

export interface AccountingCostCenterListResponse {
  cost_centers: AccountingCostCenter[];
  total: number;
}

// =============================================================================
// TAX TEMPLATES & SUMMARIES
// =============================================================================

export interface AccountingTaxCategory {
  id?: number;
  name?: string;
  description?: string | null;
  rate?: number | null;
  is_withholding?: boolean;
}

export interface AccountingTaxTemplate {
  id?: number;
  name?: string;
  type?: string | null;
  description?: string | null;
  rate?: number | null;
  account?: string | null;
}

export interface AccountingTaxSummary {
  total?: number;
  period?: { start?: string; end?: string };
  by_account?: Array<{
    account: string;
    account_name?: string | null;
    amount: number;
  }>;
}

// =============================================================================
// NIGERIAN TAX MODULE TYPES
// =============================================================================

export type NigerianTaxType = 'VAT' | 'WHT' | 'PAYE' | 'CIT' | 'STAMP_DUTY' | 'CAPITAL_GAINS';
export type TaxJurisdiction = 'FEDERAL' | 'STATE' | 'LOCAL';
export type WHTPaymentType = 'DIVIDEND' | 'INTEREST' | 'RENT' | 'ROYALTY' | 'PROFESSIONAL' | 'CONTRACT' | 'DIRECTOR_FEE' | 'COMMISSION' | 'OTHER';
export type CITCompanySize = 'SMALL' | 'MEDIUM' | 'LARGE';
export type VATTransactionType = 'OUTPUT' | 'INPUT';
export type EInvoiceStatus = 'DRAFT' | 'VALIDATED' | 'SUBMITTED' | 'ACCEPTED' | 'REJECTED';
export type PAYEFilingFrequency = 'MONTHLY' | 'QUARTERLY';

export interface TaxSettings {
  id: number;
  company: string;
  tin: string | null;
  vat_registration_number: string | null;
  is_vat_registered: boolean;
  vat_filing_frequency: 'MONTHLY';
  wht_auto_deduct: boolean;
  paye_filing_frequency: PAYEFilingFrequency | string;
  cit_company_size: CITCompanySize;
  fiscal_year_start_month: number;
  einvoice_enabled: boolean;
  firs_api_key: string | null;
  created_at: string;
  updated_at: string;
  company_tin?: string | null;
  company_name?: string | null;
  rc_number?: string | null;
  tax_office?: string | null;
  vat_registered?: boolean;
  default_vat_rate?: number;
  fiscal_year_end_month?: number;
  auto_calculate_wht?: boolean;
  einvoice_api_key?: string | null;
}

export interface TaxDashboard {
  period: string;
  vat_summary: {
    output_vat: number;
    input_vat: number;
    net_vat: number;
    transactions_count: number;
  };
  wht_summary: {
    total_deducted: number;
    pending_remittance: number;
    transactions_count: number;
  };
  paye_summary: {
    total_paye: number;
    employees_count: number;
    avg_tax_rate: number;
  };
  cit_summary: {
    estimated_liability: number;
    year: number;
    company_size: CITCompanySize;
  };
  upcoming_deadlines: FilingDeadline[];
  overdue_filings: FilingDeadline[];
}

export interface VATTransaction {
  id: number;
  company: string;
  transaction_type: VATTransactionType;
  invoice_id: string | null;
  party_name: string;
  party_tin: string | null;
  transaction_date: string;
  gross_amount: number;
  vat_amount: number;
  net_amount: number;
  vat_rate: number;
  description: string | null;
  period: string;
  is_exempt: boolean;
  exemption_reason: string | null;
  created_at: string;
}

export interface VATTransactionsResponse {
  transactions: VATTransaction[];
  total: number;
  page: number;
  page_size: number;
}

export interface VATOutputPayload {
  invoice_id?: string;
  party_name: string;
  party_tin?: string;
  transaction_date: string;
  gross_amount: number;
  description?: string;
  is_exempt?: boolean;
  exemption_reason?: string;
}

export interface VATInputPayload {
  invoice_id?: string;
  party_name: string;
  party_tin?: string;
  transaction_date: string;
  gross_amount: number;
  vat_amount: number;
  description?: string;
}

export interface VATSummary {
  period: string;
  output_vat: number;
  input_vat: number;
  net_vat: number;
  output_count: number;
  input_count: number;
  exempt_amount: number;
}

export interface VATFilingPrep {
  period: string;
  filing_deadline: string;
  summary: VATSummary;
  output_transactions: VATTransaction[];
  input_transactions: VATTransaction[];
  is_complete: boolean;
  missing_tins: string[];
}

export interface WHTTransaction {
  id: number;
  company: string;
  supplier_id: string | null;
  supplier_name: string;
  supplier_tin: string | null;
  payment_type: WHTPaymentType;
  gross_amount: number;
  wht_rate: number;
  wht_amount: number;
  net_payment: number;
  transaction_date: string;
  invoice_reference: string | null;
  period: string;
  is_remitted: boolean;
  remittance_date: string | null;
  certificate_id: number | null;
  has_tin: boolean;
  penalty_rate: number;
  created_at: string;
}

export interface WHTTransactionsResponse {
  transactions: WHTTransaction[];
  total: number;
  page: number;
  page_size: number;
}

export interface WHTDeductPayload {
  supplier_id?: string;
  supplier_name: string;
  supplier_tin?: string;
  payment_type: WHTPaymentType;
  gross_amount: number;
  transaction_date: string;
  invoice_reference?: string;
}

export interface WHTSupplierSummary {
  supplier_id: string;
  supplier_name: string;
  supplier_tin: string | null;
  total_deducted: number;
  total_transactions: number;
  certificates_issued: number;
  pending_certificates: number;
}

export interface WHTRemittanceDue {
  period: string;
  deadline: string;
  total_deducted: number;
  transaction_count: number;
  is_overdue: boolean;
  days_until_due: number;
}

export interface WHTCertificate {
  id: number;
  company: string;
  certificate_number: string;
  supplier_id: string | null;
  supplier_name: string;
  supplier_tin: string | null;
  period_start: string;
  period_end: string;
  total_gross: number;
  total_wht: number;
  transaction_count: number;
  issued_date: string;
  created_at: string;
}

export interface WHTCertificatePayload {
  supplier_id?: string;
  supplier_name: string;
  period_start: string;
  period_end: string;
  transaction_ids?: number[];
}

export interface PAYECalculation {
  id: number;
  company: string;
  employee_id: string;
  employee_name: string;
  period: string;
  gross_income: number;
  pension_contribution: number;
  nhf_contribution: number;
  nhis_contribution: number;
  voluntary_contribution: number;
  consolidated_relief: number;
  taxable_income: number;
  paye_amount: number;
  effective_rate: number;
  tax_bands: Array<{ band: string; rate: number; amount: number; tax: number }>;
  created_at: string;
}

export interface PAYECalculationsResponse {
  calculations: PAYECalculation[];
  total: number;
  page: number;
  page_size: number;
}

export interface PAYECalculatePayload {
  employee_id: string;
  employee_name: string;
  gross_income: number;
  pension_contribution?: number;
  nhf_contribution?: number;
  nhis_contribution?: number;
  voluntary_contribution?: number;
  period?: string;
}

export interface PAYESummary {
  period: string;
  total_paye: number;
  total_gross_income: number;
  employees_count: number;
  avg_tax_rate: number;
  total_relief: number;
}

export interface CITAssessment {
  id: number;
  company: string;
  assessment_year: number;
  year?: number;
  company_size: CITCompanySize;
  turnover: number;
  assessable_profit: number;
  profit_before_tax?: number;
  taxable_profit?: number;
  cit_rate: number;
  cit_amount: number;
  cit_liability?: number;
  education_tax_rate: number;
  education_tax_amount: number;
  total_tax: number;
  minimum_tax: number;
  tax_payable: number;
  status?: string;
  created_by?: string | null;
  created_at: string;
}

export interface CITAssessmentsResponse {
  assessments: CITAssessment[];
  total: number;
  page: number;
  page_size: number;
}

export interface CITAssessmentPayload {
  assessment_year: number;
  turnover: number;
  assessable_profit: number;
}

export interface CITComputation {
  year: number;
  company_size: CITCompanySize;
  turnover: number;
  assessable_profit: number;
  cit_rate: number;
  cit_amount: number;
  education_tax_rate: number;
  education_tax_amount: number;
  total_tax: number;
  minimum_tax: number;
  tax_payable: number;
  due_date: string;
  quarterly_installments: Array<{ quarter: number; amount: number; due_date: string }>;
}

export interface CITRateResult {
  company_size: CITCompanySize;
  turnover: number;
  cit_rate: number;
  education_tax_rate: number;
  effective_rate: number;
  minimum_tax_rate: number;
}

export interface FilingDeadline {
  id: number;
  tax_type: NigerianTaxType;
  period: string;
  deadline: string;
  description: string;
  is_filed: boolean;
  filed_date: string | null;
  is_overdue: boolean;
  days_until_due: number;
  penalty_rate: number | null;
}

export interface FilingCalendar {
  year: number;
  deadlines: FilingDeadline[];
  upcoming: FilingDeadline[];
  overdue: FilingDeadline[];
  filings?: FilingDeadline[];
}

export interface EInvoice {
  id: number;
  company: string;
  invoice_id: string;
  invoice_number: string;
  customer_name: string;
  customer_tin: string | null;
  invoice_date: string;
  due_date: string | null;
  subtotal: number;
  vat_amount: number;
  total: number;
  currency: string;
  status: EInvoiceStatus;
  ubl_xml: string | null;
  firs_reference: string | null;
  validation_errors: string[] | null;
  submitted_at: string | null;
  created_at: string;
}

export interface EInvoicesResponse {
  einvoices: EInvoice[];
  total: number;
  page: number;
  page_size: number;
}

export interface EInvoicePayload {
  invoice_id: string;
  customer_name: string;
  customer_tin?: string;
  invoice_date: string;
  due_date?: string;
  lines: Array<{
    description: string;
    quantity: number;
    unit_price: number;
    vat_rate?: number;
  }>;
}

export interface EInvoiceValidation {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
}

export interface EInvoiceUBL {
  invoice_id: number;
  ubl_xml: string;
}

// =============================================================================
// PARAM TYPES
// =============================================================================

export interface AccountingChartOfAccountsParams {
  account_type?: string;
  root_type?: string;
  is_group?: boolean;
  include_disabled?: boolean;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface AccountingAccountDetailParams {
  include_ledger?: boolean;
  start_date?: string;
  end_date?: string;
  limit?: number;
}

export interface AccountingGeneralLedgerParams {
  account?: string;
  party?: string;
  start_date?: string;
  end_date?: string;
  cost_center?: string;
  fiscal_year?: string;
  currency?: string;
  limit?: number;
  offset?: number;
}

export interface AccountingJournalEntryListParams {
  voucher_type?: string;
  party?: string;
  cost_center?: string;
  start_date?: string;
  end_date?: string;
  currency?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

export interface AccountingBankTransactionListParams {
  status?: string;
  account?: string;
  start_date?: string;
  end_date?: string;
  min_amount?: number;
  max_amount?: number;
  currency?: string;
  search?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  page?: number;
  page_size?: number;
}

export interface AccountingPurchaseInvoiceListParams {
  status?: string;
  supplier_id?: number;
  start_date?: string;
  end_date?: string;
  min_amount?: number;
  max_amount?: number;
  currency?: string;
  search?: string;
  sort_by?: string;
  sort_order?: 'asc' | 'desc';
  page?: number;
  page_size?: number;
}

export interface AccountingSupplierListParams {
  search?: string;
  status?: string;
  currency?: string;
  limit?: number;
  offset?: number;
}

// =============================================================================
// API OBJECT
// =============================================================================

export const accountingApi = {
  // Dashboard
  getDashboard: (currency?: string) =>
    fetchApi<AccountingDashboard>('/v1/accounting/dashboard', { params: { currency } }),

  // Chart of Accounts
  getChartOfAccounts: (accountType?: string, params?: AccountingChartOfAccountsParams) =>
    fetchApi<AccountingChartOfAccounts>('/v1/accounting/accounts', {
      params: { account_type: accountType, ...params },
    }),

  getAccountDetail: (id: number, params?: AccountingAccountDetailParams) =>
    fetchApi<AccountingAccountDetail>(`/v1/accounting/accounts/${id}`, {
      params: params ? ({ ...params } as Record<string, unknown>) : undefined,
    }),

  // Financial Statements
  getTrialBalance: (params?: { fiscal_year?: string; start_date?: string; end_date?: string; currency?: string; drill?: boolean }) =>
    fetchApi<AccountingTrialBalance>('/v1/accounting/trial-balance', { params }),

  getBalanceSheet: (params?: { fiscal_year?: string; as_of_date?: string; currency?: string; common_size?: boolean }) =>
    fetchApi<AccountingBalanceSheet>('/v1/accounting/balance-sheet', { params }),

  getIncomeStatement: (params?: {
    fiscal_year?: string;
    start_date?: string;
    end_date?: string;
    currency?: string;
    compare_start?: string;
    compare_end?: string;
    show_ytd?: boolean;
    common_size?: boolean;
    basis?: string;
  }) => fetchApi<AccountingIncomeStatement>('/v1/accounting/income-statement', { params }),

  getCashFlow: (params?: { start_date?: string; end_date?: string; currency?: string; fiscal_year?: string }) =>
    fetchApi<AccountingCashFlow>('/v1/accounting/cash-flow', { params }),

  getEquityStatement: (params?: { start_date?: string; end_date?: string; fiscal_year?: string; currency?: string }) =>
    fetchApi<AccountingEquityStatement>('/v1/accounting/equity-statement', { params }),

  getFinancialRatios: (params?: { as_of_date?: string; fiscal_year?: string }) =>
    fetchApi<AccountingFinancialRatios>('/v1/accounting/financial-ratios', { params }),

  // General Ledger
  getGeneralLedger: (params?: AccountingGeneralLedgerParams) =>
    fetchApi<AccountingGeneralLedgerResponse>('/v1/accounting/general-ledger', {
      params: params ? ({ ...params } as Record<string, unknown>) : undefined,
    }),

  // Journal Entries
  getJournalEntries: (params?: AccountingJournalEntryListParams) =>
    fetchApi<AccountingJournalEntryListResponse>('/v1/accounting/journal-entries', {
      params: params ? ({ ...params } as Record<string, unknown>) : undefined,
    }),

  getJournalEntryDetail: (id: number) =>
    fetchApi<AccountingJournalEntry>(`/v1/accounting/journal-entries/${id}`),

  createJournalEntry: (body: AccountingJournalEntryPayload) =>
    fetchApi<AccountingJournalEntry>('/v1/accounting/journal-entries', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateJournalEntry: (id: number | string, body: Partial<AccountingJournalEntryPayload>) =>
    fetchApi<AccountingJournalEntry>(`/v1/accounting/journal-entries/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteJournalEntry: (id: number | string) =>
    fetchApi<void>(`/v1/accounting/journal-entries/${id}`, { method: 'DELETE' }),

  submitJournalEntry: (id: number | string) =>
    fetchApi<AccountingJournalEntry>(`/v1/accounting/journal-entries/${id}/submit`, { method: 'POST' }),

  approveJournalEntry: (id: number | string) =>
    fetchApi<AccountingJournalEntry>(`/v1/accounting/journal-entries/${id}/approve`, { method: 'POST' }),

  rejectJournalEntry: (id: number | string) =>
    fetchApi<AccountingJournalEntry>(`/v1/accounting/journal-entries/${id}/reject`, { method: 'POST' }),

  postJournalEntry: (id: number | string) =>
    fetchApi<AccountingJournalEntry>(`/v1/accounting/journal-entries/${id}/post`, { method: 'POST' }),

  // Accounts Payable & Receivable
  getPayables: (params?: {
    supplier_id?: number;
    currency?: string;
    as_of_date?: string;
    start_date?: string;
    end_date?: string;
    limit?: number;
    offset?: number;
  }) => fetchApi<AccountingPayableResponse>('/v1/accounting/accounts-payable', { params }),

  getReceivables: (params?: {
    customer_id?: number;
    currency?: string;
    as_of_date?: string;
    limit?: number;
    offset?: number;
  }) => fetchApi<AccountingReceivableResponse>('/v1/accounting/accounts-receivable', { params }),

  getReceivablesOutstanding: (params?: { currency?: string; top?: number }) =>
    fetchApi<AccountingOutstandingSummary>('/v1/accounting/receivables-outstanding', { params }),

  getPayablesOutstanding: (params?: { currency?: string; top?: number }) =>
    fetchApi<AccountingOutstandingSummary>('/v1/accounting/payables-outstanding', { params }),

  // Suppliers
  getSuppliers: (params?: AccountingSupplierListParams) =>
    fetchApi<AccountingSupplierListResponse>('/v1/accounting/suppliers', {
      params: params ? ({ ...params } as Record<string, unknown>) : undefined,
    }),

  // Bank Accounts
  getBankAccounts: () =>
    fetchApi<AccountingBankAccountListResponse>('/v1/accounting/bank-accounts'),

  // Bank Transactions
  getBankTransactions: (params?: AccountingBankTransactionListParams) =>
    fetchApi<AccountingBankTransactionListResponse>('/v1/accounting/bank-transactions', {
      params: params ? ({ ...params } as Record<string, unknown>) : undefined,
    }),

  getBankTransactionDetail: (id: number | string) =>
    fetchApi<AccountingBankTransactionDetail>(`/v1/accounting/bank-transactions/${id}`),

  createBankTransaction: (payload: BankTransactionCreatePayload) =>
    fetchApi<BankTransactionCreateResponse>('/v1/accounting/bank-transactions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  importBankTransactions: (formData: FormData) =>
    fetchApiFormData<BankTransactionImportResponse>('/v1/accounting/bank-transactions/import', formData),

  getBankTransactionSuggestions: (id: number | string, params?: { party_type?: string; limit?: number }) =>
    fetchApi<BankTransactionSuggestionsResponse>(`/v1/accounting/bank-transactions/${id}/suggestions`, { params }),

  reconcileBankTransaction: (id: number | string, payload: ReconcilePayload) =>
    fetchApi<ReconcileResponse>(`/v1/accounting/bank-transactions/${id}/allocate`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // Purchase Invoices (Accounting View)
  getPurchaseInvoices: (params?: AccountingPurchaseInvoiceListParams) =>
    fetchApi<AccountingPurchaseInvoiceListResponse>('/v1/accounting/purchase-invoices', {
      params: params ? ({ ...params } as Record<string, unknown>) : undefined,
    }),

  getPurchaseInvoiceDetail: (id: number, currency?: string) =>
    fetchApi<AccountingPurchaseInvoiceDetail>(`/v1/accounting/purchase-invoices/${id}`, { params: { currency } }),

  // Fiscal Years & Cost Centers
  getFiscalYears: () =>
    fetchApi<AccountingFiscalYearListResponse>('/v1/accounting/fiscal-years'),

  getCostCenters: () =>
    fetchApi<AccountingCostCenterListResponse>('/v1/accounting/cost-centers'),

  // Tax Templates & Summaries
  getTaxCategories: () =>
    fetchApi<{ tax_categories: AccountingTaxCategory[] }>('/v1/accounting/tax-categories'),

  getSalesTaxTemplates: () =>
    fetchApi<{ sales_tax_templates: AccountingTaxTemplate[] }>('/v1/accounting/sales-tax-templates'),

  getPurchaseTaxTemplates: () =>
    fetchApi<{ purchase_tax_templates: AccountingTaxTemplate[] }>('/v1/accounting/purchase-tax-templates'),

  getItemTaxTemplates: () =>
    fetchApi<{ item_tax_templates: AccountingTaxTemplate[] }>('/v1/accounting/item-tax-templates'),

  getTaxRules: () =>
    fetchApi<{ tax_rules: AccountingTaxTemplate[] }>('/v1/accounting/tax-rules'),

  getTaxPayable: (params?: { start_date?: string; end_date?: string; currency?: string }) =>
    fetchApi<AccountingTaxSummary>('/v1/accounting/tax-payable', { params }),

  getTaxReceivable: (params?: { start_date?: string; end_date?: string; currency?: string }) =>
    fetchApi<AccountingTaxSummary>('/v1/accounting/tax-receivable', { params }),

  // Nigerian Tax Module
  getTaxDashboard: () =>
    fetchApi<TaxDashboard>('/tax/dashboard'),

  getTaxSettings: () =>
    fetchApi<TaxSettings>('/tax/settings'),

  updateTaxSettings: (payload: Partial<TaxSettings>) =>
    fetchApi<TaxSettings>('/tax/settings', {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),

  // VAT
  getVATTransactions: (params?: { period?: string; type?: string; page?: number; page_size?: number }) =>
    fetchApi<VATTransactionsResponse>('/tax/vat/transactions', { params }),

  recordVATOutput: (payload: VATOutputPayload) =>
    fetchApi<VATTransaction>('/tax/vat/record-output', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  recordVATInput: (payload: VATInputPayload) =>
    fetchApi<VATTransaction>('/tax/vat/record-input', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getVATSummary: (period: string) =>
    fetchApi<VATSummary>(`/tax/vat/summary/${period}`),

  getVATFilingPrep: (period: string) =>
    fetchApi<VATFilingPrep>(`/tax/vat/filing-prep/${period}`),

  // WHT
  getWHTTransactions: (params?: { period?: string; supplier_id?: string; page?: number; page_size?: number }) =>
    fetchApi<WHTTransactionsResponse>('/tax/wht/transactions', { params }),

  deductWHT: (payload: WHTDeductPayload) =>
    fetchApi<WHTTransaction>('/tax/wht/deduct', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getWHTSupplierSummary: (supplierId: string | number) =>
    fetchApi<WHTSupplierSummary>(`/tax/wht/supplier/${supplierId}/summary`),

  getWHTRemittanceDue: () =>
    fetchApi<WHTRemittanceDue>('/tax/wht/remittance-due'),

  // PAYE
  getPAYECalculations: (params?: { period?: string; employee_id?: string; page?: number; page_size?: number }) =>
    fetchApi<PAYECalculationsResponse>('/tax/paye/calculations', { params }),

  calculatePAYE: (payload: PAYECalculatePayload) =>
    fetchApi<PAYECalculation>('/tax/paye/calculate', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getPAYESummary: (period: string) =>
    fetchApi<PAYESummary>(`/tax/paye/summary/${period}`),

  // CIT
  getCITAssessments: (params?: { year?: number; page?: number; page_size?: number }) =>
    fetchApi<CITAssessmentsResponse>('/tax/cit/assessments', { params }),

  createCITAssessment: (payload: CITAssessmentPayload) =>
    fetchApi<CITAssessment>('/tax/cit/create-assessment', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getCITComputation: (year: number) =>
    fetchApi<CITComputation>(`/tax/cit/${year}/computation`),

  getCITRateCalculator: (params: { turnover: number; profit: number }) =>
    fetchApi<CITRateResult>('/tax/cit/rate-calculator', { params }),

  // Filing Calendar
  getFilingCalendar: (params?: { year?: number; tax_type?: string }) =>
    fetchApi<FilingCalendar>('/tax/filing/calendar', { params }),

  getUpcomingFilings: (params?: { days?: number }) =>
    fetchApi<FilingDeadline[]>('/tax/filing/upcoming', { params }),

  getOverdueFilings: () =>
    fetchApi<FilingDeadline[]>('/tax/filing/overdue'),

  // WHT Certificates
  generateWHTCertificate: (payload: WHTCertificatePayload) =>
    fetchApi<WHTCertificate>('/tax/certificates/wht/generate', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getWHTCertificate: (id: number | string) =>
    fetchApi<WHTCertificate>(`/tax/certificates/wht/${id}`),

  // E-Invoice
  getEInvoices: (params?: { status?: string; page?: number; page_size?: number }) =>
    fetchApi<EInvoicesResponse>('/tax/einvoice', { params }),

  createEInvoice: (payload: EInvoicePayload) =>
    fetchApi<EInvoice>('/tax/einvoice/create', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  validateEInvoice: (id: number | string) =>
    fetchApi<EInvoiceValidation>(`/tax/einvoice/${id}/validate`, {
      method: 'POST',
    }),

  getEInvoiceUBL: (id: number | string) =>
    fetchApi<EInvoiceUBL>(`/tax/einvoice/${id}/ubl`),
};
