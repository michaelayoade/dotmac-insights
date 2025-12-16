export type FundingMethod = 'out_of_pocket' | 'cash_advance' | 'corporate_card' | 'per_diem';
export type ExpenseClaimStatus =
  | 'draft'
  | 'pending_approval'
  | 'approved'
  | 'rejected'
  | 'returned'
  | 'recalled'
  | 'posted'
  | 'paid'
  | 'reversed'
  | 'cancelled';

// ============== Expense Categories ==============

export interface ExpenseCategory {
  id: number;
  code: string;
  name: string;
  description?: string | null;
  parent_id?: number | null;
  is_group: boolean;
  expense_account: string;
  payable_account?: string | null;
  category_type?: string | null;
  default_tax_code_id?: number | null;
  is_tax_deductible: boolean;
  requires_receipt: boolean;
  is_active: boolean;
  is_system?: boolean;
  company?: string | null;
}

export interface ExpenseCategoryCreatePayload {
  code: string;
  name: string;
  expense_account: string;
  description?: string | null;
  parent_id?: number | null;
  is_group?: boolean;
  payable_account?: string | null;
  category_type?: string | null;
  default_tax_code_id?: number | null;
  is_tax_deductible?: boolean;
  requires_receipt?: boolean;
  company?: string | null;
}

// ============== Expense Policies ==============

export interface ExpensePolicy {
  id: number;
  policy_name: string;
  description?: string | null;
  category_id?: number | null;
  applies_to_all: boolean;
  department_id?: number | null;
  designation_id?: number | null;
  employment_type?: string | null;
  grade_level?: string | null;
  max_single_expense?: number | null;
  max_daily_limit?: number | null;
  max_monthly_limit?: number | null;
  max_claim_amount?: number | null;
  currency: string;
  receipt_required: boolean;
  receipt_threshold?: number | null;
  auto_approve_below?: number | null;
  requires_pre_approval: boolean;
  allow_out_of_pocket: boolean;
  allow_cash_advance: boolean;
  allow_corporate_card: boolean;
  allow_per_diem: boolean;
  effective_from?: string | null;
  effective_to?: string | null;
  is_active: boolean;
  priority: number;
  company?: string | null;
}

export interface ExpensePolicyCreatePayload {
  policy_name: string;
  description?: string | null;
  category_id?: number | null;
  applies_to_all?: boolean;
  department_id?: number | null;
  designation_id?: number | null;
  employment_type?: string | null;
  grade_level?: string | null;
  max_single_expense?: number | null;
  max_daily_limit?: number | null;
  max_monthly_limit?: number | null;
  max_claim_amount?: number | null;
  currency?: string;
  receipt_required?: boolean;
  receipt_threshold?: number | null;
  auto_approve_below?: number | null;
  requires_pre_approval?: boolean;
  allow_out_of_pocket?: boolean;
  allow_cash_advance?: boolean;
  allow_corporate_card?: boolean;
  allow_per_diem?: boolean;
  effective_from?: string | null;
  effective_to?: string | null;
  is_active?: boolean;
  priority?: number;
  company?: string | null;
}

export interface ExpenseClaimLine {
  id: number;
  category_id: number;
  expense_date: string;
  description: string;
  claimed_amount: number;
  sanctioned_amount: number;
  currency: string;
  funding_method: FundingMethod;
  has_receipt: boolean;
  tax_amount: number;
  conversion_rate: number;
  base_claimed_amount: number;
}

export interface ExpenseClaim {
  id: number;
  claim_number?: string | null;
  title: string;
  employee_id: number;
  claim_date: string;
  status: ExpenseClaimStatus;
  total_claimed_amount: number;
  total_taxes: number;
  currency: string;
  base_currency: string;
  conversion_rate: number;
  lines: ExpenseClaimLine[];
}

