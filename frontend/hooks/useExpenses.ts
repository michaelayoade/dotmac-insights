import useSWR, { SWRConfiguration, useSWRConfig } from 'swr';
import { api } from '@/lib/api';
import type {
  ExpenseClaim,
  ExpenseCategory,
  ExpenseCategoryCreatePayload,
  ExpensePolicy,
  ExpensePolicyCreatePayload,
  CashAdvance,
  ExpenseClaimCreatePayload,
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
} from '@/lib/expenses.types';

export function useExpenseCategories(params?: { include_inactive?: boolean }, config?: SWRConfiguration) {
  return useSWR<ExpenseCategory[]>(['expense-categories', params], () => api.getExpenseCategories(params), config);
}

export function useExpenseCategoryMutations() {
  const { mutate } = useSWRConfig();
  const invalidateCategories = () => mutate((key) => Array.isArray(key) && key[0] === 'expense-categories');

  return {
    createCategory: async (payload: ExpenseCategoryCreatePayload) => {
      const res = await api.createExpenseCategory(payload);
      await invalidateCategories();
      return res;
    },
    updateCategory: async (id: number, payload: ExpenseCategoryCreatePayload) => {
      const res = await api.updateExpenseCategory(id, payload);
      await invalidateCategories();
      return res;
    },
    deleteCategory: async (id: number) => {
      await api.deleteExpenseCategory(id);
      await invalidateCategories();
    },
  };
}

export function useExpensePolicies(params?: { include_inactive?: boolean; category_id?: number }, config?: SWRConfiguration) {
  return useSWR<ExpensePolicy[]>(['expense-policies', params], () => api.getExpensePolicies(params), config);
}

export function useExpensePolicyMutations() {
  const { mutate } = useSWRConfig();
  const invalidatePolicies = () => mutate((key) => Array.isArray(key) && key[0] === 'expense-policies');

  return {
    createPolicy: async (payload: ExpensePolicyCreatePayload) => {
      const res = await api.createExpensePolicy(payload);
      await invalidatePolicies();
      return res;
    },
    updatePolicy: async (id: number, payload: ExpensePolicyCreatePayload) => {
      const res = await api.updateExpensePolicy(id, payload);
      await invalidatePolicies();
      return res;
    },
    deletePolicy: async (id: number) => {
      await api.deleteExpensePolicy(id);
      await invalidatePolicies();
    },
  };
}

export function useExpenseClaims(params?: { status?: string; limit?: number; offset?: number }, config?: SWRConfiguration) {
  return useSWR<ExpenseClaim[]>(['expense-claims', params], () => api.getExpenseClaims(params), config);
}

export function useExpenseClaimDetail(id?: number, config?: SWRConfiguration) {
  const key = id ? (['expense-claim', id] as const) : null;
  return useSWR<ExpenseClaim>(
    key,
    key ? ([, claimId]: [string, number]) => api.getExpenseClaimDetail(claimId) : null,
    config
  );
}

export function useCashAdvances(params?: { status?: string; limit?: number; offset?: number }, config?: SWRConfiguration) {
  return useSWR<CashAdvance[]>(['cash-advances', params], () => api.getCashAdvances(params), config);
}

export function useCashAdvanceDetail(id?: number, config?: SWRConfiguration) {
  const key = id ? (['cash-advance', id] as const) : null;
  return useSWR<CashAdvance>(
    key,
    key ? ([, advanceId]: [string, number]) => api.getCashAdvanceDetail(advanceId) : null,
    config
  );
}

export function useExpenseMutations() {
  const { mutate } = useSWRConfig();
  return {
    createClaim: async (payload: ExpenseClaimCreatePayload) => {
      const res = await api.createExpenseClaim(payload);
      await mutate(['expense-claims']);
      return res;
    },
    submitClaim: async (id: number, companyCode?: string) => {
      const res = await api.submitExpenseClaim(id, companyCode);
      await mutate(['expense-claims']);
      await mutate(['expense-claim', id]);
      return res;
    },
    approveClaim: async (id: number) => {
      const res = await api.approveExpenseClaim(id);
      await mutate(['expense-claims']);
      await mutate(['expense-claim', id]);
      return res;
    },
    rejectClaim: async (id: number, reason: string) => {
      const res = await api.rejectExpenseClaim(id, reason);
      await mutate(['expense-claims']);
      await mutate(['expense-claim', id]);
      return res;
    },
    postClaim: async (id: number) => {
      const res = await api.postExpenseClaim(id);
      await mutate(['expense-claims']);
      await mutate(['expense-claim', id]);
      return res;
    },
    reverseClaim: async (id: number, reason: string) => {
      const res = await api.reverseExpenseClaim(id, reason);
      await mutate(['expense-claims']);
      await mutate(['expense-claim', id]);
      return res;
    },
  };
}

