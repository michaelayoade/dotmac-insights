/**
 * Expenses Domain API
 * Includes: Categories, Policies, Claims, Cash Advances, Corporate Cards, Statements, Analytics
 */

import { fetchApi, buildApiUrl } from '../core';

// Re-export all types from existing expenses.types.ts
export * from '../../expenses.types';

// Import types for internal use
import type {
  ExpenseCategory,
  ExpenseCategoryCreatePayload,
  ExpensePolicy,
  ExpensePolicyCreatePayload,
  ExpenseClaim,
  ExpenseClaimCreatePayload,
  CashAdvance,
  CashAdvanceCreatePayload,
  CashAdvanceDisbursePayload,
  CashAdvanceSettlePayload,
  CorporateCard,
  CorporateCardCreatePayload,
  CorporateCardUpdatePayload,
  CorporateCardTransaction,
  CorporateCardTransactionCreatePayload,
  CorporateCardStatement,
  StatementImportPayload,
  CardAnalyticsOverview,
  SpendTrendItem,
  TopMerchant,
  CategoryBreakdown,
  CardUtilization,
  StatusBreakdownItem,
  TopSpender,
  ReconciliationTrendItem,
  StatementSummary,
  ExpenseSummaryReport,
} from '../../expenses.types';

// =============================================================================
// ADDITIONAL TYPES
// =============================================================================

export interface ExpenseReportStatus {
  formats: Record<string, { available: boolean; requires?: string }>;
}

export interface TopMerchantsResponse {
  merchants: TopMerchant[];
  total_spend: number;
  period_days: number;
}

export interface CategoryBreakdownResponse {
  categories: CategoryBreakdown[];
  total_spend: number;
  period_days: number;
}

export interface StatusBreakdownResponse {
  by_status: StatusBreakdownItem[];
  totals: { count: number; amount: number };
  period_days: number;
}

export interface TopSpendersResponse {
  spenders: TopSpender[];
  period_days: number;
}

export interface ExpenseClaimsExportParams {
  format: 'csv' | 'excel' | 'pdf';
  start_date?: string;
  end_date?: string;
  status?: string;
  employee_id?: number;
  include_lines?: boolean;
  filename?: string;
}

export interface CashAdvancesExportParams {
  format: 'csv' | 'excel' | 'pdf';
  start_date?: string;
  end_date?: string;
  status?: string;
  employee_id?: number;
  filename?: string;
}

export interface CardTransactionsExportParams {
  format: 'csv' | 'excel';
  start_date?: string;
  end_date?: string;
  card_id?: number;
  status?: string;
  filename?: string;
}

// =============================================================================
// HELPER FUNCTIONS
// =============================================================================

function getAccessToken(): string {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('dotmac_access_token') || '';
  }
  return '';
}

// =============================================================================
// API
// =============================================================================

