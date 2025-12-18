/**
 * Finance Domain API (Sales/AR)
 * Includes: Invoices, Payments, Credit Notes, Orders, Quotations, Analytics
 */

import { fetchApi } from '../core';

// =============================================================================
// TYPES
// =============================================================================

// Dashboard
export interface FinanceDashboard {
  currency: string;
  revenue: {
    mrr: number;
    arr: number;
    active_subscriptions?: number;
  };
  collections: {
    last_30_days: number;
    invoiced_30_days: number;
    collection_rate: number;
  };
  outstanding: {
    total: number;
    overdue: number;
  };
  metrics: {
    dso: number;
  };
  invoices_by_status?: Record<string, { count: number; total: number }>;
  period?: {
    start: string;
    end: string;
  };
}

// Invoice Types
export interface FinanceInvoice {
  id: number;
  invoice_number: string | null;
  customer_id: number | null;
  customer_name?: string | null;
  description?: string | null;
  amount?: number | null;
  tax_amount?: number | null;
  total_amount: number;
  amount_paid: number;
  balance: number | null;
  status: string;
  invoice_date: string | null;
  due_date: string | null;
  paid_date?: string | null;
  days_overdue?: number | null;
  category?: string | null;
  currency: string | null;
  source?: string | null;
  external_ids?: { splynx_id?: string | null; erpnext_id?: string | null };
  write_back_status?: string | null;
}

export interface FinanceInvoiceItem {
  id?: number | string;
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
  income_account?: string | null;
  expense_account?: string | null;
  cost_center?: string | null;
  sales_order?: string | null;
  delivery_note?: string | null;
  idx?: number;
}

export interface FinanceInvoicePaymentRef {
  id: number;
  amount: number;
  payment_method?: string | null;
  status: string;
  payment_date: string | null;
  currency?: string | null;
}

export interface FinanceInvoiceCreditNoteRef {
  id: number;
  amount: number;
  status: string;
  issue_date: string | null;
}

export interface FinanceInvoiceDetail extends FinanceInvoice {
  customer?: { id?: number | null; name?: string | null; email?: string | null };
  items?: FinanceInvoiceItem[];
  payments?: FinanceInvoicePaymentRef[];
  credit_notes?: FinanceInvoiceCreditNoteRef[];
}

export interface FinanceInvoiceListResponse {
  invoices: FinanceInvoice[];
  total: number;
  page: number;
  page_size: number;
}

export interface FinanceInvoicePayload {
  invoice_number?: string | null;
  customer_id?: number | null;
  description?: string | null;
  amount?: number | null;
  tax_amount?: number | null;
  amount_paid?: number | null;
  currency?: string | null;
  status?: string | null;
  invoice_date?: string | null;
  due_date?: string | null;
  paid_date?: string | null;
  category?: string | null;
  total_amount?: number | null;
  balance?: number | null;
  line_items?: Array<{
    description?: string | null;
    quantity?: number;
    unit_price?: number;
    tax_rate?: number;
  }>;
}

export interface FinanceInvoiceListParams {
  status?: string;
  customer_id?: number;
  start_date?: string;
  end_date?: string;
  min_amount?: number;
  max_amount?: number;
  currency?: string;
  overdue_only?: boolean;
  search?: string;
  sort_by?: 'invoice_date' | 'total_amount' | 'status';
  sort_order?: 'asc' | 'desc';
  page?: number;
  page_size?: number;
}

// Payment Types
export interface FinancePayment {
  id: number;
  receipt_number: string | null;
  customer_id: number | null;
  customer_name?: string | null;
  amount: number;
  currency: string | null;
  payment_method: string | null;
  status: string;
  payment_date: string | null;
  transaction_reference: string | null;
  gateway_reference?: string | null;
  notes?: string | null;
  invoice_id?: number | null;
  source?: string | null;
  external_ids?: { splynx_id?: string | null; erpnext_id?: string | null };
  write_back_status?: string | null;
}

export interface FinancePaymentReference {
  id?: number;
  reference_doctype?: string | null;
  reference_name?: string | null;
  total_amount?: number | null;
  outstanding_amount?: number | null;
  allocated_amount?: number | null;
  exchange_rate?: number | null;
  exchange_gain_loss?: number | null;
  due_date?: string | null;
  idx?: number;
}