export function useCashAdvanceMutations() {
  const { mutate } = useSWRConfig();
  return {
    createAdvance: async (payload: CashAdvanceCreatePayload) => {
      const res = await api.createCashAdvance(payload);
      await mutate(['cash-advances']);
      return res;
    },
    submitAdvance: async (id: number, companyCode?: string) => {
      const res = await api.submitCashAdvance(id, companyCode);
      await mutate(['cash-advances']);
      await mutate(['cash-advance', id]);
      return res;
    },
    approveAdvance: async (id: number) => {
      const res = await api.approveCashAdvance(id);
      await mutate(['cash-advances']);
      await mutate(['cash-advance', id]);
      return res;
    },
    rejectAdvance: async (id: number, reason: string) => {
      const res = await api.rejectCashAdvance(id, reason);
      await mutate(['cash-advances']);
      await mutate(['cash-advance', id]);
      return res;
    },
    disburseAdvance: async (id: number, payload: CashAdvanceDisbursePayload) => {
      const res = await api.disburseCashAdvance(id, payload);
      await mutate(['cash-advances']);
      await mutate(['cash-advance', id]);
      return res;
    },
    settleAdvance: async (id: number, payload: CashAdvanceSettlePayload) => {
      const res = await api.settleCashAdvance(id, payload);
      await mutate(['cash-advances']);
      await mutate(['cash-advance', id]);
      return res;
    },
  };
}

// ============== Corporate Cards ==============