export const expensesApi = {
  // =========================================================================
  // CATEGORIES
  // =========================================================================

  getCategories: (params?: { include_inactive?: boolean }) =>
    fetchApi<ExpenseCategory[]>('/expenses/categories/', { params }),

  createCategory: (payload: ExpenseCategoryCreatePayload) =>
    fetchApi<ExpenseCategory>('/expenses/categories/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateCategory: (id: number, payload: ExpenseCategoryCreatePayload) =>
    fetchApi<ExpenseCategory>(`/expenses/categories/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  deleteCategory: (id: number) =>
    fetchApi<void>(`/expenses/categories/${id}`, { method: 'DELETE' }),

  // =========================================================================
  // POLICIES
  // =========================================================================

  getPolicies: (params?: { include_inactive?: boolean; category_id?: number }) =>
    fetchApi<ExpensePolicy[]>('/expenses/policies/', { params }),

  createPolicy: (payload: ExpensePolicyCreatePayload) =>
    fetchApi<ExpensePolicy>('/expenses/policies/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updatePolicy: (id: number, payload: ExpensePolicyCreatePayload) =>
    fetchApi<ExpensePolicy>(`/expenses/policies/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  deletePolicy: (id: number) =>
    fetchApi<void>(`/expenses/policies/${id}`, { method: 'DELETE' }),

  // =========================================================================
  // CLAIMS
  // =========================================================================

  getClaims: (params?: { status?: string; limit?: number; offset?: number }) =>
    fetchApi<ExpenseClaim[]>('/expenses/claims/', { params }),

  getClaimDetail: (id: number) =>
    fetchApi<ExpenseClaim>(`/expenses/claims/${id}`),

  createClaim: (payload: ExpenseClaimCreatePayload) =>
    fetchApi<ExpenseClaim>('/expenses/claims/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  submitClaim: (id: number, company_code?: string) =>
    fetchApi<ExpenseClaim>(`/expenses/claims/${id}/submit`, {
      method: 'POST',
      params: company_code ? { company_code } : undefined,
    }),

  approveClaim: (id: number) =>
    fetchApi<ExpenseClaim>(`/expenses/claims/${id}/approve`, { method: 'POST' }),

  rejectClaim: (id: number, reason: string) =>
    fetchApi<ExpenseClaim>(`/expenses/claims/${id}/reject`, {
      method: 'POST',
      params: { reason },
    }),

  postClaim: (id: number) =>
    fetchApi<ExpenseClaim>(`/expenses/claims/${id}/post`, { method: 'POST' }),

  reverseClaim: (id: number, reason: string) =>
    fetchApi<ExpenseClaim>(`/expenses/claims/${id}/reverse`, {
      method: 'POST',
      params: { reason },
    }),

  // =========================================================================
  // CASH ADVANCES
  // =========================================================================

  getCashAdvances: (params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }) => fetchApi<CashAdvance[]>('/expenses/cash-advances/', { params }),

  getCashAdvanceDetail: (id: number) =>
    fetchApi<CashAdvance>(`/expenses/cash-advances/${id}`),

  createCashAdvance: (payload: CashAdvanceCreatePayload) =>
    fetchApi<CashAdvance>('/expenses/cash-advances/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  submitCashAdvance: (id: number, company_code?: string) =>
    fetchApi<CashAdvance>(`/expenses/cash-advances/${id}/submit`, {
      method: 'POST',
      params: company_code ? { company_code } : undefined,
    }),

  approveCashAdvance: (id: number) =>
    fetchApi<CashAdvance>(`/expenses/cash-advances/${id}/approve`, {
      method: 'POST',
    }),

  rejectCashAdvance: (id: number, reason: string) =>
    fetchApi<CashAdvance>(`/expenses/cash-advances/${id}/reject`, {
      method: 'POST',
      params: { reason },
    }),

  disburseCashAdvance: (id: number, payload: CashAdvanceDisbursePayload) =>
    fetchApi<CashAdvance>(`/expenses/cash-advances/${id}/disburse`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  settleCashAdvance: (id: number, payload: CashAdvanceSettlePayload) =>
    fetchApi<CashAdvance>(`/expenses/cash-advances/${id}/settle`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // =========================================================================
  // CORPORATE CARDS
  // =========================================================================

  getCards: (params?: {
    employee_id?: number;
    status?: string;
    include_inactive?: boolean;
    limit?: number;
    offset?: number;
  }) => fetchApi<CorporateCard[]>('/expenses/cards/', { params }),

  getCardDetail: (id: number) =>
    fetchApi<CorporateCard>(`/expenses/cards/${id}`),

  createCard: (payload: CorporateCardCreatePayload) =>
    fetchApi<CorporateCard>('/expenses/cards/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  updateCard: (id: number, payload: CorporateCardUpdatePayload) =>
    fetchApi<CorporateCard>(`/expenses/cards/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    }),

  suspendCard: (id: number) =>
    fetchApi<CorporateCard>(`/expenses/cards/${id}/suspend`, { method: 'POST' }),

  activateCard: (id: number) =>
    fetchApi<CorporateCard>(`/expenses/cards/${id}/activate`, { method: 'POST' }),

  cancelCard: (id: number) =>
    fetchApi<CorporateCard>(`/expenses/cards/${id}/cancel`, { method: 'POST' }),

  deleteCard: (id: number) =>
    fetchApi<void>(`/expenses/cards/${id}`, { method: 'DELETE' }),

  // =========================================================================
  // CARD TRANSACTIONS
  // =========================================================================

  getTransactions: (params?: {
    card_id?: number;
    statement_id?: number;
    status?: string;
    unmatched_only?: boolean;
    limit?: number;
    offset?: number;
  }) => fetchApi<CorporateCardTransaction[]>('/expenses/transactions/', { params }),

  getTransactionDetail: (id: number) =>
    fetchApi<CorporateCardTransaction>(`/expenses/transactions/${id}`),

  createTransaction: (payload: CorporateCardTransactionCreatePayload) =>
    fetchApi<CorporateCardTransaction>('/expenses/transactions/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  matchTransaction: (
    id: number,
    expenseClaimLineId: number,
    confidence?: number
  ) =>
    fetchApi<CorporateCardTransaction>(`/expenses/transactions/${id}/match`, {
      method: 'POST',
      body: JSON.stringify({
        expense_claim_line_id: expenseClaimLineId,
        confidence,
      }),
    }),

  unmatchTransaction: (id: number) =>
    fetchApi<CorporateCardTransaction>(`/expenses/transactions/${id}/unmatch`, {
      method: 'POST',
    }),

  disputeTransaction: (id: number, reason: string) =>
    fetchApi<CorporateCardTransaction>(`/expenses/transactions/${id}/dispute`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  resolveTransactionDispute: (
    id: number,
    resolutionNotes: string,
    newStatus?: string
  ) =>
    fetchApi<CorporateCardTransaction>(`/expenses/transactions/${id}/resolve`, {
      method: 'POST',
      params: { resolution_notes: resolutionNotes, new_status: newStatus },
    }),

  excludeTransaction: (id: number) =>
    fetchApi<CorporateCardTransaction>(`/expenses/transactions/${id}/exclude`, {
      method: 'POST',
    }),

  markTransactionPersonal: (id: number) =>
    fetchApi<CorporateCardTransaction>(
      `/expenses/transactions/${id}/mark-personal`,
      { method: 'POST' }
    ),

  deleteTransaction: (id: number) =>
    fetchApi<void>(`/expenses/transactions/${id}`, { method: 'DELETE' }),

  // =========================================================================
  // STATEMENTS
  // =========================================================================

  getStatements: (params?: {
    card_id?: number;
    status?: string;
    limit?: number;
    offset?: number;
  }) => fetchApi<CorporateCardStatement[]>('/expenses/statements/', { params }),

  getStatementDetail: (id: number) =>
    fetchApi<CorporateCardStatement>(`/expenses/statements/${id}`),

  createStatement: (payload: {
    card_id: number;
    period_start: string;
    period_end: string;
    statement_date?: string;
    import_source?: string;
    original_filename?: string;
  }) =>
    fetchApi<CorporateCardStatement>('/expenses/statements/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  importStatement: (payload: StatementImportPayload) =>
    fetchApi<CorporateCardStatement>('/expenses/statements/import', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  reconcileStatement: (id: number) =>
    fetchApi<CorporateCardStatement>(`/expenses/statements/${id}/reconcile`, {
      method: 'POST',
    }),

  closeStatement: (id: number) =>
    fetchApi<CorporateCardStatement>(`/expenses/statements/${id}/close`, {
      method: 'POST',
    }),

  reopenStatement: (id: number) =>
    fetchApi<CorporateCardStatement>(`/expenses/statements/${id}/reopen`, {
      method: 'POST',
    }),

  getStatementTransactions: (id: number, status?: string) =>
    fetchApi<CorporateCardTransaction[]>(
      `/expenses/statements/${id}/transactions`,
      { params: { status } }
    ),

  deleteStatement: (id: number) =>
    fetchApi<void>(`/expenses/statements/${id}`, { method: 'DELETE' }),

  // =========================================================================
  // ANALYTICS
  // =========================================================================

  getAnalyticsOverview: (params?: { months?: number }) =>
    fetchApi<CardAnalyticsOverview>('/expenses/analytics/overview', { params }),

  getSpendTrend: (params?: { months?: number }) =>
    fetchApi<SpendTrendItem[]>('/expenses/analytics/spend-trend', { params }),

  getTopMerchants: (params?: { days?: number; limit?: number }) =>
    fetchApi<TopMerchantsResponse>('/expenses/analytics/top-merchants', {
      params,
    }),

  getByCategory: (params?: { days?: number }) =>
    fetchApi<CategoryBreakdownResponse>('/expenses/analytics/by-category', {
      params,
    }),

  getCardUtilization: (params?: { days?: number }) =>
    fetchApi<CardUtilization[]>('/expenses/analytics/card-utilization', {
      params,
    }),

  getStatusBreakdown: (params?: { days?: number }) =>
    fetchApi<StatusBreakdownResponse>('/expenses/analytics/status-breakdown', {
      params,
    }),

  getTopSpenders: (params?: { days?: number; limit?: number }) =>
    fetchApi<TopSpendersResponse>('/expenses/analytics/top-spenders', {
      params,
    }),

  getReconciliationTrend: (params?: { months?: number }) =>
    fetchApi<ReconciliationTrendItem[]>(
      '/expenses/analytics/reconciliation-trend',
      { params }
    ),

  getStatementSummary: () =>
    fetchApi<StatementSummary>('/expenses/analytics/statement-summary'),

  // =========================================================================
  // REPORTS
  // =========================================================================

  getReportStatus: () =>
    fetchApi<ExpenseReportStatus>('/expenses/reports/status'),

  getSummaryReport: (params?: { start_date?: string; end_date?: string }) =>
    fetchApi<ExpenseSummaryReport>('/expenses/reports/summary', { params }),

  exportClaimsReport: async (params: ExpenseClaimsExportParams): Promise<Blob> => {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) searchParams.set(key, String(value));
    });
    const token = getAccessToken();
    const url = buildApiUrl(
      '/expenses/reports/claims',
      Object.fromEntries(searchParams.entries())
    );
    const res = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error('Export failed');
    return res.blob();
  },

  exportAdvancesReport: async (params: CashAdvancesExportParams): Promise<Blob> => {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) searchParams.set(key, String(value));
    });
    const token = getAccessToken();
    const url = buildApiUrl(
      '/expenses/reports/advances',
      Object.fromEntries(searchParams.entries())
    );
    const res = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error('Export failed');
    return res.blob();
  },

  exportTransactionsReport: async (
    params: CardTransactionsExportParams
  ): Promise<Blob> => {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) searchParams.set(key, String(value));
    });
    const token = getAccessToken();
    const url = buildApiUrl(
      '/expenses/reports/transactions',
      Object.fromEntries(searchParams.entries())
    );
    const res = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error('Export failed');
    return res.blob();
  },
};

export default expensesApi;