export interface FinancePaymentDetail extends FinancePayment {
  customer?: { id?: number | null; name?: string | null; email?: string | null };
  invoice?: {
    id: number | null;
    invoice_number: string | null;
    total_amount?: number | null;
  };
  references?: FinancePaymentReference[];
}

export interface FinancePaymentListResponse {
  payments: FinancePayment[];
  total: number;
  page: number;
  page_size: number;
}

export interface FinancePaymentPayload {
  customer_id: number | null;
  invoice_id?: number | null;
  receipt_number?: string | null;
  amount: number;
  currency?: string | null;
  payment_method?: string | null;
  status?: string;
  payment_date?: string | null;
  transaction_reference?: string | null;
  gateway_reference?: string | null;
  notes?: string | null;
}

export interface FinancePaymentListParams {
  status?: string;
  payment_method?: string;
  customer_id?: number;
  invoice_id?: number;
  start_date?: string;
  end_date?: string;
  min_amount?: number;
  max_amount?: number;
  currency?: string;
  search?: string;
  sort_by?: 'payment_date' | 'amount' | 'status';
  sort_order?: 'asc' | 'desc';
  page?: number;
  page_size?: number;
}

// Credit Note Types
export interface FinanceCreditNote {
  id: number;
  credit_number: string | null;
  customer_id: number | null;
  customer_name?: string | null;
  amount: number;
  currency: string | null;
  status: string;
  issue_date: string | null;
  applied_date?: string | null;
  description: string | null;
  invoice_id?: number | null;
  source?: string | null;
  write_back_status?: string | null;
}

export interface FinanceCreditNoteDetail extends FinanceCreditNote {
  invoice?: {
    id: number | null;
    invoice_number: string | null;
    total_amount?: number | null;
  };
}

export interface FinanceCreditNoteListResponse {
  credit_notes: FinanceCreditNote[];
  total: number;
  page: number;
  page_size: number;
}

export interface FinanceCreditNotePayload {
  credit_number?: string | null;
  customer_id?: number | null;
  invoice_id?: number | null;
  description?: string | null;
  amount?: number | null;
  currency?: string | null;
  status?: string | null;
  issue_date?: string | null;
  applied_date?: string | null;
}

export interface FinanceCreditNoteListParams {
  customer_id?: number;
  invoice_id?: number;
  start_date?: string;
  end_date?: string;
  currency?: string;
  search?: string;
  status?: string;
  min_amount?: number;
  max_amount?: number;
  sort_by?: 'issue_date' | 'amount' | 'status';
  sort_order?: 'asc' | 'desc';
  page?: number;
  page_size?: number;
}

// Order Types
export interface FinanceOrderItem {
  id?: number;
  item_code?: string | null;
  item_name?: string | null;
  description?: string | null;
  qty?: number | null;
  stock_qty?: number | null;
  uom?: string | null;
  stock_uom?: string | null;
  conversion_factor?: number | null;
  rate?: number | null;
  price_list_rate?: number | null;
  discount_percentage?: number | null;
  discount_amount?: number | null;
  amount?: number | null;
  net_amount?: number | null;
  delivered_qty?: number | null;
  billed_amt?: number | null;
  warehouse?: string | null;
  delivery_date?: string | null;
  expense_account?: string | null;
  cost_center?: string | null;
  schedule_date?: string | null;
  idx?: number | null;
}

export interface FinanceOrder {
  id: number;
  order_number: string | null;
  customer_id: number | null;
  customer_name?: string | null;
  order_type?: string | null;
  company?: string | null;
  status: string | null;
  total_amount: number;
  currency: string | null;
  order_date?: string | null;
  transaction_date?: string | null;
  delivery_date?: string | null;
  description?: string | null;
  total_qty?: number | null;
  net_total?: number | null;
  grand_total?: number | null;
  rounded_total?: number | null;
  total_taxes_and_charges?: number | null;
  per_delivered?: number | null;
  per_billed?: number | null;
  billing_status?: string | null;
  delivery_status?: string | null;
  erpnext_id?: string | null;
  items?: FinanceOrderItem[];
  write_back_status?: string | null;
}

export interface FinanceOrderListResponse {
  orders: FinanceOrder[];
  total: number;
  page: number;
  page_size: number;
}

