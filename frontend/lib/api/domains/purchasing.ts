/**
 * Purchasing Domain API (AP)
 * Includes: Bills, Payments, Orders, Debit Notes, Suppliers, Expenses, Analytics
 */

import { fetchApi } from '../core';

// =============================================================================
// DASHBOARD
// =============================================================================

export interface PurchasingDashboard {
  as_of_date: string;
  total_outstanding: number;
  total_overdue: number;
  overdue_percentage: number;
  supplier_count: number;
  status_breakdown: Record<string, { count: number; total: number }>;
  due_this_week: { count: number; total: number };
  top_suppliers: Array<{ name: string; outstanding: number; bill_count: number }>;
}

// =============================================================================
// BILLS
// =============================================================================

export interface PurchasingBill {
  id: number;
  erpnext_id: string | null;
  supplier: string | null;
  supplier_name: string | null;
  posting_date: string | null;
  due_date: string | null;
  grand_total: number;
  outstanding_amount: number;
  status: string | null;
  currency: string | null;
  is_overdue: boolean;
  days_overdue: number;
  write_back_status?: string | null;
}

export interface PurchasingBillListResponse {
  bills: PurchasingBill[];
  total: number;
  limit: number;
  offset: number;
}

export interface PurchasingBillItem {
  id?: number;
  item_code?: string | null;
  item_name?: string | null;
  description?: string | null;
  qty?: number;
  stock_qty?: number;
  uom?: string | null;
  stock_uom?: string | null;
  conversion_factor?: number;
  rate?: number;
  price_list_rate?: number;
  discount_percentage?: number;
  discount_amount?: number;
  amount?: number;
  net_amount?: number;
  warehouse?: string | null;
  expense_account?: string | null;
  cost_center?: string | null;
  purchase_order?: string | null;
  purchase_receipt?: string | null;
  idx?: number;
}

export interface PurchasingBillGLEntry {
  id: number;
  account: string;
  debit: number;
  credit: number;
  cost_center: string | null;
}

export interface PurchasingBillDetail extends PurchasingBill {
  net_total: number | null;
  total_taxes_and_charges: number;
  company: string | null;
  cost_center: string | null;
  remarks: string | null;
  items?: PurchasingBillItem[];
  gl_entries: PurchasingBillGLEntry[];
}

export interface PurchasingBillPayload {
  supplier?: string | null;
  supplier_name?: string | null;
  company?: string | null;
  posting_date?: string | null;
  due_date?: string | null;
  grand_total?: number | null;
  outstanding_amount?: number | null;
  paid_amount?: number | null;
  currency?: string | null;
  status?: string | null;
}

