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

export interface ExpenseCategory {
  id: number;
  code: string;
  name: string;
  expense_account: string;
  requires_receipt: boolean;
  is_active: boolean;
}

export interface ExpensePolicy {
  id: number;
  policy_name: string;
  applies_to_all: boolean;
  allow_out_of_pocket: boolean;
  allow_cash_advance: boolean;
  allow_corporate_card: boolean;
  allow_per_diem: boolean;
  priority: number;
  is_active: boolean;
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
