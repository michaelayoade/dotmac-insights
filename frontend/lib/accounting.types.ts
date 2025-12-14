/**
 * TypeScript interfaces for the Accounting API.
 *
 * These interfaces match the Pydantic schemas in app/api/accounting/schemas.py
 * to ensure type safety between frontend and backend.
 *
 * Note: Monetary values use string type for precision (to match Decimal on backend).
 * Convert to number only when displaying or calculating.
 */

// =============================================================================
// Enums
// =============================================================================

export type RootType = 'asset' | 'liability' | 'equity' | 'income' | 'expense';

export type ApprovalMode = 'any' | 'all' | 'sequential';

export type TaxType = 'vat' | 'wht' | 'cit' | 'paye' | 'other';

export type PeriodStatus = 'open' | 'soft_closed' | 'hard_closed';

export type ValidationSeverity = 'error' | 'warning';

export type NonCashTransactionType =
  | 'lease_inception'
  | 'debt_conversion'
  | 'asset_exchange'
  | 'barter'
  | 'share_based_payment'
  | 'other';

export type ClassificationBasis = 'by_nature' | 'by_function';

export type InterestDividendClassification = 'operating' | 'investing' | 'financing';

export type PaymentStatus = 'pending' | 'completed' | 'failed' | 'cancelled';

export type PaymentMethod =
  | 'cash'
  | 'bank_transfer'
  | 'check'
  | 'credit_card'
  | 'debit_card'
  | 'mobile_money'
  | 'other';

export type InvoiceStatus =
  | 'draft'
  | 'pending'
  | 'paid'
  | 'partially_paid'
  | 'overdue'
  | 'cancelled';

export type BillStatus =
  | 'draft'
  | 'pending'
  | 'paid'
  | 'partially_paid'
  | 'overdue'
  | 'cancelled';

export type CreditNoteStatus = 'draft' | 'issued' | 'applied' | 'cancelled';

export type DebitNoteStatus = 'draft' | 'issued' | 'applied' | 'cancelled';

export type SupplierPaymentStatus =
  | 'draft'
  | 'submitted'
  | 'approved'
  | 'posted'
  | 'cancelled';

// =============================================================================
// Validation Schemas
// =============================================================================

export interface ValidationIssue {
  code: string;
  message: string;
  field?: string;
  expected?: unknown;
  actual?: unknown;
}

export interface ValidationResult {
  is_valid: boolean;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
}

// =============================================================================
// FX and Currency
// =============================================================================

export interface FXMetadata {
  functional_currency: string;
  presentation_currency: string;
  is_same_currency: boolean;
  average_rate?: number;
  closing_rate?: number;
}

// =============================================================================
// EPS (IAS 33)
// =============================================================================

export interface DilutiveInstrument {
  instrument_type: string;
  shares_equivalent: number;
  dilutive_effect: number;
}

export interface EarningsPerShare {
  basic_eps?: number;
  diluted_eps?: number;
  weighted_average_shares_basic?: number;
  weighted_average_shares_diluted?: number;
  dilutive_instruments: DilutiveInstrument[];
  note?: string;
}

// =============================================================================
// Tax Reconciliation (IAS 12)
// =============================================================================

export interface TaxReconciliationItem {
  description: string;
  amount: number;
  rate_effect?: number;
}

export interface TaxReconciliation {
  profit_before_tax: number;
  statutory_rate: number;
  tax_at_statutory_rate: number;
  reconciling_items: TaxReconciliationItem[];
  effective_tax_expense: number;
  effective_tax_rate: number;
}

// =============================================================================
// Non-Cash Transaction (IAS 7)
// =============================================================================

export interface NonCashTransaction {
  transaction_type: NonCashTransactionType;
  description: string;
  amount: number;
  debit_account?: string;
  credit_account?: string;
}

// =============================================================================
// Cash Flow Classification Policy (IAS 7)
// =============================================================================

