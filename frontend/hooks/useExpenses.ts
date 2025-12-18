import useSWR, { SWRConfiguration, useSWRConfig } from 'swr';
import { expensesApi } from '@/lib/api';
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
  return useSWR<ExpenseCategory[]>(['expense-categories', params], () => expensesApi.getExpenseCategories(params), config);
}

export function useExpenseCategoryMutations() {
  const { mutate } = useSWRConfig();
  const invalidateCategories = () => mutate((key) => Array.isArray(key) && key[0] === 'expense-categories');

  return {
    createCategory: async (payload: ExpenseCategoryCreatePayload) => {
      const res = await expensesApi.createExpenseCategory(payload);
      await invalidateCategories();
      return res;
    },
    updateCategory: async (id: number, payload: ExpenseCategoryCreatePayload) => {
      const res = await expensesApi.updateExpenseCategory(id, payload);
      await invalidateCategories();
      return res;
    },
    deleteCategory: async (id: number) => {
      await expensesApi.deleteExpenseCategory(id);
      await invalidateCategories();
    },
  };
}

export function useExpensePolicies(params?: { include_inactive?: boolean; category_id?: number }, config?: SWRConfiguration) {
  return useSWR<ExpensePolicy[]>(['expense-policies', params], () => expensesApi.getExpensePolicies(params), config);
}

export function useExpensePolicyMutations() {
  const { mutate } = useSWRConfig();
  const invalidatePolicies = () => mutate((key) => Array.isArray(key) && key[0] === 'expense-policies');

  return {
    createPolicy: async (payload: ExpensePolicyCreatePayload) => {
      const res = await expensesApi.createExpensePolicy(payload);
      await invalidatePolicies();
      return res;
    },
    updatePolicy: async (id: number, payload: ExpensePolicyCreatePayload) => {
      const res = await expensesApi.updateExpensePolicy(id, payload);
      await invalidatePolicies();
      return res;
    },
    deletePolicy: async (id: number) => {
      await expensesApi.deleteExpensePolicy(id);
      await invalidatePolicies();
    },
  };
}

export function useExpenseClaims(params?: { status?: string; limit?: number; offset?: number }, config?: SWRConfiguration) {
  return useSWR<ExpenseClaim[]>(['expense-claims', params], () => expensesApi.getExpenseClaims(params), config);
}

export function useExpenseClaimDetail(id?: number, config?: SWRConfiguration) {
  const key = id ? (['expense-claim', id] as const) : null;
  return useSWR<ExpenseClaim>(
    key,
    key ? ([, claimId]: [string, number]) => expensesApi.getExpenseClaimDetail(claimId) : null,
    config
  );
}

export function useCashAdvances(params?: { status?: string; limit?: number; offset?: number }, config?: SWRConfiguration) {
  return useSWR<CashAdvance[]>(['cash-advances', params], () => expensesApi.getCashAdvances(params), config);
}

export function useCashAdvanceDetail(id?: number, config?: SWRConfiguration) {
  const key = id ? (['cash-advance', id] as const) : null;
  return useSWR<CashAdvance>(
    key,
    key ? ([, advanceId]: [string, number]) => expensesApi.getCashAdvanceDetail(advanceId) : null,
    config
  );
}

