import useSWR, { SWRConfiguration, useSWRConfig } from 'swr';
import { api } from '@/lib/api';
import type {
  ExpenseClaim,
  ExpenseCategory,
  CashAdvance,
  ExpenseClaimCreatePayload,
  CashAdvanceCreatePayload,
  CashAdvanceDisbursePayload,
  CashAdvanceSettlePayload,
} from '@/lib/expenses.types';

export function useExpenseCategories(params?: { include_inactive?: boolean }, config?: SWRConfiguration) {
  return useSWR<ExpenseCategory[]>(['expense-categories', params], () => api.getExpenseCategories(params), config);
}

export function useExpenseClaims(params?: { status?: string; limit?: number; offset?: number }, config?: SWRConfiguration) {
  return useSWR<ExpenseClaim[]>(['expense-claims', params], () => api.getExpenseClaims(params), config);
}

export function useExpenseClaimDetail(id?: number, config?: SWRConfiguration) {
  return useSWR<ExpenseClaim>(id ? ['expense-claim', id] : null, () => (id ? api.getExpenseClaimDetail(id) : null), config);
}

export function useCashAdvances(params?: { status?: string; limit?: number; offset?: number }, config?: SWRConfiguration) {
  return useSWR<CashAdvance[]>(['cash-advances', params], () => api.getCashAdvances(params), config);
}

export function useCashAdvanceDetail(id?: number, config?: SWRConfiguration) {
  return useSWR<CashAdvance>(id ? ['cash-advance', id] : null, () => (id ? api.getCashAdvanceDetail(id) : null), config);
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