export interface PurchasingBillListParams {
  status?: string;
  supplier?: string;
  start_date?: string;
  end_date?: string;
  min_amount?: number;
  max_amount?: number;
  currency?: string;
  outstanding_only?: boolean;
  overdue_only?: boolean;
  search?: string;
  sort_by?: 'posting_date' | 'due_date' | 'grand_total' | 'outstanding_amount' | 'supplier';
  sort_dir?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

// =============================================================================
// PAYMENTS
// =============================================================================

export interface PurchasingPayment {
  id: number;
  receipt_number: string | null;
  supplier_id?: number | null;
  supplier_name?: string | null;
  purchase_invoice_id?: number | null;
  amount: number;
  currency: string | null;
  payment_method: string | null;
  status: string | null;
  payment_date: string | null;
  transaction_reference?: string | null;
  gateway_reference?: string | null;
  notes?: string | null;
}

export interface PurchasingPaymentListResponse {
  payments: PurchasingPayment[];
  total: number;
  limit: number;
  offset: number;
}

export type PurchasingPaymentDetail = PurchasingPayment;

export interface PurchasingPaymentListParams {
  supplier?: string;
  start_date?: string;
  end_date?: string;
  min_amount?: number;
  max_amount?: number;
  currency?: string;
  limit?: number;
  offset?: number;
}

// =============================================================================
// ORDERS
// =============================================================================

export interface PurchasingOrder {
  id?: number;
  order_no: string | null;
  supplier: string | null;
  date: string | null;
  total: number;
  grand_total?: number | null;
  schedule_date?: string | null;
  status?: string | null;
  currency?: string | null;
  write_back_status?: string | null;
}

export interface PurchasingOrderListResponse {
  orders: PurchasingOrder[];
  total: number;
  limit: number;
  offset: number;
}

export interface PurchasingOrderItem {
  id?: number;
  item_code?: string | null;
  item_name?: string | null;
  description?: string | null;
  qty?: number;
  stock_qty?: number;
  uom?: string | null;
  stock_uom?: string | null;
  conversion_factor?: number;
  rate?: number;
  price_list_rate?: number;
  discount_percentage?: number;
  discount_amount?: number;
  amount?: number;
  net_amount?: number;
  received_qty?: number;
  billed_amt?: number;
  warehouse?: string | null;
  schedule_date?: string | null;
  expense_account?: string | null;
  cost_center?: string | null;
  idx?: number;
}

export interface PurchasingOrderDetail extends PurchasingOrder {
  net_total?: number | null;
  total_taxes_and_charges?: number | null;
  discount_amount?: number | null;
  per_billed?: number | null;
  per_received?: number | null;
  billed_amt?: number | null;
  received_amt?: number | null;
  company?: string | null;
  conversion_rate?: number | null;
  cost_center?: string | null;
  project?: string | null;
  payment_terms_template?: string | null;
  items?: PurchasingOrderItem[];
}

export interface PurchasingOrderPayload {
  supplier?: string | null;
  supplier_name?: string | null;
  company?: string | null;
  transaction_date?: string | null;
  schedule_date?: string | null;
  grand_total?: number | null;
  net_total?: number | null;
  total_taxes_and_charges?: number | null;
  discount_amount?: number | null;
  per_billed?: number | null;
  per_received?: number | null;
  billed_amt?: number | null;
  received_amt?: number | null;
  currency?: string | null;
  conversion_rate?: number | null;
  status?: string | null;
  cost_center?: string | null;
  project?: string | null;
  payment_terms_template?: string | null;
}

export interface PurchasingOrderListParams {
  supplier?: string;
  status?: string;
  start_date?: string;
  end_date?: string;
  min_amount?: number;
  max_amount?: number;
  currency?: string;
  search?: string;
  sort_by?: 'transaction_date' | 'grand_total' | 'supplier_name';
  sort_dir?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

// =============================================================================
// DEBIT NOTES
// =============================================================================

export interface PurchasingDebitNote {
  id: number;
  erpnext_id: string | null;
  supplier: string | null;
  posting_date: string | null;
  grand_total: number;
  status: string | null;
  return_against: string | null;
  write_back_status?: string | null;
}

export interface PurchasingDebitNoteListResponse {
  debit_notes: PurchasingDebitNote[];
  total: number;
  limit: number;
  offset: number;
}

export interface PurchasingDebitNoteItem {
  id?: number;
  item_code?: string | null;
  item_name?: string | null;
  description?: string | null;
  qty?: number;
  stock_qty?: number;
  uom?: string | null;
  stock_uom?: string | null;
  conversion_factor?: number;
  rate?: number;
  amount?: number;
  net_amount?: number;
  expense_account?: string | null;
  cost_center?: string | null;
  purchase_invoice?: string | null;
  purchase_invoice_item?: string | null;
  idx?: number;
}

export interface PurchasingDebitNoteDetail extends PurchasingDebitNote {
  due_date?: string | null;
  outstanding_amount?: number | null;
  paid_amount?: number | null;
  total_taxes_and_charges?: number | null;
  currency?: string | null;
  conversion_rate?: number | null;
  company?: string | null;
  items?: PurchasingDebitNoteItem[];
}

export interface PurchasingDebitNotePayload {
  supplier?: string | null;
  supplier_name?: string | null;
  company?: string | null;
  posting_date?: string | null;
  due_date?: string | null;
  debit_note_number?: string | null;
  return_against?: string | null;
  grand_total?: number | null;
  outstanding_amount?: number | null;
  paid_amount?: number | null;
  total_taxes_and_charges?: number | null;
  currency?: string | null;
  conversion_rate?: number | null;
  status?: string | null;
  line_items?: Array<{
    description?: string;
    quantity?: number;
    unit_price?: number;
    tax_rate?: number;
  }>;
}

export interface PurchasingDebitNoteListParams {
  supplier?: string;
  start_date?: string;
  end_date?: string;
  status?: string;
  currency?: string;
  search?: string;
  sort_by?: 'posting_date' | 'grand_total' | 'supplier_name';
  sort_dir?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

// =============================================================================
// SUPPLIERS
// =============================================================================

export interface PurchasingSupplier {
  id: number;
  erpnext_id: string | null;
  name: string | null;
  group: string | null;
  type: string | null;
  country: string | null;
  currency: string | null;
  email: string | null;
  mobile: string | null;
  outstanding: number;
  status?: string | null;
  supplier_name?: string | null;
  code?: string | null;
  address?: string | null;
  phone?: string | null;
  credit_limit?: number | null;
  notes?: string | null;
}

export interface PurchasingSupplierListResponse {
  suppliers: PurchasingSupplier[];
  total: number;
  limit: number;
  offset: number;
  items?: PurchasingSupplier[];
  data?: PurchasingSupplier[];
}

export interface PurchasingSupplierRecentBill {
  id: number;
  bill_no: string | null;
  date: string | null;
  amount: number;
  outstanding: number;
  status: string | null;
}

export interface PurchasingSupplierDetail extends PurchasingSupplier {
  tax_id: string | null;
  pan: string | null;
  total_purchases: number;
  total_outstanding: number;
  bill_count: number;
  recent_bills: PurchasingSupplierRecentBill[];
}

export interface PurchasingSupplierGroupsResponse {
  total_groups: number;
  groups: Array<{ name: string; count: number; outstanding: number }>;
}

export interface PurchasingSupplierPayload {
  supplier_name: string;
  supplier_group?: string | null;
  supplier_type?: string | null;
  country?: string | null;
  default_currency?: string | null;
  email_id?: string | null;
  mobile_no?: string | null;
  tax_id?: string | null;
  payment_terms?: string | null;
  disabled?: boolean;
}

export interface PurchasingSupplierListParams {
  search?: string;
  supplier_group?: string;
  supplier_type?: string;
  include_disabled?: boolean;
  sort_by?: 'supplier_name' | 'supplier_group' | 'country';
  sort_dir?: 'asc' | 'desc';
  country?: string;
  with_outstanding?: boolean;
  limit?: number;
  offset?: number;
}

// =============================================================================
// EXPENSES
// =============================================================================

export interface PurchasingExpense {
  id: number;
  posting_date: string | null;
  account?: string;
  amount: number;
  party: string | null;
  voucher_type: string | null;
  voucher_no: string | null;
  cost_center: string | null;
  status?: string | null;
  employee_id?: number | null;
  purpose?: string | null;
  total_claimed_amount?: number | null;
  total_sanctioned_amount?: number | null;
  total_amount_reimbursed?: number | null;
  company?: string | null;
  currency?: string | null;
  write_back_status?: string | null;
}

export interface PurchasingExpenseListResponse {
  expenses: PurchasingExpense[];
  total: number;
  limit: number;
  offset: number;
  summary?: Record<string, unknown>;
}

export interface PurchasingExpenseDetail extends PurchasingExpense {
  purpose?: string | null;
  employee_name?: string | null;
  expense_date?: string | null;
  notes?: string | null;
}

export interface PurchasingExpensePayload {
  employee_id?: number | null;
  purpose?: string | null;
  posting_date?: string | null;
  total_claimed_amount?: number | null;
  total_sanctioned_amount?: number | null;
  total_amount_reimbursed?: number | null;
  currency?: string | null;
  status?: string | null;
  company?: string | null;
  cost_center?: string | null;
}

export interface PurchasingExpenseTypesResponse {
  total_expenses: number;
  expense_types: Array<{
    account: string;
    account_name: string | null;
    total: number;
    entry_count: number;
    percentage: number;
  }>;
}

export interface PurchasingExpenseListParams {
  account?: string;
  cost_center?: string;
  expense_type?: string;
  employee_id?: number;
  project_id?: number;
  status?: string;
  start_date?: string;
  end_date?: string;
  min_amount?: number;
  max_amount?: number;
  currency?: string;
  search?: string;
  sort_by?: 'posting_date' | 'expense_date' | 'total_claimed_amount' | 'employee_name';
  sort_dir?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

// =============================================================================
// ERPNEXT EXPENSE CLAIMS
// =============================================================================

export interface ERPNextExpenseClaim {
  id: number;
  erpnext_id: string | null;
  employee_id: number | null;
  employee_name: string | null;
  erpnext_employee: string | null;
  project_id: number | null;
  erpnext_project: string | null;
  expense_type: string | null;
  description: string | null;
  remark: string | null;
  total_claimed_amount: number;
  total_sanctioned_amount: number;
  total_amount_reimbursed: number;
  total_advance_amount: number;
  amount: number;
  currency: string | null;
  cost_center: string | null;
  company: string | null;
  status: string | null;
  is_paid: boolean;
  posting_date: string | null;
}

export interface ERPNextExpenseClaimListResponse {
  expenses: ERPNextExpenseClaim[];
  total: number;
  limit: number;
  offset: number;
}

export interface ERPNextExpenseClaimDetail extends ERPNextExpenseClaim {
  ticket_id: number | null;
  task_id: number | null;
  erpnext_task: string | null;
  total_taxes_and_charges: number;
  category: string | null;
  pop_id: number | null;
  payable_account: string | null;
  mode_of_payment: string | null;
  clearance_date: string | null;
  approval_status: string | null;
  expense_approver: string | null;
}

export interface ERPNextExpenseClaimPayload {
  employee_id?: number | null;
  employee_name?: string | null;
  erpnext_employee?: string | null;
  project_id?: number | null;
  erpnext_project?: string | null;
  ticket_id?: number | null;
  task_id?: number | null;
  erpnext_task?: string | null;
  expense_type?: string | null;
  description?: string | null;
  remark?: string | null;
  total_claimed_amount?: number;
  total_sanctioned_amount?: number;
  total_amount_reimbursed?: number;
  total_advance_amount?: number;
  amount?: number;
  currency?: string;
  total_taxes_and_charges?: number;
  category?: string | null;
  cost_center?: string | null;
  pop_id?: number | null;
  company?: string | null;
  payable_account?: string | null;
  mode_of_payment?: string | null;
  clearance_date?: string | null;
  approval_status?: string | null;
  expense_approver?: string | null;
  status?: string;
  is_paid?: boolean;
  expense_date?: string | null;
  posting_date?: string | null;
}

export interface ERPNextExpenseClaimListParams {
  employee_id?: number;
  project_id?: number;
  status?: string;
  limit?: number;
  offset?: number;
}

// =============================================================================
// ANALYTICS
// =============================================================================

export interface PurchasingAgingInvoice {
  id: number;
  invoice_no: string | null;
  supplier: string | null;
  posting_date: string | null;
  due_date: string | null;
  grand_total: number;
  outstanding: number;
  days_overdue: number;
}

export interface PurchasingAgingBucket {
  count: number;
  total: number;
  invoices: PurchasingAgingInvoice[];
}

export interface PurchasingAgingResponse {
  as_of_date: string;
  total_payable: number;
  total_invoices: number;
  aging: {
    current: PurchasingAgingBucket;
    '1_30': PurchasingAgingBucket;
    '31_60': PurchasingAgingBucket;
    '61_90': PurchasingAgingBucket;
    over_90: PurchasingAgingBucket;
  };
}

export interface PurchasingBySupplierItem {
  name: string | null;
  bill_count: number;
  total_purchases: number;
  outstanding: number;
  percentage: number;
}

export interface PurchasingBySupplierResponse {
  total: number;
  suppliers: PurchasingBySupplierItem[];
}

export interface PurchasingByCostCenterItem {
  name: string;
  total: number;
  entry_count: number;
  percentage: number;
}

export interface PurchasingByCostCenterResponse {
  total: number;
  cost_centers: PurchasingByCostCenterItem[];
}

export interface PurchasingExpenseTrendItem {
  period: string | null;
  total: number;
  entry_count: number;
}

export interface PurchasingExpenseTrendResponse {
  granularity: string;
  trend: PurchasingExpenseTrendItem[];
}

// =============================================================================
// HELPER FUNCTION FOR PAGINATION
// =============================================================================

function buildPagingParams(params?: { limit?: number; offset?: number }): { page_size?: number; page?: number } {
  if (!params || params.limit === undefined) {
    return {};
  }
  return {
    page_size: params.limit,
    page: params.offset !== undefined && params.limit > 0 ? Math.floor(params.offset / params.limit) + 1 : undefined,
  };
}

// =============================================================================
// API OBJECT
// =============================================================================

export const purchasingApi = {
  // Dashboard
  getDashboard: (params?: { start_date?: string; end_date?: string; currency?: string }) =>
    fetchApi<PurchasingDashboard>('/v1/purchasing/dashboard', { params }),

  // Bills
  getBills: (params?: PurchasingBillListParams) => {
    const paging = buildPagingParams(params);
    return fetchApi<PurchasingBillListResponse>('/v1/purchasing/bills', { params: { ...params, ...paging } });
  },

  getBillDetail: (id: number) =>
    fetchApi<PurchasingBillDetail>(`/v1/purchasing/bills/${id}`),

  createBill: (body: PurchasingBillPayload) =>
    fetchApi<PurchasingBillDetail>('/v1/purchasing/bills', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateBill: (id: number, body: PurchasingBillPayload) =>
    fetchApi<PurchasingBillDetail>(`/v1/purchasing/bills/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteBill: (id: number, soft = true) =>
    fetchApi<void>(`/v1/purchasing/bills/${id}?soft=${soft ? 'true' : 'false'}`, {
      method: 'DELETE',
    }),

  // Payments
  getPayments: (params?: PurchasingPaymentListParams) => {
    const paging = buildPagingParams(params);
    return fetchApi<PurchasingPaymentListResponse>('/v1/purchasing/payments', { params: { ...params, ...paging } });
  },

  getPaymentDetail: (id: number) =>
    fetchApi<PurchasingPaymentDetail>(`/v1/purchasing/payments/${id}`),

  // Orders
  getOrders: (params?: PurchasingOrderListParams) => {
    const paging = buildPagingParams(params);
    return fetchApi<PurchasingOrderListResponse>('/v1/purchasing/orders', { params: { ...params, ...paging } });
  },

  getOrderDetail: (id: number) =>
    fetchApi<PurchasingOrderDetail>(`/v1/purchasing/orders/${id}`),

  createOrder: (body: PurchasingOrderPayload) =>
    fetchApi<PurchasingOrderDetail>('/v1/purchasing/orders', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateOrder: (id: number, body: PurchasingOrderPayload) =>
    fetchApi<PurchasingOrderDetail>(`/v1/purchasing/orders/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteOrder: (id: number, soft = true) =>
    fetchApi<void>(`/v1/purchasing/orders/${id}?soft=${soft ? 'true' : 'false'}`, {
      method: 'DELETE',
    }),

  // Debit Notes
  getDebitNotes: (params?: PurchasingDebitNoteListParams) => {
    const paging = buildPagingParams(params);
    return fetchApi<PurchasingDebitNoteListResponse>('/v1/purchasing/debit-notes', { params: { ...params, ...paging } });
  },

  getDebitNoteDetail: (id: number) =>
    fetchApi<PurchasingDebitNoteDetail>(`/v1/purchasing/debit-notes/${id}`),

  createDebitNote: (body: PurchasingDebitNotePayload) =>
    fetchApi<PurchasingDebitNoteDetail>('/v1/purchasing/debit-notes', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateDebitNote: (id: number, body: PurchasingDebitNotePayload) =>
    fetchApi<PurchasingDebitNoteDetail>(`/v1/purchasing/debit-notes/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteDebitNote: (id: number, soft = true) =>
    fetchApi<void>(`/v1/purchasing/debit-notes/${id}?soft=${soft ? 'true' : 'false'}`, {
      method: 'DELETE',
    }),

  // Suppliers
  getSuppliers: (params?: PurchasingSupplierListParams) => {
    const paging = buildPagingParams(params);
    return fetchApi<PurchasingSupplierListResponse>('/v1/purchasing/suppliers', { params: { ...params, ...paging } });
  },

  getSupplierGroups: () =>
    fetchApi<PurchasingSupplierGroupsResponse>('/v1/purchasing/suppliers/groups'),

  getSupplierDetail: (id: number) =>
    fetchApi<PurchasingSupplierDetail>(`/v1/purchasing/suppliers/${id}`),

  createSupplier: (body: PurchasingSupplierPayload) =>
    fetchApi<PurchasingSupplierDetail>('/v1/purchasing/suppliers', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateSupplier: (id: number, body: Partial<PurchasingSupplierPayload>) =>
    fetchApi<PurchasingSupplierDetail>(`/v1/purchasing/suppliers/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteSupplier: (id: number, soft = true) =>
    fetchApi<void>(`/v1/purchasing/suppliers/${id}?soft=${soft ? 'true' : 'false'}`, {
      method: 'DELETE',
    }),

  // Expenses
  getExpenses: (params?: PurchasingExpenseListParams) => {
    const paging = buildPagingParams(params);
    return fetchApi<PurchasingExpenseListResponse>('/v1/purchasing/expenses', { params: { ...params, ...paging } });
  },

  getExpenseTypes: (params?: { start_date?: string; end_date?: string }) =>
    fetchApi<PurchasingExpenseTypesResponse>('/v1/purchasing/expenses/types', { params }),

  getExpenseDetail: (id: number) =>
    fetchApi<PurchasingExpenseDetail>(`/v1/purchasing/expenses/${id}`),

  // Analytics
  getAging: (params?: { as_of_date?: string; supplier?: string; currency?: string }) =>
    fetchApi<PurchasingAgingResponse>('/v1/purchasing/aging', { params }),

  getBySupplier: (params?: { start_date?: string; end_date?: string; limit?: number; currency?: string }) =>
    fetchApi<PurchasingBySupplierResponse>('/v1/purchasing/analytics/by-supplier', { params }),

  getByCostCenter: (params?: { start_date?: string; end_date?: string; currency?: string }) =>
    fetchApi<PurchasingByCostCenterResponse>('/v1/purchasing/analytics/by-cost-center', { params }),

  getExpenseTrend: (params?: { months?: number; interval?: 'month' | 'week'; currency?: string }) =>
    fetchApi<PurchasingExpenseTrendResponse>('/v1/purchasing/analytics/expense-trend', { params }),

  // ERPNext Expense Claims
  getERPNextExpenses: (params?: ERPNextExpenseClaimListParams) => {
    const paging = buildPagingParams(params);
    return fetchApi<ERPNextExpenseClaimListResponse>('/v1/purchasing/erpnext-expenses', { params: { ...params, ...paging } });
  },

  getERPNextExpenseDetail: (id: number | string) =>
    fetchApi<ERPNextExpenseClaimDetail>(`/v1/purchasing/erpnext-expenses/${id}`),

  createERPNextExpense: (body: ERPNextExpenseClaimPayload) =>
    fetchApi<{ id: number }>('/v1/purchasing/erpnext-expenses', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateERPNextExpense: (id: number | string, body: Partial<ERPNextExpenseClaimPayload>) =>
    fetchApi<{ id: number }>(`/v1/purchasing/erpnext-expenses/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteERPNextExpense: (id: number | string) =>
    fetchApi<void>(`/v1/purchasing/erpnext-expenses/${id}`, {
      method: 'DELETE',
    }),
};
