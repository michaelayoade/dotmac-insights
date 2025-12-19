/**
 * API helper functions for E2E tests.
 *
 * These helpers interact with the backend API to seed test data,
 * clean up after tests, and verify API state.
 */

import { type APIRequestContext } from '@playwright/test';
import { createTestToken, type Scope } from './auth';

const API_BASE = process.env.E2E_API_URL || 'http://localhost:8000';

/**
 * Get API request headers with authentication.
 */
export function getAuthHeaders(scopes: Scope[] = []): Record<string, string> {
  const token = createTestToken(scopes);
  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
}

/**
 * Create a test contact via API.
 */
export async function createTestContact(
  request: APIRequestContext,
  data: Partial<{
    name: string;
    email: string;
    phone: string;
    company: string;
    contact_type: string;
  }> = {}
): Promise<{ id: number; name: string; email: string }> {
  const response = await request.post(`${API_BASE}/api/contacts`, {
    headers: getAuthHeaders(['customers:write']),
    data: {
      name: data.name || `Test Contact ${Date.now()}`,
      email: data.email || `test-${Date.now()}@example.com`,
      phone: data.phone || '+234800000000',
      company: data.company || 'Test Company',
      contact_type: data.contact_type || 'customer',
    },
  });

  if (!response.ok()) {
    throw new Error(`Failed to create test contact: ${response.status()}`);
  }

  return response.json();
}

/**
 * Delete a test contact via API.
 */
export async function deleteTestContact(
  request: APIRequestContext,
  contactId: number
): Promise<void> {
  await request.delete(`${API_BASE}/api/contacts/${contactId}`, {
    headers: getAuthHeaders(['customers:write']),
  });
}

/**
 * Create a test support ticket via API.
 */
export async function createTestTicket(
  request: APIRequestContext,
  data: Partial<{
    subject: string;
    description: string;
    priority: string;
    contact_id: number;
  }> = {}
): Promise<{ id: number; ticket_number: string; subject: string }> {
  const response = await request.post(`${API_BASE}/api/support/tickets`, {
    headers: getAuthHeaders(['customers:write']),
    data: {
      subject: data.subject || `Test Ticket ${Date.now()}`,
      description: data.description || 'Test ticket description',
      priority: data.priority || 'medium',
      contact_id: data.contact_id,
    },
  });

  if (!response.ok()) {
    throw new Error(`Failed to create test ticket: ${response.status()}`);
  }

  return response.json();
}

/**
 * Create a test expense claim via API.
 */
export async function createTestExpenseClaim(
  request: APIRequestContext,
  data: Partial<{
    title: string;
    amount: number;
    currency: string;
    employee_id: number;
  }> = {}
): Promise<{ id: number; claim_number: string; title: string }> {
  const response = await request.post(`${API_BASE}/api/expenses/claims`, {
    headers: getAuthHeaders(['hr:write']),
    data: {
      title: data.title || `Test Expense ${Date.now()}`,
      total_claimed_amount: data.amount || 10000,
      currency: data.currency || 'NGN',
      employee_id: data.employee_id || 1,
      claim_date: new Date().toISOString().split('T')[0],
    },
  });

  if (!response.ok()) {
    throw new Error(`Failed to create test expense claim: ${response.status()}`);
  }

  return response.json();
}

/**
 * Create a test cash advance via API.
 */
export async function createTestCashAdvance(
  request: APIRequestContext,
  data: Partial<{
    purpose: string;
    amount: number;
    currency: string;
    employee_id: number;
  }> = {}
): Promise<{ id: number; advance_number: string; purpose: string }> {
  const response = await request.post(`${API_BASE}/api/expenses/cash-advances`, {
    headers: getAuthHeaders(['hr:write']),
    data: {
      purpose: data.purpose || `Test Advance ${Date.now()}`,
      requested_amount: data.amount || 50000,
      currency: data.currency || 'NGN',
      employee_id: data.employee_id || 1,
      request_date: new Date().toISOString().split('T')[0],
    },
  });

  if (!response.ok()) {
    throw new Error(`Failed to create test cash advance: ${response.status()}`);
  }

  return response.json();
}