export interface CashFlowClassificationPolicy {
  interest_paid: InterestDividendClassification;
  interest_received: InterestDividendClassification;
  dividends_paid: InterestDividendClassification;
  dividends_received: InterestDividendClassification;
  taxes_paid: InterestDividendClassification;
}

// =============================================================================
// OCI Components (IAS 1)
// =============================================================================

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

// =============================================================================
// Base/Common
// =============================================================================

export interface PaginatedResponse {
  total: number;
  limit: number;
  offset: number;
}

export interface DateRangeParams {
  start_date?: string;
  end_date?: string;
}

export interface PeriodInfo {
  start_date?: string;
  end_date?: string;
}

export interface ComparativePeriod {
  start_date?: string;
  end_date?: string;
  as_of_date?: string;
}

// =============================================================================
// Account
// =============================================================================

export interface AccountBase {
  account_name: string;
  account_number?: string;
  root_type: RootType;
  account_type?: string;
  parent_account?: string;
  is_group: boolean;
}

export interface AccountCreate extends AccountBase {
  company?: string;
}

export interface AccountUpdate {
  account_name?: string;
  account_number?: string;
  account_type?: string;
  disabled?: boolean;
}

export interface Account {
  id: number;
  erpnext_id?: string;
  name: string;
  account_number?: string;
  parent_account?: string;
  root_type?: string;
  account_type?: string;
  is_group: boolean;
  disabled: boolean;
}

export interface AccountListResponse extends PaginatedResponse {
  accounts: Account[];
}

// =============================================================================
// Journal Entry
// =============================================================================

export interface JournalEntryLineCreate {
  account: string;
  /** Use string for Decimal precision */
  debit: string;
  /** Use string for Decimal precision */
  credit: string;
  party_type?: string;
  party?: string;
  cost_center?: string;
}

export interface JournalEntryCreate {
  posting_date: string;
  voucher_type?: string;
  company: string;
  user_remark?: string;
  lines: JournalEntryLineCreate[];
}

export interface JournalEntryUpdate {
  posting_date?: string;
  user_remark?: string;
  lines?: JournalEntryLineCreate[];
}

export interface JournalEntryLine {
  id: number;
  account: string;
  account_name?: string;
  debit: number;
  credit: number;
  party_type?: string;
  party?: string;
  cost_center?: string;
}

export interface JournalEntry {
  id: number;
  erpnext_id?: string;
  voucher_type: string;
  posting_date: string;
  company?: string;
  total_debit: number;
  total_credit: number;
  user_remark?: string;
  docstatus?: number;
  lines?: JournalEntryLine[];
}

export interface JournalEntryListResponse extends PaginatedResponse {
  entries: JournalEntry[];
}

// =============================================================================
// Supplier
// =============================================================================

export interface SupplierCreate {
  supplier_name: string;
  supplier_group?: string;
  supplier_type?: string;
  country?: string;
  default_currency?: string;
  tax_id?: string;
  email_id?: string;
  mobile_no?: string;
}

export interface SupplierUpdate {
  supplier_name?: string;
  supplier_group?: string;
  supplier_type?: string;
  country?: string;
  default_currency?: string;
  tax_id?: string;
  email_id?: string;
  mobile_no?: string;
  disabled?: boolean;
}

export interface Supplier {
  id: number;
  erpnext_id?: string;
  supplier_name: string;
  supplier_group?: string;
  supplier_type?: string;
  country?: string;
  default_currency?: string;
  tax_id?: string;
  email_id?: string;
  mobile_no?: string;
  disabled: boolean;
}

export interface SupplierListResponse extends PaginatedResponse {
  suppliers: Supplier[];
}

// =============================================================================
// Customer
// =============================================================================

export interface Customer {
  id: number;
  erpnext_id?: string;
  customer_name: string;
  customer_group?: string;
  customer_type?: string;
  territory?: string;
  default_currency?: string;
  tax_id?: string;
  email_id?: string;
  mobile_no?: string;
  credit_limit?: number;
  on_hold: boolean;
  disabled: boolean;
}