export interface FinanceOrderPayload {
  customer_id?: number | null;
  customer_name?: string | null;
  order_type?: string | null;
  company?: string | null;
  currency?: string | null;
  transaction_date?: string | null;
  delivery_date?: string | null;
  total_qty?: number | null;
  total?: number | null;
  net_total?: number | null;
  grand_total?: number | null;
  rounded_total?: number | null;
  total_taxes_and_charges?: number | null;
  per_delivered?: number | null;
  per_billed?: number | null;
  billing_status?: string | null;
  delivery_status?: string | null;
  status?: string | null;
  sales_partner?: string | null;
  territory?: string | null;
  source?: string | null;
  campaign?: string | null;
  order_number?: string | null;
  description?: string | null;
}

export interface FinanceOrderListParams {
  customer_id?: number;
  status?: string;
  start_date?: string;
  end_date?: string;
  min_amount?: number;
  max_amount?: number;
  currency?: string;
  search?: string;
  sort_by?: 'order_date' | 'total_amount' | 'status';
  sort_order?: 'asc' | 'desc';
  page?: number;
  page_size?: number;
}

// Quotation Types
export interface FinanceQuotationItem {
  id?: number;
  item_code?: string | null;
  item_name?: string | null;
  description?: string | null;
  qty?: number | null;
  stock_qty?: number | null;
  uom?: string | null;
  stock_uom?: string | null;
  conversion_factor?: number | null;
  rate?: number | null;
  price_list_rate?: number | null;
  discount_percentage?: number | null;
  discount_amount?: number | null;
  amount?: number | null;
  net_amount?: number | null;
  idx?: number | null;
}

export interface FinanceQuotation {
  id: number;
  quotation_number: string | null;
  customer_id: number | null;
  customer_name?: string | null;
  quotation_to?: string | null;
  party_name?: string | null;
  order_type?: string | null;
  company?: string | null;
  status: string | null;
  total_amount: number;
  currency: string | null;
  quotation_date?: string | null;
  transaction_date?: string | null;
  valid_till?: string | null;
  description?: string | null;
  total_qty?: number | null;
  total?: number | null;
  net_total?: number | null;
  grand_total?: number | null;
  rounded_total?: number | null;
  total_taxes_and_charges?: number | null;
  sales_partner?: string | null;
  territory?: string | null;
  source?: string | null;
  campaign?: string | null;
  order_lost_reason?: string | null;
  erpnext_id?: string | null;
  items?: FinanceQuotationItem[];
  write_back_status?: string | null;
}

export interface FinanceQuotationListResponse {
  quotations: FinanceQuotation[];
  total: number;
  page: number;
  page_size: number;
}

export interface FinanceQuotationPayload {
  quotation_to?: string | null;
  party_name?: string | null;
  customer_name?: string | null;
  order_type?: string | null;
  company?: string | null;
  currency?: string | null;
  transaction_date?: string | null;
  valid_till?: string | null;
  total_qty?: number | null;
  total?: number | null;
  net_total?: number | null;
  grand_total?: number | null;
  rounded_total?: number | null;
  total_taxes_and_charges?: number | null;
  status?: string | null;
  sales_partner?: string | null;
  territory?: string | null;
  source?: string | null;
  campaign?: string | null;
  order_lost_reason?: string | null;
  quotation_number?: string | null;
  description?: string | null;
}

export interface FinanceQuotationListParams {
  customer_id?: number;
  status?: string;
  start_date?: string;
  end_date?: string;
  min_amount?: number;
  max_amount?: number;
  currency?: string;
  search?: string;
  sort_by?: 'quotation_date' | 'total_amount' | 'status';
  sort_order?: 'asc' | 'desc';
  page?: number;
  page_size?: number;
}

// Customer Types
export interface FinanceCustomerPayload {
  name: string;
  email?: string | null;
  billing_email?: string | null;
  phone?: string | null;
  phone_secondary?: string | null;
  address?: string | null;
  address_2?: string | null;
  city?: string | null;
  state?: string | null;
  zip_code?: string | null;
  country?: string | null;
  customer_type?: string | null;
  status?: string | null;
  billing_type?: string | null;
  gps?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  signup_date?: string | null;
}

// Analytics Types
export interface FinanceRevenueTrend {
  period: string;
  revenue: number;
  payment_count?: number;
}