export function useCorporateCards(
  params?: { employee_id?: number; status?: string; include_inactive?: boolean; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR<CorporateCard[]>(['corporate-cards', params], () => api.getCorporateCards(params), config);
}

export function useCorporateCardDetail(id?: number, config?: SWRConfiguration) {
  const key = id ? (['corporate-card', id] as const) : null;
  return useSWR<CorporateCard>(
    key,
    key ? ([, cardId]: [string, number]) => api.getCorporateCardDetail(cardId) : null,
    config
  );
}

export function useCorporateCardMutations() {
  const { mutate } = useSWRConfig();
  return {
    createCard: async (payload: CorporateCardCreatePayload) => {
      const res = await api.createCorporateCard(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'corporate-cards');
      return res;
    },
    updateCard: async (id: number, payload: CorporateCardUpdatePayload) => {
      const res = await api.updateCorporateCard(id, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'corporate-cards');
      await mutate(['corporate-card', id]);
      return res;
    },
    suspendCard: async (id: number) => {
      const res = await api.suspendCorporateCard(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'corporate-cards');
      await mutate(['corporate-card', id]);
      return res;
    },
    activateCard: async (id: number) => {
      const res = await api.activateCorporateCard(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'corporate-cards');
      await mutate(['corporate-card', id]);
      return res;
    },
    cancelCard: async (id: number) => {
      const res = await api.cancelCorporateCard(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'corporate-cards');
      await mutate(['corporate-card', id]);
      return res;
    },
    deleteCard: async (id: number) => {
      await api.deleteCorporateCard(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'corporate-cards');
    },
  };
}

// ============== Corporate Card Transactions ==============

export function useCorporateCardTransactions(
  params?: { card_id?: number; statement_id?: number; status?: string; unmatched_only?: boolean; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR<CorporateCardTransaction[]>(['card-transactions', params], () => api.getCorporateCardTransactions(params), config);
}

export function useCorporateCardTransactionDetail(id?: number, config?: SWRConfiguration) {
  const key = id ? (['card-transaction', id] as const) : null;
  return useSWR<CorporateCardTransaction>(
    key,
    key ? ([, txnId]: [string, number]) => api.getCorporateCardTransactionDetail(txnId) : null,
    config
  );
}

export function useTransactionMutations() {
  const { mutate } = useSWRConfig();
  const invalidateTransactions = () => mutate((key) => Array.isArray(key) && key[0] === 'card-transactions');
  const invalidateStatements = () => mutate((key) => Array.isArray(key) && key[0] === 'card-statements');

  return {
    createTransaction: async (payload: CorporateCardTransactionCreatePayload) => {
      const res = await api.createCorporateCardTransaction(payload);
      await invalidateTransactions();
      return res;
    },
    matchTransaction: async (id: number, expenseClaimLineId: number, confidence?: number) => {
      const res = await api.matchTransaction(id, expenseClaimLineId, confidence);
      await invalidateTransactions();
      await invalidateStatements();
      await mutate(['card-transaction', id]);
      return res;
    },
    unmatchTransaction: async (id: number) => {
      const res = await api.unmatchTransaction(id);
      await invalidateTransactions();
      await invalidateStatements();
      await mutate(['card-transaction', id]);
      return res;
    },
    disputeTransaction: async (id: number, reason: string) => {
      const res = await api.disputeTransaction(id, reason);
      await invalidateTransactions();
      await mutate(['card-transaction', id]);
      return res;
    },
    resolveDispute: async (id: number, resolutionNotes: string, newStatus?: string) => {
      const res = await api.resolveTransactionDispute(id, resolutionNotes, newStatus);
      await invalidateTransactions();
      await mutate(['card-transaction', id]);
      return res;
    },
    excludeTransaction: async (id: number) => {
      const res = await api.excludeTransaction(id);
      await invalidateTransactions();
      await invalidateStatements();
      await mutate(['card-transaction', id]);
      return res;
    },
    markPersonal: async (id: number) => {
      const res = await api.markTransactionPersonal(id);
      await invalidateTransactions();
      await invalidateStatements();
      await mutate(['card-transaction', id]);
      return res;
    },
    deleteTransaction: async (id: number) => {
      await api.deleteTransaction(id);
      await invalidateTransactions();
    },
  };
}

// ============== Corporate Card Statements ==============

export function useCorporateCardStatements(
  params?: { card_id?: number; status?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR<CorporateCardStatement[]>(['card-statements', params], () => api.getCorporateCardStatements(params), config);
}

export function useCorporateCardStatementDetail(id?: number, config?: SWRConfiguration) {
  const key = id ? (['card-statement', id] as const) : null;
  return useSWR<CorporateCardStatement>(
    key,
    key ? ([, stmtId]: [string, number]) => api.getCorporateCardStatementDetail(stmtId) : null,
    config
  );
}

export function useStatementTransactions(statementId?: number, status?: string, config?: SWRConfiguration) {
  const key = statementId ? (['statement-transactions', statementId, status] as const) : null;
  return useSWR<CorporateCardTransaction[]>(
    key,
    key ? () => api.getStatementTransactions(statementId!, status) : null,
    config
  );
}

export function useStatementMutations() {
  const { mutate } = useSWRConfig();
  const invalidateStatements = () => mutate((key) => Array.isArray(key) && key[0] === 'card-statements');
  const invalidateTransactions = () => mutate((key) => Array.isArray(key) && key[0] === 'card-transactions');

  return {
    createStatement: async (payload: { card_id: number; period_start: string; period_end: string; statement_date?: string; import_source?: string; original_filename?: string }) => {
      const res = await api.createCorporateCardStatement(payload);
      await invalidateStatements();
      return res;
    },
    importStatement: async (payload: StatementImportPayload) => {
      const res = await api.importStatement(payload);
      await invalidateStatements();
      await invalidateTransactions();
      return res;
    },
    reconcileStatement: async (id: number) => {
      const res = await api.reconcileStatement(id);
      await invalidateStatements();
      await mutate(['card-statement', id]);
      return res;
    },
    closeStatement: async (id: number) => {
      const res = await api.closeStatement(id);
      await invalidateStatements();
      await mutate(['card-statement', id]);
      return res;
    },
    reopenStatement: async (id: number) => {
      const res = await api.reopenStatement(id);
      await invalidateStatements();
      await mutate(['card-statement', id]);
      return res;
    },
    deleteStatement: async (id: number) => {
      await api.deleteStatement(id);
      await invalidateStatements();
      await invalidateTransactions();
    },
  };
}

// ============== Corporate Card Analytics ==============

export function useCardAnalyticsOverview(params?: { months?: number }, config?: SWRConfiguration) {
  return useSWR<CardAnalyticsOverview>(
    ['card-analytics-overview', params],
    () => api.getCardAnalyticsOverview(params),
    config
  );
}

export function useCardSpendTrend(params?: { months?: number }, config?: SWRConfiguration) {
  return useSWR<SpendTrendItem[]>(
    ['card-spend-trend', params],
    () => api.getCardSpendTrend(params),
    config
  );
}

export function useCardTopMerchants(params?: { days?: number; limit?: number }, config?: SWRConfiguration) {
  return useSWR<{ merchants: TopMerchant[]; total_spend: number; period_days: number }>(
    ['card-top-merchants', params],
    () => api.getCardTopMerchants(params),
    config
  );
}

export function useCardByCategory(params?: { days?: number }, config?: SWRConfiguration) {
  return useSWR<{ categories: CategoryBreakdown[]; total_spend: number; period_days: number }>(
    ['card-by-category', params],
    () => api.getCardByCategory(params),
    config
  );
}

export function useCardUtilization(params?: { days?: number }, config?: SWRConfiguration) {
  return useSWR<CardUtilization[]>(
    ['card-utilization', params],
    () => api.getCardUtilization(params),
    config
  );
}

export function useCardStatusBreakdown(params?: { days?: number }, config?: SWRConfiguration) {
  return useSWR<{ by_status: StatusBreakdownItem[]; totals: { count: number; amount: number }; period_days: number }>(
    ['card-status-breakdown', params],
    () => api.getCardStatusBreakdown(params),
    config
  );
}

export function useCardTopSpenders(params?: { days?: number; limit?: number }, config?: SWRConfiguration) {
  return useSWR<{ spenders: TopSpender[]; period_days: number }>(
    ['card-top-spenders', params],
    () => api.getCardTopSpenders(params),
    config
  );
}

export function useCardReconciliationTrend(params?: { months?: number }, config?: SWRConfiguration) {
  return useSWR<ReconciliationTrendItem[]>(
    ['card-reconciliation-trend', params],
    () => api.getCardReconciliationTrend(params),
    config
  );
}

export function useCardStatementSummary(config?: SWRConfiguration) {
  return useSWR<StatementSummary>(
    ['card-statement-summary'],
    () => api.getCardStatementSummary(),
    config
  );
}

// =============================================================================
// EXPENSE REPORTS
// =============================================================================

export function useExpenseSummaryReport(
  params?: { start_date?: string; end_date?: string },
  config?: SWRConfiguration
) {
  return useSWR<import('@/lib/expenses.types').ExpenseSummaryReport>(
    ['expense-summary-report', params],
    () => api.getExpenseSummaryReport(params),
    config
  );
}

export function useExpenseReportExports() {
  const downloadBlob = (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const getExtension = (format: string) => {
    if (format === 'excel') return 'xlsx';
    return format;
  };

  return {
    exportClaims: async (params: Parameters<typeof api.exportExpenseClaimsReport>[0]) => {
      const blob = await api.exportExpenseClaimsReport(params);
      const filename = params.filename || `expense_claims_${new Date().toISOString().slice(0, 10)}`;
      downloadBlob(blob, `${filename}.${getExtension(params.format)}`);
    },
    exportAdvances: async (params: Parameters<typeof api.exportCashAdvancesReport>[0]) => {
      const blob = await api.exportCashAdvancesReport(params);
      const filename = params.filename || `cash_advances_${new Date().toISOString().slice(0, 10)}`;
      downloadBlob(blob, `${filename}.${getExtension(params.format)}`);
    },
    exportTransactions: async (params: Parameters<typeof api.exportCardTransactionsReport>[0]) => {
      const blob = await api.exportCardTransactionsReport(params);
      const filename = params.filename || `card_transactions_${new Date().toISOString().slice(0, 10)}`;
      downloadBlob(blob, `${filename}.${getExtension(params.format)}`);
    },
  };
}