export interface CustomerListResponse extends PaginatedResponse {
  customers: Customer[];
}

// =============================================================================
// GL Entry
// =============================================================================

export interface GLEntry {
  id: number;
  erpnext_id?: string;
  posting_date?: string;
  account?: string;
  account_name?: string;
  debit: number;
  credit: number;
  party_type?: string;
  party?: string;
  voucher_type?: string;
  voucher_no?: string;
  cost_center?: string;
  remarks?: string;
  is_cancelled: boolean;
}

export interface GLEntryListResponse extends PaginatedResponse {
  entries: GLEntry[];
}

// =============================================================================
// Invoice (AR)
// =============================================================================

export interface InvoiceLineCreate {
  description: string;
  quantity: number;
  unit_price: string;
  tax_rate?: number;
  account?: string;
  cost_center?: string;
}

export interface InvoiceCreate {
  customer_id: number;
  invoice_date: string;
  due_date?: string;
  currency?: string;
  line_items: InvoiceLineCreate[];
  invoice_number?: string;
  memo?: string;
  payment_terms_id?: number;
}

export interface InvoiceUpdate {
  invoice_date?: string;
  due_date?: string;
  memo?: string;
  status?: InvoiceStatus;
}

export interface InvoiceLine {
  id: number;
  description: string;
  quantity: number;
  unit_price: number;
  amount: number;
  tax_rate?: number;
  tax_amount?: number;
  net_amount: number;
  account?: string;
  cost_center?: string;
}

export interface Invoice {
  id: number;
  erpnext_id?: string;
  invoice_number?: string;
  customer_id: number;
  customer_name?: string;
  invoice_date: string;
  due_date?: string;
  currency: string;
  subtotal: number;
  tax_amount: number;
  total_amount: number;
  amount_paid: number;
  balance_due: number;
  status: InvoiceStatus;
  workflow_status?: string;
  docstatus: number;
  memo?: string;
  lines?: InvoiceLine[];
  base_currency?: string;
  conversion_rate?: number;
  base_amount?: number;
}

export interface InvoiceListResponse extends PaginatedResponse {
  invoices: Invoice[];
}

// =============================================================================
// Bill (AP / Purchase Invoice)
// =============================================================================

export interface BillLineCreate {
  description: string;
  quantity: number;
  unit_price: string;
  tax_rate?: number;
  account?: string;
  cost_center?: string;
}

export interface BillCreate {
  supplier_id: number;
  bill_date: string;
  due_date?: string;
  currency?: string;
  line_items: BillLineCreate[];
  bill_number?: string;
  memo?: string;
  payment_terms_id?: number;
}

export interface BillUpdate {
  bill_date?: string;
  due_date?: string;
  memo?: string;
  status?: BillStatus;
}

export interface BillLine {
  id: number;
  description: string;
  quantity: number;
  unit_price: number;
  amount: number;
  tax_rate?: number;
  tax_amount?: number;
  net_amount: number;
  account?: string;
  cost_center?: string;
}

export interface Bill {
  id: number;
  erpnext_id?: string;
  bill_number?: string;
  supplier_id: number;
  supplier_name?: string;
  bill_date: string;
  due_date?: string;
  currency: string;
  subtotal: number;
  tax_amount: number;
  grand_total: number;
  amount_paid: number;
  outstanding_amount: number;
  status: BillStatus;
  workflow_status?: string;
  docstatus: number;
  memo?: string;
  lines?: BillLine[];
  base_currency?: string;
  conversion_rate?: number;
  base_grand_total?: number;
}

export interface BillListResponse extends PaginatedResponse {
  bills: Bill[];
}

// =============================================================================
// Credit Note (AR)
// =============================================================================

export interface CreditNoteLineCreate {
  description: string;
  quantity: number;
  unit_price: string;
  tax_rate?: number;
}

export interface CreditNoteCreate {
  customer_id: number;
  issue_date: string;
  currency?: string;
  line_items: CreditNoteLineCreate[];
  credit_note_number?: string;
  original_invoice_id?: number;
  reason?: string;
  memo?: string;
}

