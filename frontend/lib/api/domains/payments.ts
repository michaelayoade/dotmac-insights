/**
 * Payments Domain API
 * Includes: Payment Gateway, Transfers, Open Banking, Account Resolution
 */

import { fetchApi } from '../core';

// =============================================================================
// TYPES
// =============================================================================

// Gateway Payments
export interface GatewayPayment {
  id: number;
  reference: string;
  provider: string;
  provider_reference?: string;
  amount: number;
  currency: string;
  status: string;
  customer_email?: string;
  fees?: number;
  paid_at?: string;
  created_at: string;
  extra_data?: Record<string, unknown>;
}

export interface GatewayPaymentListResponse {
  items: GatewayPayment[];
  limit: number;
  offset: number;
}

export interface InitializePaymentRequest {
  amount: number;
  email: string;
  currency?: string;
  callback_url?: string;
  reference?: string;
  channels?: string[];
  invoice_id?: number;
  customer_id?: number;
  metadata?: Record<string, unknown>;
  provider?: string;
}

export interface InitializePaymentResponse {
  authorization_url: string;
  access_code: string;
  reference: string;
  provider: string;
}

export interface VerifyPaymentResponse {
  reference: string;
  provider_reference: string;
  status: string;
  amount: number;
  currency: string;
  paid_at?: string;
  channel?: string;
  fees: number;
  customer_email?: string;
}

// Gateway Transfers
export interface GatewayTransfer {
  id: number;
  reference: string;
  provider: string;
  provider_reference?: string;
  transfer_type: string;
  amount: number;
  currency: string;
  status: string;
  recipient_account: string;
  recipient_bank_code: string;
  recipient_name: string;
  reason?: string;
  fee?: number;
  failure_reason?: string;
  created_at: string;
  completed_at?: string;
}

export interface GatewayTransferListResponse {
  items: GatewayTransfer[];
  limit: number;
  offset: number;
}

export interface TransferRecipient {
  account_number: string;
  bank_code: string;
  account_name?: string;
}

export interface InitiateTransferRequest {
  amount: number;
  recipient: TransferRecipient;
  currency?: string;
  reference?: string;
  reason?: string;
  narration?: string;
  transfer_type?: string;
  metadata?: Record<string, unknown>;
  provider?: string;
}

export interface TransferResponse {
  reference: string;
  provider_reference: string;
  status: string;
  amount: number;
  currency: string;
  recipient_code: string;
  fee: number;
}

// Banks & Account Resolution
export interface BankInfo {
  code: string;
  name: string;
  slug: string;
  is_active: boolean;
  country: string;
  currency: string;
}

export interface BankListResponse {
  banks: BankInfo[];
  count?: number;
}

export interface ResolveAccountRequest {
  account_number: string;
  bank_code: string;
}

export interface ResolveAccountResponse {
  account_number: string;
  account_name: string;
  bank_code: string;
  bank_name?: string;
}

// Open Banking
export interface OpenBankingConnection {
  id: number;
  provider: string;
  provider_account_id: string;
  account_number: string;
  bank_name: string;
  account_name: string;
  account_type: string;
  currency: string;
  balance?: number;
  status: string;
}

export interface OpenBankingConnectionListResponse {
  items?: OpenBankingConnection[];
  data?: OpenBankingConnection[];
  total?: number;
}

export interface OpenBankingTransaction {
  transaction_id: string;
  date: string;
  narration: string;
  type: string;
  amount: number;
  balance?: number;
  category?: string;
}

export interface OpenBankingTransactionListResponse {
  transactions?: OpenBankingTransaction[];
  data?: OpenBankingTransaction[];
  total?: number;
}

export interface OpenBankingBalance {
  available_balance: number;
  ledger_balance: number;
  currency: string;
  last_updated?: string;
}

export interface OpenBankingIdentity {
  full_name: string;
  email?: string;
  phone?: string;
  bvn?: string;
  address?: string;
}

// =============================================================================
// PAYMENTS API
// =============================================================================