export function useExpenseMutations() {
  const { mutate } = useSWRConfig();
  return {
    createClaim: async (payload: ExpenseClaimCreatePayload) => {
      const res = await expensesApi.createExpenseClaim(payload);
      await mutate(['expense-claims']);
      return res;
    },
    submitClaim: async (id: number, companyCode?: string) => {
      const res = await expensesApi.submitExpenseClaim(id, companyCode);
      await mutate(['expense-claims']);
      await mutate(['expense-claim', id]);
      return res;
    },
    approveClaim: async (id: number) => {
      const res = await expensesApi.approveExpenseClaim(id);
      await mutate(['expense-claims']);
      await mutate(['expense-claim', id]);
      return res;
    },
    rejectClaim: async (id: number, reason: string) => {
      const res = await expensesApi.rejectExpenseClaim(id, reason);
      await mutate(['expense-claims']);
      await mutate(['expense-claim', id]);
      return res;
    },
    postClaim: async (id: number) => {
      const res = await expensesApi.postExpenseClaim(id);
      await mutate(['expense-claims']);
      await mutate(['expense-claim', id]);
      return res;
    },
    reverseClaim: async (id: number, reason: string) => {
      const res = await expensesApi.reverseExpenseClaim(id, reason);
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
      const res = await expensesApi.createCashAdvance(payload);
      await mutate(['cash-advances']);
      return res;
    },
    submitAdvance: async (id: number, companyCode?: string) => {
      const res = await expensesApi.submitCashAdvance(id, companyCode);
      await mutate(['cash-advances']);
      await mutate(['cash-advance', id]);
      return res;
    },
    approveAdvance: async (id: number) => {
      const res = await expensesApi.approveCashAdvance(id);
      await mutate(['cash-advances']);
      await mutate(['cash-advance', id]);
      return res;
    },
    rejectAdvance: async (id: number, reason: string) => {
      const res = await expensesApi.rejectCashAdvance(id, reason);
      await mutate(['cash-advances']);
      await mutate(['cash-advance', id]);
      return res;
    },
    disburseAdvance: async (id: number, payload: CashAdvanceDisbursePayload) => {
      const res = await expensesApi.disburseCashAdvance(id, payload);
      await mutate(['cash-advances']);
      await mutate(['cash-advance', id]);
      return res;
    },
    settleAdvance: async (id: number, payload: CashAdvanceSettlePayload) => {
      const res = await expensesApi.settleCashAdvance(id, payload);
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
  return useSWR<CorporateCard[]>(['corporate-cards', params], () => expensesApi.getCorporateCards(params), config);
}

export function useCorporateCardDetail(id?: number, config?: SWRConfiguration) {
  const key = id ? (['corporate-card', id] as const) : null;
  return useSWR<CorporateCard>(
    key,
    key ? ([, cardId]: [string, number]) => expensesApi.getCorporateCardDetail(cardId) : null,
    config
  );
}

export function useCorporateCardMutations() {
  const { mutate } = useSWRConfig();
  return {
    createCard: async (payload: CorporateCardCreatePayload) => {
      const res = await expensesApi.createCorporateCard(payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'corporate-cards');
      return res;
    },
    updateCard: async (id: number, payload: CorporateCardUpdatePayload) => {
      const res = await expensesApi.updateCorporateCard(id, payload);
      await mutate((key) => Array.isArray(key) && key[0] === 'corporate-cards');
      await mutate(['corporate-card', id]);
      return res;
    },
    suspendCard: async (id: number) => {
      const res = await expensesApi.suspendCorporateCard(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'corporate-cards');
      await mutate(['corporate-card', id]);
      return res;
    },
    activateCard: async (id: number) => {
      const res = await expensesApi.activateCorporateCard(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'corporate-cards');
      await mutate(['corporate-card', id]);
      return res;
    },
    cancelCard: async (id: number) => {
      const res = await expensesApi.cancelCorporateCard(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'corporate-cards');
      await mutate(['corporate-card', id]);
      return res;
    },
    deleteCard: async (id: number) => {
      await expensesApi.deleteCorporateCard(id);
      await mutate((key) => Array.isArray(key) && key[0] === 'corporate-cards');
    },
  };
}

// ============== Corporate Card Transactions ==============

export function useCorporateCardTransactions(
  params?: { card_id?: number; statement_id?: number; status?: string; unmatched_only?: boolean; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR<CorporateCardTransaction[]>(['card-transactions', params], () => expensesApi.getCorporateCardTransactions(params), config);
}

export function useCorporateCardTransactionDetail(id?: number, config?: SWRConfiguration) {
  const key = id ? (['card-transaction', id] as const) : null;
  return useSWR<CorporateCardTransaction>(
    key,
    key ? ([, txnId]: [string, number]) => expensesApi.getCorporateCardTransactionDetail(txnId) : null,
    config
  );
}

export function useTransactionMutations() {
  const { mutate } = useSWRConfig();
  const invalidateTransactions = () => mutate((key) => Array.isArray(key) && key[0] === 'card-transactions');
  const invalidateStatements = () => mutate((key) => Array.isArray(key) && key[0] === 'card-statements');

  return {
    createTransaction: async (payload: CorporateCardTransactionCreatePayload) => {
      const res = await expensesApi.createCorporateCardTransaction(payload);
      await invalidateTransactions();
      return res;
    },
    matchTransaction: async (id: number, expenseClaimLineId: number, confidence?: number) => {
      const res = await expensesApi.matchTransaction(id, expenseClaimLineId, confidence);
      await invalidateTransactions();
      await invalidateStatements();
      await mutate(['card-transaction', id]);
      return res;
    },
    unmatchTransaction: async (id: number) => {
      const res = await expensesApi.unmatchTransaction(id);
      await invalidateTransactions();
      await invalidateStatements();
      await mutate(['card-transaction', id]);
      return res;
    },
    disputeTransaction: async (id: number, reason: string) => {
      const res = await expensesApi.disputeTransaction(id, reason);
      await invalidateTransactions();
      await mutate(['card-transaction', id]);
      return res;
    },
    resolveDispute: async (id: number, resolutionNotes: string, newStatus?: string) => {
      const res = await expensesApi.resolveTransactionDispute(id, resolutionNotes, newStatus);
      await invalidateTransactions();
      await mutate(['card-transaction', id]);
      return res;
    },
    excludeTransaction: async (id: number) => {
      const res = await expensesApi.excludeTransaction(id);
      await invalidateTransactions();
      await invalidateStatements();
      await mutate(['card-transaction', id]);
      return res;
    },
    markPersonal: async (id: number) => {
      const res = await expensesApi.markTransactionPersonal(id);
      await invalidateTransactions();
      await invalidateStatements();
      await mutate(['card-transaction', id]);
      return res;
    },
    deleteTransaction: async (id: number) => {
      await expensesApi.deleteTransaction(id);
      await invalidateTransactions();
    },
  };
}

// ============== Corporate Card Statements ==============

export function useCorporateCardStatements(
  params?: { card_id?: number; status?: string; limit?: number; offset?: number },
  config?: SWRConfiguration
) {
  return useSWR<CorporateCardStatement[]>(['card-statements', params], () => expensesApi.getCorporateCardStatements(params), config);
}

export function useCorporateCardStatementDetail(id?: number, config?: SWRConfiguration) {
  const key = id ? (['card-statement', id] as const) : null;
  return useSWR<CorporateCardStatement>(
    key,
    key ? ([, stmtId]: [string, number]) => expensesApi.getCorporateCardStatementDetail(stmtId) : null,
    config
  );
}

export function useStatementTransactions(statementId?: number, status?: string, config?: SWRConfiguration) {
  const key = statementId ? (['statement-transactions', statementId, status] as const) : null;
  return useSWR<CorporateCardTransaction[]>(
    key,
    key ? () => expensesApi.getStatementTransactions(statementId!, status) : null,
    config
  );
}

export function useStatementMutations() {
  const { mutate } = useSWRConfig();
  const invalidateStatements = () => mutate((key) => Array.isArray(key) && key[0] === 'card-statements');
  const invalidateTransactions = () => mutate((key) => Array.isArray(key) && key[0] === 'card-transactions');

  return {
    createStatement: async (payload: { card_id: number; period_start: string; period_end: string; statement_date?: string; import_source?: string; original_filename?: string }) => {
      const res = await expensesApi.createCorporateCardStatement(payload);
      await invalidateStatements();
      return res;
    },
    importStatement: async (payload: StatementImportPayload) => {
      const res = await expensesApi.importStatement(payload);
      await invalidateStatements();
      await invalidateTransactions();
      return res;
    },
    reconcileStatement: async (id: number) => {
      const res = await expensesApi.reconcileStatement(id);
      await invalidateStatements();
      await mutate(['card-statement', id]);
      return res;
    },
    closeStatement: async (id: number) => {
      const res = await expensesApi.closeStatement(id);
      await invalidateStatements();
      await mutate(['card-statement', id]);
      return res;
    },
    reopenStatement: async (id: number) => {
      const res = await expensesApi.reopenStatement(id);
      await invalidateStatements();
      await mutate(['card-statement', id]);
      return res;
    },
    deleteStatement: async (id: number) => {
      await expensesApi.deleteStatement(id);
      await invalidateStatements();
      await invalidateTransactions();
    },
  };
}

// ============== Corporate Card Analytics ==============

export function useCardAnalyticsOverview(params?: { months?: number }, config?: SWRConfiguration) {
  return useSWR<CardAnalyticsOverview>(
    ['card-analytics-overview', params],
    () => expensesApi.getCardAnalyticsOverview(params),
    config
  );
}

export function useCardSpendTrend(params?: { months?: number }, config?: SWRConfiguration) {
  return useSWR<SpendTrendItem[]>(
    ['card-spend-trend', params],
    () => expensesApi.getCardSpendTrend(params),
    config
  );
}

export function useCardTopMerchants(params?: { days?: number; limit?: number }, config?: SWRConfiguration) {
  return useSWR<{ merchants: TopMerchant[]; total_spend: number; period_days: number }>(
    ['card-top-merchants', params],
    () => expensesApi.getCardTopMerchants(params),
    config
  );
}

export function useCardByCategory(params?: { days?: number }, config?: SWRConfiguration) {
  return useSWR<{ categories: CategoryBreakdown[]; total_spend: number; period_days: number }>(
    ['card-by-category', params],
    () => expensesApi.getCardByCategory(params),
    config
  );
}

export function useCardUtilization(params?: { days?: number }, config?: SWRConfiguration) {
  return useSWR<CardUtilization[]>(
    ['card-utilization', params],
    () => expensesApi.getCardUtilization(params),
    config
  );
}

export function useCardStatusBreakdown(params?: { days?: number }, config?: SWRConfiguration) {
  return useSWR<{ by_status: StatusBreakdownItem[]; totals: { count: number; amount: number }; period_days: number }>(
    ['card-status-breakdown', params],
    () => expensesApi.getCardStatusBreakdown(params),
    config
  );
}

export function useCardTopSpenders(params?: { days?: number; limit?: number }, config?: SWRConfiguration) {
  return useSWR<{ spenders: TopSpender[]; period_days: number }>(
    ['card-top-spenders', params],
    () => expensesApi.getCardTopSpenders(params),
    config
  );
}

export function useCardReconciliationTrend(params?: { months?: number }, config?: SWRConfiguration) {
  return useSWR<ReconciliationTrendItem[]>(
    ['card-reconciliation-trend', params],
    () => expensesApi.getCardReconciliationTrend(params),
    config
  );
}

export function useCardStatementSummary(config?: SWRConfiguration) {
  return useSWR<StatementSummary>(
    ['card-statement-summary'],
    () => expensesApi.getCardStatementSummary(),
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
    () => expensesApi.getExpenseSummaryReport(params),
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
    exportClaims: async (params: Parameters<typeof expensesApi.exportExpenseClaimsReport>[0]) => {
      const blob = await expensesApi.exportExpenseClaimsReport(params);
      const filename = params.filename || `expense_claims_${new Date().toISOString().slice(0, 10)}`;
      downloadBlob(blob, `${filename}.${getExtension(params.format)}`);
    },
    exportAdvances: async (params: Parameters<typeof expensesApi.exportCashAdvancesReport>[0]) => {
      const blob = await expensesApi.exportCashAdvancesReport(params);
      const filename = params.filename || `cash_advances_${new Date().toISOString().slice(0, 10)}`;
      downloadBlob(blob, `${filename}.${getExtension(params.format)}`);
    },
    exportTransactions: async (params: Parameters<typeof expensesApi.exportCardTransactionsReport>[0]) => {
      const blob = await expensesApi.exportCardTransactionsReport(params);
      const filename = params.filename || `card_transactions_${new Date().toISOString().slice(0, 10)}`;
      downloadBlob(blob, `${filename}.${getExtension(params.format)}`);
    },
  };
}