export interface CreditNote {
  id: number;
  erpnext_id?: string;
  credit_note_number?: string;
  customer_id: number;
  customer_name?: string;
  issue_date: string;
  currency: string;
  amount: number;
  tax_amount?: number;
  total_amount: number;
  amount_applied: number;
  amount_remaining: number;
  status: CreditNoteStatus;
  workflow_status?: string;
  docstatus: number;
  original_invoice_id?: number;
  reason?: string;
  memo?: string;
  base_currency?: string;
  conversion_rate?: number;
  base_amount?: number;
}

export interface CreditNoteListResponse extends PaginatedResponse {
  credit_notes: CreditNote[];
}

// =============================================================================
// Debit Note (AP)
// =============================================================================

export interface DebitNoteLineCreate {
  description: string;
  quantity: number;
  unit_price: string;
  tax_rate?: number;
}

export interface DebitNoteCreate {
  supplier_id: number;
  issue_date: string;
  currency?: string;
  line_items: DebitNoteLineCreate[];
  debit_note_number?: string;
  original_bill_id?: number;
  reason?: string;
  memo?: string;
}

export interface DebitNote {
  id: number;
  erpnext_id?: string;
  debit_note_number?: string;
  supplier_id: number;
  supplier_name?: string;
  posting_date: string;
  currency: string;
  total_amount: number;
  outstanding_amount: number;
  status: DebitNoteStatus;
  workflow_status?: string;
  docstatus: number;
  purchase_invoice_id?: number;
  reason?: string;
  remarks?: string;
  base_currency?: string;
  conversion_rate?: number;
  base_amount?: number;
}

export interface DebitNoteListResponse extends PaginatedResponse {
  debit_notes: DebitNote[];
}

// =============================================================================
// Payment (AR - Customer Payment)
// =============================================================================

export interface PaymentAllocationCreate {
  document_type: 'invoice' | 'credit_note';
  document_id: number;
  allocated_amount: string;
  discount_amount?: string;
  write_off_amount?: string;
  discount_type?: string;
  discount_account?: string;
  write_off_account?: string;
  write_off_reason?: string;
}

export interface PaymentCreate {
  customer_id: number;
  payment_date: string;
  amount: string;
  currency?: string;
  payment_method?: PaymentMethod;
  receipt_number?: string;
  transaction_reference?: string;
  notes?: string;
  conversion_rate?: number;
  bank_account_id?: number;
  allocations?: PaymentAllocationCreate[];
}

export interface PaymentUpdate {
  payment_date?: string;
  amount?: string;
  payment_method?: PaymentMethod;
  transaction_reference?: string;
  notes?: string;
  conversion_rate?: number;
}

export interface PaymentAllocation {
  id: number;
  document_type: string;
  document_id: number;
  allocated_amount: number;
  discount_amount?: number;
  write_off_amount?: number;
  exchange_gain_loss?: number;
}

export interface Payment {
  id: number;
  receipt_number?: string;
  customer_id: number;
  customer_name?: string;
  invoice_id?: number;
  payment_date: string;
  amount: number;
  currency: string;
  base_currency?: string;
  conversion_rate?: number;
  base_amount?: number;
  payment_method?: PaymentMethod;
  status: PaymentStatus;
  workflow_status?: string;
  docstatus: number;
  transaction_reference?: string;
  gateway_reference?: string;
  notes?: string;
  total_allocated?: number;
  unallocated_amount?: number;
  created_at?: string;
  allocations?: PaymentAllocation[];
}

export interface PaymentListResponse extends PaginatedResponse {
  payments: Payment[];
}

// =============================================================================
// Supplier Payment (AP)
// =============================================================================

export interface SupplierPaymentAllocationCreate {
  document_type: 'bill' | 'debit_note';
  document_id: number;
  allocated_amount: string;
  discount_amount?: string;
  write_off_amount?: string;
  withholding_tax_amount?: string;
}