export const paymentsApi = {
  // -------------------------------------------------------------------------
  // Gateway Payments
  // -------------------------------------------------------------------------

  /** List gateway payments with optional filters */
  getPayments: (params?: {
    status?: string;
    provider?: string;
    customer_id?: number;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<GatewayPaymentListResponse>('/integrations/payments/', { params }),

  /** Get a specific payment by reference */
  getPayment: (reference: string) =>
    fetchApi<GatewayPayment>(`/integrations/payments/${reference}`),

  /** Initialize a new payment */
  initializePayment: (body: InitializePaymentRequest) =>
    fetchApi<InitializePaymentResponse>('/integrations/payments/initialize', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** Verify a payment by reference */
  verifyPayment: (reference: string) =>
    fetchApi<VerifyPaymentResponse>(`/integrations/payments/verify/${reference}`),

  /** Refund a payment */
  refundPayment: (reference: string, body?: { amount?: number; reason?: string }) =>
    fetchApi<{ status: string; reference: string }>(`/integrations/payments/${reference}/refund`, {
      method: 'POST',
      body: JSON.stringify(body || {}),
    }),

  // -------------------------------------------------------------------------
  // Gateway Transfers
  // -------------------------------------------------------------------------

  /** List transfers with optional filters */
  getTransfers: (params?: {
    status?: string;
    transfer_type?: string;
    provider?: string;
    limit?: number;
    offset?: number;
  }) =>
    fetchApi<GatewayTransferListResponse>('/integrations/transfers/', { params }),

  /** Get a specific transfer by reference */
  getTransfer: (reference: string) =>
    fetchApi<GatewayTransfer>(`/integrations/transfers/${reference}`),

  /** Initiate a new transfer */
  initiateTransfer: (body: InitiateTransferRequest) =>
    fetchApi<TransferResponse>('/integrations/transfers/initiate', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** Verify a transfer by reference */
  verifyTransfer: (reference: string) =>
    fetchApi<TransferResponse>(`/integrations/transfers/verify/${reference}`),

  /** Pay multiple payroll transfers */
  payPayrollTransfers: (payload: { transfer_ids: number[]; provider?: string }) =>
    fetchApi<{ status: string; processed: number; failed: number }>(
      '/integrations/transfers/pay-payroll',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    ),

  // -------------------------------------------------------------------------
  // Banks & Account Resolution
  // -------------------------------------------------------------------------

  /** Get list of banks for a country */
  getBanks: (params?: { country?: string; currency?: string }) =>
    fetchApi<BankListResponse>('/integrations/banks', { params }),

  /** Resolve/verify a bank account */
  resolveAccount: (body: ResolveAccountRequest | string, provider?: string) => {
    // Support both object and string (account_number only) for backward compatibility
    const payload = typeof body === 'string'
      ? { account_number: body, bank_code: provider || '' }
      : body;
    return fetchApi<ResolveAccountResponse>('/integrations/banks/resolve', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  // -------------------------------------------------------------------------
  // Open Banking
  // -------------------------------------------------------------------------

  /** List open banking connections */
  getOpenBankingConnections: (params?: {
    customer_id?: number;
    provider?: string;
    status?: string;
  }) =>
    fetchApi<OpenBankingConnection[] | OpenBankingConnectionListResponse>(
      '/integrations/openbanking/accounts',
      { params }
    ),

  /** Get a specific open banking connection */
  getOpenBankingConnection: (id: number) =>
    fetchApi<OpenBankingConnection>(`/integrations/openbanking/accounts/${id}`),

  /** Get balance for an open banking connection */
  getOpenBankingBalance: (id: number) =>
    fetchApi<OpenBankingBalance>(`/integrations/openbanking/accounts/${id}/balance`),

  /** Get transactions for an open banking connection */
  getOpenBankingTransactions: (
    id: number,
    params?: { start_date?: string; end_date?: string; limit?: number }
  ) =>
    fetchApi<OpenBankingTransaction[] | OpenBankingTransactionListResponse>(
      `/integrations/openbanking/accounts/${id}/transactions`,
      { params }
    ),

  /** Get identity info for an open banking connection */
  getOpenBankingIdentity: (id: number) =>
    fetchApi<OpenBankingIdentity>(`/integrations/openbanking/accounts/${id}/identity`),

  /** Unlink an open banking account */
  unlinkOpenBankingAccount: (id: number) =>
    fetchApi<{ status: string }>(`/integrations/openbanking/accounts/${id}/unlink`, {
      method: 'POST',
    }),

  /** Refresh an open banking connection */
  refreshOpenBankingConnection: (id: number) =>
    fetchApi<{ status: string }>(`/integrations/openbanking/accounts/${id}/refresh`, {
      method: 'POST',
    }),
};

// =============================================================================
// STANDALONE EXPORTS (for backward compatibility)
// =============================================================================

// Gateway Payments
export const getGatewayPayments = paymentsApi.getPayments;
export const getGatewayPayment = paymentsApi.getPayment;
export const initializePayment = paymentsApi.initializePayment;
export const verifyPayment = paymentsApi.verifyPayment;
export const refundPayment = paymentsApi.refundPayment;

// Gateway Transfers
export const getGatewayTransfers = paymentsApi.getTransfers;
export const getGatewayTransfer = paymentsApi.getTransfer;
export const initiateTransfer = paymentsApi.initiateTransfer;
export const verifyTransfer = paymentsApi.verifyTransfer;
export const payPayrollTransfers = paymentsApi.payPayrollTransfers;

// Banks & Account Resolution
export const getBanks = paymentsApi.getBanks;
export const resolveAccount = paymentsApi.resolveAccount;

// Open Banking
export const getOpenBankingConnections = paymentsApi.getOpenBankingConnections;
export const getOpenBankingConnection = paymentsApi.getOpenBankingConnection;
export const getOpenBankingBalance = paymentsApi.getOpenBankingBalance;
export const getOpenBankingTransactions = paymentsApi.getOpenBankingTransactions;
export const getOpenBankingIdentity = paymentsApi.getOpenBankingIdentity;
export const unlinkOpenBankingAccount = paymentsApi.unlinkOpenBankingAccount;
export const refreshOpenBankingConnection = paymentsApi.refreshOpenBankingConnection;