export interface FinanceCollectionsAnalytics {
  by_method: Array<{
    method: string;
    amount: number;
    count: number;
  }>;
  timing?: Record<string, number>;
  daily_totals?: Array<{
    date: string;
    amount: number;
    count: number;
  }>;
  meta?: Record<string, unknown>;
}

export interface FinanceAgingBucket {
  count: number;
  total: number;
  invoices: Array<{
    id: number;
    customer_name: string | null;
    total_amount: number;
    balance: number | null;
    due_date: string | null;
    status: string;
  }>;
}

export interface FinanceAgingAnalytics {
  buckets: {
    current: FinanceAgingBucket;
    '1_30': FinanceAgingBucket;
    '31_60': FinanceAgingBucket;
    '61_90': FinanceAgingBucket;
    over_90: FinanceAgingBucket;
  };
  total_invoices: number;
}

export interface FinanceByCurrencyAnalytics {
  by_currency: Array<{
    currency: string;
    mrr?: number;
    arr?: number;
    subscription_count?: number;
    outstanding?: number;
  }>;
}

export interface FinancePaymentBehavior {
  avg_days_to_pay?: number;
  late_payments_percent?: number;
  early_payments_percent?: number;
  on_time_percent?: number;
  late_count?: number;
  early_count?: number;
  on_time_count?: number;
  best_payers?: Array<{ customer_name?: string | null; avg_days_to_pay?: number }>;
  worst_payers?: Array<{ customer_name?: string | null; avg_days_to_pay?: number }>;
  stats?: Record<string, number>;
}

export interface FinanceForecast {
  baseline_mrr: number;
  projection: Array<{ period: string; mrr: number }>;
  assumptions?: Record<string, unknown>;
}

// =============================================================================
// API
// =============================================================================