export interface SupplierPaymentCreate {
  supplier_id: number;
  payment_date: string;
  paid_amount: string;
  currency?: string;
  mode_of_payment?: string;
  bank_account_id?: number;
  reference_number?: string;
  reference_date?: string;
  remarks?: string;
  conversion_rate?: number;
  allocations?: SupplierPaymentAllocationCreate[];
}

export interface SupplierPaymentUpdate {
  payment_date?: string;
  paid_amount?: string;
  mode_of_payment?: string;
  reference_number?: string;
  remarks?: string;
  conversion_rate?: number;
}

export interface SupplierPayment {
  id: number;
  payment_number: string;
  supplier_id: number;
  supplier_name?: string;
  payment_date: string;
  posting_date?: string;
  mode_of_payment?: string;
  currency: string;
  paid_amount: number;
  conversion_rate?: number;
  base_paid_amount?: number;
  total_allocated?: number;
  unallocated_amount?: number;
  total_discount?: number;
  total_write_off?: number;
  total_withholding_tax?: number;
  reference_number?: string;
  reference_date?: string;
  status: SupplierPaymentStatus;
  workflow_status?: string;
  docstatus: number;
  remarks?: string;
  allocations?: PaymentAllocation[];
}

export interface SupplierPaymentListResponse extends PaginatedResponse {
  payments: SupplierPayment[];
}

// =============================================================================
// Bank Transaction
// =============================================================================

export interface BankTransactionSplitCreate {
  amount: string;
  account: string;
  tax_code_id?: number;
  tax_amount?: string;
  memo?: string;
  cost_center?: string;
}

export interface BankTransactionCreate {
  bank_account_id: number;
  transaction_date: string;
  amount: string;
  transaction_type: 'credit' | 'debit';
  description?: string;
  payee_name?: string;
  payee_account?: string;
  reference_number?: string;
  statement_reference?: string;
  statement_line_no?: number;
  currency?: string;
  conversion_rate?: number;
  splits?: BankTransactionSplitCreate[];
}

export interface BankTransactionUpdate {
  description?: string;
  payee_name?: string;
  payee_account?: string;
  reference_number?: string;
  category?: string;
}

export interface BankTransactionSplit {
  id: number;
  amount: number;
  base_amount?: number;
  account: string;
  account_name?: string;
  tax_code_id?: number;
  tax_amount?: number;
  memo?: string;
  cost_center?: string;
}

export interface BankTransaction {
  id: number;
  erpnext_id?: string;
  bank_account_id: number;
  bank_account_name?: string;
  transaction_date: string;
  amount: number;
  transaction_type: 'credit' | 'debit';
  description?: string;
  payee_name?: string;
  payee_account?: string;
  reference_number?: string;
  statement_reference?: string;
  statement_line_no?: number;
  currency: string;
  base_currency?: string;
  conversion_rate?: number;
  base_amount?: number;
  is_reconciled: boolean;
  reconciled_date?: string;
  is_manual_entry: boolean;
  workflow_status?: string;
  category?: string;
  matched_document_type?: string;
  matched_document_id?: number;
  splits?: BankTransactionSplit[];
}

export interface BankTransactionListResponse extends PaginatedResponse {
  transactions: BankTransaction[];
}

// =============================================================================
// Bank Account
// =============================================================================

export interface BankAccount {
  id: number;
  erpnext_id?: string;
  account_name: string;
  bank_name?: string;
  account_number?: string;
  account_type?: string;
  currency: string;
  gl_account?: string;
  gl_account_name?: string;
  is_default: boolean;
  is_active: boolean;
  opening_balance?: number;
  current_balance?: number;
}

export interface BankAccountListResponse extends PaginatedResponse {
  bank_accounts: BankAccount[];
}

// =============================================================================
// Tax Code
// =============================================================================