export interface ExpenseClaimLinePayload {
  category_id: number;
  expense_date: string;
  description: string;
  claimed_amount: number;
  currency?: string;
  tax_code_id?: number | null;
  tax_rate?: number;
  tax_amount?: number;
  is_tax_inclusive?: boolean;
  is_tax_reclaimable?: boolean;
  withholding_tax_rate?: number;
  withholding_tax_amount?: number;
  conversion_rate?: number;
  rate_source?: string | null;
  rate_date?: string | null;
  funding_method?: FundingMethod;
  merchant_name?: string | null;
  invoice_number?: string | null;
  cost_center?: string | null;
  project_id?: number | null;
  has_receipt?: boolean;
  receipt_missing_reason?: string | null;
}

export interface ExpenseClaimCreatePayload {
  title: string;
  employee_id: number;
  claim_date: string;
  description?: string | null;
  currency?: string;
  base_currency?: string;
  conversion_rate?: number;
  project_id?: number | null;
  cost_center?: string | null;
  cash_advance_id?: number | null;
  company?: string | null;
  lines: ExpenseClaimLinePayload[];
}

export type CashAdvanceStatus =
  | 'draft'
  | 'pending_approval'
  | 'approved'
  | 'rejected'
  | 'disbursed'
  | 'partially_settled'
  | 'fully_settled'
  | 'cancelled'
  | 'written_off';

export interface CashAdvance {
  id: number;
  advance_number?: string | null;
  employee_id: number;
  purpose: string;
  request_date: string;
  required_by_date?: string | null;
  project_id?: number | null;
  trip_start_date?: string | null;
  trip_end_date?: string | null;
  destination?: string | null;
  requested_amount: number;
  approved_amount: number;
  disbursed_amount: number;
  settled_amount: number;
  outstanding_amount: number;
  refund_amount: number;
  currency: string;
  base_currency: string;
  conversion_rate: number;
  status: CashAdvanceStatus;
  company?: string | null;
}

export interface CashAdvanceCreatePayload {
  employee_id: number;
  purpose: string;
  request_date: string;
  required_by_date?: string | null;
  project_id?: number | null;
  trip_start_date?: string | null;
  trip_end_date?: string | null;
  destination?: string | null;
  requested_amount: number;
  currency?: string;
  base_currency?: string;
  conversion_rate?: number;
  company?: string | null;
}

export interface CashAdvanceDisbursePayload {
  amount: number;
  mode_of_payment?: string | null;
  payment_reference?: string | null;
  bank_account_id?: number | null;
}

export interface CashAdvanceSettlePayload {
  amount: number;
  refund_amount?: number;
}

// Corporate Card Types
export type CorporateCardStatus = 'active' | 'suspended' | 'cancelled';
export type CardTransactionStatus = 'imported' | 'matched' | 'unmatched' | 'disputed' | 'excluded' | 'personal';
export type StatementStatus = 'open' | 'reconciled' | 'closed';

export interface CorporateCard {
  id: number;
  card_number_last4: string;
  card_name: string;
  card_type?: string | null;
  bank_name?: string | null;
  card_provider?: string | null;
  employee_id: number;
  credit_limit: number;
  single_transaction_limit?: number | null;
  daily_limit?: number | null;
  monthly_limit?: number | null;
  currency: string;
  status: CorporateCardStatus;
  issue_date: string;
  expiry_date?: string | null;
  liability_account?: string | null;
  bank_account_id?: number | null;
  company?: string | null;
}

export interface CorporateCardCreatePayload {
  card_number_last4: string;
  card_name: string;
  card_type?: string | null;
  bank_name?: string | null;
  card_provider?: string | null;
  employee_id: number;
  credit_limit?: number;
  single_transaction_limit?: number | null;
  daily_limit?: number | null;
  monthly_limit?: number | null;
  currency?: string;
  issue_date: string;
  expiry_date?: string | null;
  liability_account?: string | null;
  bank_account_id?: number | null;
  company?: string | null;
}

export interface CorporateCardUpdatePayload {
  card_name?: string;
  card_type?: string | null;
  bank_name?: string | null;
  card_provider?: string | null;
  credit_limit?: number;
  single_transaction_limit?: number | null;
  daily_limit?: number | null;
  monthly_limit?: number | null;
  expiry_date?: string | null;
  liability_account?: string | null;
  bank_account_id?: number | null;
  status?: CorporateCardStatus;
}