/**
 * Create a test webhook configuration via API.
 */
export async function createTestWebhook(
  request: APIRequestContext,
  data: Partial<{
    name: string;
    url: string;
    events: string[];
  }> = {}
): Promise<{ id: number; name: string; secret: string }> {
  const response = await request.post(`${API_BASE}/api/admin/webhooks`, {
    headers: getAuthHeaders(['admin:write']),
    data: {
      name: data.name || `Test Webhook ${Date.now()}`,
      url: data.url || 'https://example.com/webhook',
      events: data.events || ['contact.created', 'contact.updated'],
    },
  });

  if (!response.ok()) {
    throw new Error(`Failed to create test webhook: ${response.status()}`);
  }

  return response.json();
}

/**
 * Create a test bank transaction via API.
 */
export async function createTestBankTransaction(
  request: APIRequestContext,
  data: Partial<{
    date: string;
    bank_account: string;
    deposit: number;
    withdrawal: number;
    currency: string;
    description: string;
    reference_number: string;
    transaction_type: string;
    payee_name: string;
    payee_account: string;
  }> = {}
): Promise<{ id: number; date: string; amount: number }> {
  const response = await request.post(`${API_BASE}/api/v1/accounting/bank-transactions`, {
    headers: getAuthHeaders(['books:write']),
    data: {
      date: data.date || new Date().toISOString().split('T')[0],
      bank_account: data.bank_account || 'E2E Test Account',
      deposit: data.deposit ?? 1000,
      withdrawal: data.withdrawal ?? 0,
      currency: data.currency || 'NGN',
      description: data.description || `E2E Bank Transaction ${Date.now()}`,
      reference_number: data.reference_number || `E2E-${Date.now()}`,
      transaction_type: data.transaction_type || 'credit',
      payee_name: data.payee_name || 'E2E Payee',
      payee_account: data.payee_account || '0000000000',
      splits: [],
    },
  });

  if (!response.ok()) {
    throw new Error(`Failed to create test bank transaction: ${response.status()}`);
  }

  return response.json();
}

/**
 * Delete a test bank transaction via API.
 */
export async function deleteTestBankTransaction(
  request: APIRequestContext,
  transactionId: number
): Promise<void> {
  await request.delete(`${API_BASE}/api/v1/accounting/bank-transactions/${transactionId}`, {
    headers: getAuthHeaders(['books:write']),
  });
}

/**
 * Clean up test data by deleting resources created during tests.
 * Uses soft patterns that don't fail if resources don't exist.
 */
export async function cleanupTestData(request: APIRequestContext): Promise<void> {
  // This is a helper for test teardown - implementations depend on backend support
  // In practice, you might have a dedicated cleanup endpoint or use database transactions
}

/**
 * Wait for API to be ready (useful in CI environments).
 */
export async function waitForApiReady(
  request: APIRequestContext,
  maxWaitMs = 30000
): Promise<boolean> {
  const startTime = Date.now();

  while (Date.now() - startTime < maxWaitMs) {
    try {
      const response = await request.get(`${API_BASE}/health`);
      if (response.ok()) {
        return true;
      }
    } catch {
      // API not ready yet
    }

    await new Promise((resolve) => setTimeout(resolve, 1000));
  }

  return false;
}

/**
 * Get the count of items from a paginated API response.
 */
export async function getApiItemCount(
  request: APIRequestContext,
  endpoint: string,
  scopes: Scope[] = ['customers:read']
): Promise<number> {
  const response = await request.get(`${API_BASE}/api${endpoint}`, {
    headers: getAuthHeaders(scopes),
  });

  if (!response.ok()) {
    throw new Error(`Failed to get items from ${endpoint}: ${response.status()}`);
  }

  const data = await response.json();
  return data.total || data.data?.length || data.items?.length || 0;
}