export interface TaxCodeCreate {
  code: string;
  name: string;
  rate: string;
  tax_type?: 'sales' | 'purchase' | 'both';
  is_tax_inclusive?: boolean;
  jurisdiction?: string;
  country?: string;
  rounding_method?: 'round' | 'floor' | 'ceil';
  account_head?: string;
  cost_center?: string;
  valid_from?: string;
  valid_to?: string;
}

export interface TaxCode {
  id: number;
  code: string;
  name: string;
  rate: number;
  tax_type: 'sales' | 'purchase' | 'both';
  is_tax_inclusive: boolean;
  jurisdiction?: string;
  country?: string;
  rounding_method: 'round' | 'floor' | 'ceil';
  account_head?: string;
  cost_center?: string;
  valid_from?: string;
  valid_to?: string;
  is_active: boolean;
}

export interface TaxCodeListResponse extends PaginatedResponse {
  tax_codes: TaxCode[];
}

// =============================================================================
// Payment Terms
// =============================================================================

export interface PaymentTermsScheduleCreate {
  credit_days?: number;
  credit_months?: number;
  day_of_month?: number;
  payment_percentage: string;
  discount_percentage?: string;
  discount_days?: number;
}

export interface PaymentTermsCreate {
  template_name: string;
  description?: string;
  schedules: PaymentTermsScheduleCreate[];
}

export interface PaymentTermsSchedule {
  id: number;
  credit_days?: number;
  credit_months?: number;
  day_of_month?: number;
  payment_percentage: number;
  discount_percentage?: number;
  discount_days?: number;
}

export interface PaymentTerms {
  id: number;
  template_name: string;
  description?: string;
  is_active: boolean;
  schedules: PaymentTermsSchedule[];
}

export interface PaymentTermsListResponse extends PaginatedResponse {
  payment_terms: PaymentTerms[];
}

// =============================================================================
// Workflow
// =============================================================================

export interface WorkflowStepCreate {
  step_order: number;
  step_name: string;
  role_required?: string;
  user_id?: number;
  approval_mode?: ApprovalMode;
  amount_threshold_min?: string;
  amount_threshold_max?: string;
  can_reject?: boolean;
  escalation_timeout_hours?: number;
  escalation_role?: string;
  escalation_user_id?: number;
}

export interface WorkflowCreate {
  name: string;
  doctype: string;
  is_active?: boolean;
}

export interface WorkflowUpdate {
  name?: string;
  is_active?: boolean;
}

export interface WorkflowStep {
  id: number;
  step_order: number;
  step_name: string;
  role_required?: string;
  user_id?: number;
  approval_mode: string;
  amount_threshold_min?: number;
  amount_threshold_max?: number;
  can_reject: boolean;
}

export interface Workflow {
  id: number;
  name: string;
  doctype: string;
  is_active: boolean;
  steps?: WorkflowStep[];
}

export interface WorkflowListResponse extends PaginatedResponse {
  workflows: Workflow[];
}

// =============================================================================
// Fiscal Period
// =============================================================================

export interface FiscalPeriodCreate {
  name: string;
  fiscal_year_id: number;
  period_start: string;
  period_end: string;
  status?: PeriodStatus;
}

export interface FiscalPeriod {
  id: number;
  name: string;
  fiscal_year_id: number;
  fiscal_year_name?: string;
  period_start: string;
  period_end: string;
  status: PeriodStatus;
  closing_journal_entry_id?: number;
  closed_by_id?: number;
  closed_at?: string;
}

export interface FiscalPeriodListResponse extends PaginatedResponse {
  periods: FiscalPeriod[];
}

// =============================================================================
// Tax Filing
// =============================================================================

export interface TaxFilingPeriodCreate {
  tax_type: TaxType;
  period_name: string;
  period_start: string;
  period_end: string;
  due_date: string;
  tax_base?: string;
  tax_amount?: string;
}

export interface TaxPaymentCreate {
  payment_date: string;
  amount: string;
  payment_reference?: string;
  payment_method?: string;
  bank_account?: string;
}