export interface CorporateCardTransaction {
  id: number;
  card_id: number;
  statement_id?: number | null;
  transaction_date: string;
  posting_date?: string | null;
  merchant_name?: string | null;
  merchant_category_code?: string | null;
  description?: string | null;
  amount: number;
  currency: string;
  original_amount?: number | null;
  original_currency?: string | null;
  conversion_rate: number;
  transaction_reference?: string | null;
  authorization_code?: string | null;
  status: CardTransactionStatus;
  expense_claim_line_id?: number | null;
  match_confidence?: number | null;
  disputed_at?: string | null;
  dispute_reason?: string | null;
  resolution_notes?: string | null;
}

export interface CorporateCardTransactionCreatePayload {
  card_id: number;
  statement_id?: number | null;
  transaction_date: string;
  posting_date?: string | null;
  merchant_name?: string | null;
  merchant_category_code?: string | null;
  description?: string | null;
  amount: number;
  currency?: string;
  original_amount?: number | null;
  original_currency?: string | null;
  conversion_rate?: number;
  transaction_reference?: string | null;
  authorization_code?: string | null;
}

export interface CorporateCardStatement {
  id: number;
  card_id: number;
  period_start: string;
  period_end: string;
  statement_date?: string | null;
  import_date: string;
  import_source?: string | null;
  original_filename?: string | null;
  status: StatementStatus;
  total_amount: number;
  transaction_count: number;
  matched_amount: number;
  matched_count: number;
  unmatched_count: number;
  reconciled_at?: string | null;
  reconciled_by_id?: number | null;
  closed_at?: string | null;
  closed_by_id?: number | null;
}

export interface StatementImportPayload {
  card_id: number;
  period_start: string;
  period_end: string;
  statement_date?: string | null;
  import_source?: string;
  original_filename?: string | null;
  transactions: CorporateCardTransactionCreatePayload[];
}

// Analytics Types
export interface CardAnalyticsOverview {
  cards: {
    total: number;
    active: number;
    suspended: number;
    total_credit_limit: number;
  };
  transactions: {
    total: number;
    matched: number;
    unmatched: number;
    disputed: number;
    personal: number;
    reconciliation_rate: number;
  };
  spend: {
    total: number;
    period_months: number;
  };
}

export interface SpendTrendItem {
  period: string;
  transaction_count: number;
  total_spend: number;
  matched_spend: number;
  personal_spend: number;
  reconciliation_rate: number;
}

export interface TopMerchant {
  merchant: string;
  transaction_count: number;
  total_spend: number;
  percentage: number;
}

export interface CategoryBreakdown {
  mcc_code: string;
  category_name: string;
  transaction_count: number;
  total_spend: number;
  percentage: number;
}

export interface CardUtilization {
  card_id: number;
  card_name: string;
  card_last4: string;
  employee_id: number;
  credit_limit: number;
  spend: number;
  utilization_pct: number;
  remaining: number;
}

export interface StatusBreakdownItem {
  status: string;
  count: number;
  amount: number;
  count_pct: number;
  amount_pct: number;
}

export interface TopSpender {
  card_id: number;
  card_name: string;
  card_last4: string;
  employee_id: number;
  transaction_count: number;
  total_spend: number;
}

export interface ReconciliationTrendItem {
  period: string;
  total: number;
  matched: number;
  unmatched: number;
  reconciliation_rate: number;
}

export interface StatementSummary {
  statements: {
    total: number;
    open: number;
    reconciled: number;
    closed: number;
  };
  aggregates: {
    total_amount: number;
    total_transactions: number;
    total_matched: number;
    total_unmatched: number;
  };
}

// Expense Summary Report
export interface ExpenseSummaryReport {
  period: {
    start: string;
    end: string;
  };
  claims: {
    count: number;
    total_claimed: number;
    total_approved: number;
    by_status: Array<{ status: string; count: number; amount: number }>;
  };
  advances: {
    count: number;
    total_requested: number;
    total_disbursed: number;
    total_outstanding: number;
  };
  top_categories: Array<{ category: string; count: number; total: number }>;
  generated_at: string;
}