export const financeApi = {
  // =========================================================================
  // DASHBOARD
  // =========================================================================

  getDashboard: (currency?: string) =>
    fetchApi<FinanceDashboard>('/v1/sales/dashboard', { params: { currency } }),

  // =========================================================================
  // INVOICES
  // =========================================================================

  getInvoices: (params?: FinanceInvoiceListParams) =>
    fetchApi<FinanceInvoiceListResponse>('/v1/sales/invoices', { params: params as any }),

  getInvoiceDetail: (id: number, currency?: string) =>
    fetchApi<FinanceInvoiceDetail>(`/v1/sales/invoices/${id}`, {
      params: { currency },
    }),

  createInvoice: (body: FinanceInvoicePayload) =>
    fetchApi<FinanceInvoiceDetail>('/v1/sales/invoices', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateInvoice: (id: number, body: FinanceInvoicePayload) =>
    fetchApi<FinanceInvoiceDetail>(`/v1/sales/invoices/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteInvoice: (id: number, soft = true) =>
    fetchApi<void>(`/v1/sales/invoices/${id}?soft=${soft ? 'true' : 'false'}`, {
      method: 'DELETE',
    }),

  // =========================================================================
  // PAYMENTS
  // =========================================================================

  getPayments: (params?: FinancePaymentListParams) =>
    fetchApi<FinancePaymentListResponse>('/v1/sales/payments', { params: params as any }),

  getPaymentDetail: (id: number, currency?: string) =>
    fetchApi<FinancePaymentDetail>(`/v1/sales/payments/${id}`, {
      params: { currency },
    }),

  createPayment: (body: FinancePaymentPayload) =>
    fetchApi<FinancePaymentDetail>('/v1/sales/payments', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updatePayment: (id: number, body: FinancePaymentPayload) =>
    fetchApi<FinancePaymentDetail>(`/v1/sales/payments/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deletePayment: (id: number, soft = true) =>
    fetchApi<void>(`/v1/sales/payments/${id}?soft=${soft ? 'true' : 'false'}`, {
      method: 'DELETE',
    }),

  // =========================================================================
  // CREDIT NOTES
  // =========================================================================

  getCreditNotes: (params?: FinanceCreditNoteListParams) =>
    fetchApi<FinanceCreditNoteListResponse>('/v1/sales/credit-notes', {
      params: params as any,
    }),

  getCreditNoteDetail: (id: number, currency?: string) =>
    fetchApi<FinanceCreditNoteDetail>(`/v1/sales/credit-notes/${id}`, {
      params: { currency },
    }),

  createCreditNote: (body: FinanceCreditNotePayload) =>
    fetchApi<FinanceCreditNoteDetail>('/v1/sales/credit-notes', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateCreditNote: (id: number, body: FinanceCreditNotePayload) =>
    fetchApi<FinanceCreditNoteDetail>(`/v1/sales/credit-notes/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteCreditNote: (id: number, soft = true) =>
    fetchApi<void>(
      `/v1/sales/credit-notes/${id}?soft=${soft ? 'true' : 'false'}`,
      { method: 'DELETE' }
    ),

  // =========================================================================
  // ORDERS
  // =========================================================================

  getOrders: (params?: FinanceOrderListParams) =>
    fetchApi<FinanceOrderListResponse>('/v1/sales/orders', { params: params as any }),

  getOrderDetail: (id: number, currency?: string) =>
    fetchApi<FinanceOrder>(`/v1/sales/orders/${id}`, { params: { currency } }),

  createOrder: (body: FinanceOrderPayload) =>
    fetchApi<FinanceOrder>('/v1/sales/orders', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateOrder: (id: number, body: FinanceOrderPayload) =>
    fetchApi<FinanceOrder>(`/v1/sales/orders/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteOrder: (id: number, soft = true) =>
    fetchApi<void>(`/v1/sales/orders/${id}?soft=${soft ? 'true' : 'false'}`, {
      method: 'DELETE',
    }),

  // =========================================================================
  // QUOTATIONS
  // =========================================================================

  getQuotations: (params?: FinanceQuotationListParams) =>
    fetchApi<FinanceQuotationListResponse>('/v1/sales/quotations', { params: params as any }),

  getQuotationDetail: (id: number, currency?: string) =>
    fetchApi<FinanceQuotation>(`/v1/sales/quotations/${id}`, {
      params: { currency },
    }),

  createQuotation: (body: FinanceQuotationPayload) =>
    fetchApi<FinanceQuotation>('/v1/sales/quotations', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateQuotation: (id: number, body: FinanceQuotationPayload) =>
    fetchApi<FinanceQuotation>(`/v1/sales/quotations/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  deleteQuotation: (id: number, soft = true) =>
    fetchApi<void>(
      `/v1/sales/quotations/${id}?soft=${soft ? 'true' : 'false'}`,
      { method: 'DELETE' }
    ),

  // =========================================================================
  // CUSTOMERS
  // =========================================================================

  getCustomers: (params?: {
    search?: string;
    status?: string;
    customer_type?: string;
    limit?: number;
    offset?: number;
  }) => fetchApi<{ items: unknown[]; total: number }>('/v1/sales/customers', { params }),

  getCustomerDetail: (id: number) =>
    fetchApi<unknown>(`/v1/sales/customers/${id}`),

  createCustomer: (body: FinanceCustomerPayload) =>
    fetchApi<unknown>('/v1/sales/customers', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  updateCustomer: (id: number, body: FinanceCustomerPayload) =>
    fetchApi<unknown>(`/v1/sales/customers/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  // =========================================================================
  // ANALYTICS
  // =========================================================================

  getRevenueTrend: (params?: {
    start_date?: string;
    end_date?: string;
    interval?: 'month' | 'week';
    currency?: string;
  }) =>
    fetchApi<FinanceRevenueTrend[]>('/v1/sales/analytics/revenue-trend', {
      params,
    }),

  getCollections: (params?: {
    start_date?: string;
    end_date?: string;
    currency?: string;
  }) =>
    fetchApi<FinanceCollectionsAnalytics>('/v1/sales/analytics/collections', {
      params,
    }),

  getAging: (params?: { currency?: string }) =>
    fetchApi<FinanceAgingAnalytics>('/v1/sales/aging', { params }),

  getRevenueBySegment: () =>
    fetchApi<FinanceByCurrencyAnalytics>('/v1/sales/analytics/by-currency'),

  // =========================================================================
  // INSIGHTS
  // =========================================================================

  getPaymentBehavior: (params?: { currency?: string }) =>
    fetchApi<FinancePaymentBehavior>('/v1/sales/insights/payment-behavior', {
      params,
    }),

  getForecasts: (currency?: string) =>
    fetchApi<FinanceForecast>('/v1/sales/insights/forecasts', {
      params: { currency },
    }),
};

export default financeApi;