export interface TaxFilingPeriod {
  id: number;
  tax_type: TaxType;
  period_name: string;
  period_start: string;
  period_end: string;
  due_date: string;
  tax_base: number;
  tax_amount: number;
  amount_paid: number;
  status: string;
  filed_date?: string;
}

// =============================================================================
// Bank Reconciliation
// =============================================================================

export interface BankReconciliationStartRequest {
  statement_date: string;
  opening_balance: string;
  closing_balance: string;
}

export interface BankTransactionMatchRequest {
  bank_transaction_id: number;
  gl_entry_ids: number[];
}

export interface BankStatementImportResponse {
  imported: number;
  skipped: number;
  errors: string[];
}

// =============================================================================
// Dashboard
// =============================================================================

export interface DashboardSummary {
  total_assets: number;
  total_liabilities: number;
  total_equity: number;
  net_worth: number;
}

export interface DashboardPerformance {
  total_income: number;
  total_expenses: number;
  net_profit: number;
  profit_margin: number;
}

export interface DashboardReceivablesPayables {
  total_receivable: number;
  total_payable: number;
  net_position: number;
}

export interface DashboardActivity {
  gl_entries_count: number;
  bank_transactions_count: number;
}

export interface DashboardResponse {
  period: PeriodInfo;
  summary: DashboardSummary;
  performance: DashboardPerformance;
  receivables_payables: DashboardReceivablesPayables;
  bank_balances: Record<string, unknown>[];
  activity: DashboardActivity;
}

// =============================================================================
// Receivables/Payables Aging
// =============================================================================

export interface AgingBucket {
  current: number;
  '1_30': number;
  '31_60': number;
  '61_90': number;
  over_90: number;
}

export interface CustomerAging {
  customer_id: number;
  customer_name: string;
  total_receivable: number;
  current: number;
  overdue_1_30: number;
  overdue_31_60: number;
  overdue_61_90: number;
  overdue_over_90: number;
  invoice_count: number;
  oldest_invoice_date?: string;
}

export interface ReceivablesAgingResponse {
  total_receivable: number;
  aging: AgingBucket;
  customers: CustomerAging[];
  total: number;
}

export interface SupplierAging {
  supplier_id: number;
  supplier_name: string;
  total_payable: number;
  current: number;
  overdue_1_30: number;
  overdue_31_60: number;
  overdue_61_90: number;
  overdue_over_90: number;
  bill_count: number;
  oldest_bill_date?: string;
}

export interface PayablesAgingResponse {
  total_payable: number;
  aging: AgingBucket;
  suppliers: SupplierAging[];
  total: number;
}

// =============================================================================
// Write-off/Waiver
// =============================================================================

export interface InvoiceWriteOffRequest {
  amount?: string;
  reason: string;
  write_off_account?: string;
}

export interface InvoiceWaiverRequest {
  waive_amount: string;
  reason: string;
}

// =============================================================================
// Credit Management
// =============================================================================

export interface CreditLimitUpdate {
  credit_limit: string;
  reason?: string;
}

export interface CreditHoldUpdate {
  on_hold: boolean;
  reason?: string;
}

export interface CustomerCreditStatus {
  customer_id: number;
  customer_name: string;
  credit_limit: number;
  current_balance: number;
  available_credit: number;
  on_hold: boolean;
  overdue_amount: number;
  oldest_overdue_days?: number;
}

// =============================================================================
// Dunning
// =============================================================================

export interface DunningSendRequest {
  invoice_ids: number[];
  dunning_level?: number;
  custom_message?: string;
}

export interface DunningHistory {
  id: number;
  invoice_id: number;
  level: number;
  sent_at: string;
  sent_by_id?: number;
  message?: string;
  response?: string;
}

// =============================================================================
// Accounting Controls
// =============================================================================

export interface AccountingControls {
  id: number;
  base_currency: string;
  backdating_days_allowed: number;
  future_posting_days_allowed: number;
  auto_voucher_numbering: boolean;
  voucher_prefix_format?: string;
  require_attachment_journal_entry: boolean;
  require_attachment_expense: boolean;
  require_attachment_payment: boolean;
  require_attachment_invoice: boolean;
  require_attachment_supplier_payment: boolean;
  require_attachment_purchase_invoice: boolean;
  require_attachment_credit_note: boolean;
  require_attachment_debit_note: boolean;
  require_attachment_bank_transaction: boolean;
  require_approval_journal_entry: boolean;
  require_approval_expense: boolean;
  require_approval_payment: boolean;
  require_approval_supplier_payment: boolean;
  require_approval_purchase_invoice: boolean;
  require_approval_credit_note: boolean;
  require_approval_debit_note: boolean;
  auto_create_fiscal_periods: boolean;
  default_period_type: string;
  retained_earnings_account?: string;
  fx_gain_account?: string;
  fx_loss_account?: string;
}

export interface AccountingControlsUpdate {
  backdating_days_allowed?: number;
  future_posting_days_allowed?: number;
  auto_voucher_numbering?: boolean;
  require_attachment_journal_entry?: boolean;
  require_attachment_expense?: boolean;
  require_attachment_payment?: boolean;
  require_attachment_invoice?: boolean;
  require_attachment_supplier_payment?: boolean;
  require_attachment_purchase_invoice?: boolean;
  require_attachment_credit_note?: boolean;
  require_attachment_debit_note?: boolean;
  require_attachment_bank_transaction?: boolean;
  require_approval_journal_entry?: boolean;
  require_approval_expense?: boolean;
  require_approval_payment?: boolean;
  require_approval_supplier_payment?: boolean;
  require_approval_purchase_invoice?: boolean;
  require_approval_credit_note?: boolean;
  require_approval_debit_note?: boolean;
  retained_earnings_account?: string;
  fx_gain_account?: string;
  fx_loss_account?: string;
}

// =============================================================================
// Audit Log
// =============================================================================

export interface AuditLogEntry {
  id: number;
  timestamp: string;
  doctype: string;
  document_id: number;
  document_name?: string;
  action: string;
  user_id: number;
  user_email?: string;
  user_name?: string;
  old_values?: Record<string, unknown>;
  new_values?: Record<string, unknown>;
  changed_fields?: string[];
  remarks?: string;
}

export interface AuditLogListResponse extends PaginatedResponse {
  logs: AuditLogEntry[];
}

// =============================================================================
// Document Attachment
// =============================================================================

export interface DocumentAttachment {
  id: number;
  doctype: string;
  document_id: number;
  file_name: string;
  file_path?: string;
  file_type?: string;
  file_size: number;
  attachment_type?: string;
  is_primary: boolean;
  description?: string;
  uploaded_at: string;
  uploaded_by_id?: number;
}

export interface DocumentAttachmentListResponse {
  total: number;
  attachments: DocumentAttachment[];
}

// =============================================================================
// Outstanding Documents (for payment allocation)
// =============================================================================

export interface OutstandingDocument {
  document_type: string;
  document_id: number;
  document_number?: string;
  document_date?: string;
  due_date?: string;
  currency: string;
  total_amount: number;
  outstanding_amount: number;
}

export interface OutstandingDocumentsResponse {
  total: number;
  documents: OutstandingDocument[];
}

// =============================================================================
// Supported Doctypes
// =============================================================================

export interface SupportedDoctype {
  doctype: string;
  name: string;
  description: string;
}

export interface SupportedDoctypesResponse {
  total: number;
  doctypes: SupportedDoctype[];
}

// =============================================================================
// API Response Wrappers
// =============================================================================

export interface ApiSuccessResponse<T = unknown> {
  message?: string;
  data?: T;
}

export interface ApiErrorResponse {
  detail: string | { errors: string[] };
}

// =============================================================================
// Utility types for form handling
// =============================================================================

/**
 * Helper to convert numeric strings to numbers for display
 */
export type MonetaryValue = string | number;

/**
 * Makes all properties of T optional and nullable for partial updates
 */
export type PartialUpdate<T> = {
  [P in keyof T]?: T[P] | null;
};
