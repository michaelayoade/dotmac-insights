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
    headers: getAuthHeaders(['contacts:write']),
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
    headers: getAuthHeaders(['contacts:write']),
  });
}

/**
 * Delete a test support ticket via API.
 */
export async function deleteTestTicket(
  request: APIRequestContext,
  ticketId: number
): Promise<void> {
  await request.delete(`${API_BASE}/api/support/tickets/${ticketId}`, {
    headers: getAuthHeaders(['support:write']),
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
    headers: getAuthHeaders(['support:write']),
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
  const response = await request.post(`${API_BASE}/api/notifications/webhooks`, {
    headers: getAuthHeaders(['books:admin']),
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
 * Delete a test webhook configuration via API.
 */
export async function deleteTestWebhook(
  request: APIRequestContext,
  webhookId: number
): Promise<void> {
  await request.delete(`${API_BASE}/api/notifications/webhooks/${webhookId}`, {
    headers: getAuthHeaders(['books:admin']),
  });
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
  const url = `${API_BASE}/api/v1/accounting/bank-transactions/${transactionId}`;
  const headers = getAuthHeaders(['books:write']);
  for (let attempt = 1; attempt <= 3; attempt += 1) {
    try {
      await request.delete(url, { headers });
      return;
    } catch (error) {
      if (attempt === 3) {
        console.warn(`Failed to delete test bank transaction ${transactionId}`, error);
        return;
      }
      await new Promise((resolve) => setTimeout(resolve, 500 * attempt));
    }
  }
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

// ==========================================
// CRM Helpers
// ==========================================

/**
 * Create a test CRM lead via API.
 */
export async function createTestLead(
  request: APIRequestContext,
  data: Partial<{
    name: string;
    company: string;
    email: string;
    phone: string;
    source: string;
    status: string;
  }> = {}
): Promise<{ id: number; name: string; status: string }> {
  const response = await request.post(`${API_BASE}/api/crm/leads`, {
    headers: getAuthHeaders(['crm:write']),
    data: {
      name: data.name || `Test Lead ${Date.now()}`,
      company: data.company || 'Test Company Ltd',
      email: data.email || `lead-${Date.now()}@example.com`,
      phone: data.phone || '+234800000000',
      source: data.source || 'Website',
      status: data.status || 'new',
    },
  });

  if (!response.ok()) {
    throw new Error(`Failed to create test lead: ${response.status()}`);
  }

  return response.json();
}

/**
 * Delete a test CRM lead via API.
 */
export async function deleteTestLead(
  request: APIRequestContext,
  leadId: number
): Promise<void> {
  await request.delete(`${API_BASE}/api/crm/leads/${leadId}`, {
    headers: getAuthHeaders(['crm:write']),
  });
}

/**
 * Create a test CRM opportunity via API.
 */
export async function createTestOpportunity(
  request: APIRequestContext,
  data: Partial<{
    name: string;
    value: number;
    stage: string;
    probability: number;
    close_date: string;
    contact_id: number;
  }> = {}
): Promise<{ id: number; name: string; value: number; stage: string }> {
  const response = await request.post(`${API_BASE}/api/crm/opportunities`, {
    headers: getAuthHeaders(['crm:write']),
    data: {
      name: data.name || `Test Opportunity ${Date.now()}`,
      value: data.value || 100000,
      stage: data.stage || 'qualification',
      probability: data.probability || 25,
      close_date: data.close_date || new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      contact_id: data.contact_id,
    },
  });

  if (!response.ok()) {
    throw new Error(`Failed to create test opportunity: ${response.status()}`);
  }

  return response.json();
}

/**
 * Delete a test CRM opportunity via API.
 */
export async function deleteTestOpportunity(
  request: APIRequestContext,
  opportunityId: number
): Promise<void> {
  await request.delete(`${API_BASE}/api/crm/opportunities/${opportunityId}`, {
    headers: getAuthHeaders(['crm:write']),
  });
}

/**
 * Create a test CRM activity via API.
 */
export async function createTestActivity(
  request: APIRequestContext,
  data: Partial<{
    type: string;
    subject: string;
    description: string;
    due_date: string;
    contact_id: number;
    lead_id: number;
    opportunity_id: number;
  }> = {}
): Promise<{ id: number; type: string; subject: string }> {
  const response = await request.post(`${API_BASE}/api/crm/activities`, {
    headers: getAuthHeaders(['crm:write']),
    data: {
      type: data.type || 'task',
      subject: data.subject || `Test Activity ${Date.now()}`,
      description: data.description || 'Test activity description',
      due_date: data.due_date || new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      contact_id: data.contact_id,
      lead_id: data.lead_id,
      opportunity_id: data.opportunity_id,
    },
  });

  if (!response.ok()) {
    throw new Error(`Failed to create test activity: ${response.status()}`);
  }

  return response.json();
}

/**
 * Delete a test CRM activity via API.
 */
export async function deleteTestActivity(
  request: APIRequestContext,
  activityId: number
): Promise<void> {
  await request.delete(`${API_BASE}/api/crm/activities/${activityId}`, {
    headers: getAuthHeaders(['crm:write']),
  });
}

// ==========================================
// Sales Helpers
// ==========================================

/**
 * Create a test sales quotation via API.
 */
export async function createTestQuotation(
  request: APIRequestContext,
  data: Partial<{
    customer_id: number;
    items: Array<{ item_name: string; qty: number; rate: number }>;
    valid_until: string;
  }> = {}
): Promise<{ id: number; quotation_number: string; total: number }> {
  const response = await request.post(`${API_BASE}/api/crm/sales/quotations`, {
    headers: getAuthHeaders(['sales:write']),
    data: {
      customer_id: data.customer_id || 1,
      items: data.items || [
        { item_name: 'Test Item', qty: 1, rate: 10000 },
      ],
      valid_until: data.valid_until || new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    },
  });

  if (!response.ok()) {
    throw new Error(`Failed to create test quotation: ${response.status()}`);
  }

  return response.json();
}

/**
 * Delete a test sales quotation via API.
 */
export async function deleteTestQuotation(
  request: APIRequestContext,
  quotationId: number
): Promise<void> {
  await request.delete(`${API_BASE}/api/crm/sales/quotations/${quotationId}`, {
    headers: getAuthHeaders(['sales:write']),
  });
}

/**
 * Create a test sales invoice via API.
 */
export async function createTestInvoice(
  request: APIRequestContext,
  data: Partial<{
    customer_id: number;
    items: Array<{ item_name: string; qty: number; rate: number }>;
    due_date: string;
    posting_date: string;
  }> = {}
): Promise<{ id: number; invoice_number: string; total: number; status: string }> {
  const response = await request.post(`${API_BASE}/api/sales/invoices`, {
    headers: getAuthHeaders(['sales:write']),
    data: {
      customer_id: data.customer_id || 1,
      items: data.items || [
        { item_name: 'Test Service', qty: 1, rate: 25000 },
      ],
      due_date: data.due_date || new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
      posting_date: data.posting_date || new Date().toISOString().split('T')[0],
    },
  });

  if (!response.ok()) {
    throw new Error(`Failed to create test invoice: ${response.status()}`);
  }

  return response.json();
}

/**
 * Delete a test sales invoice via API.
 */
export async function deleteTestInvoice(
  request: APIRequestContext,
  invoiceId: number
): Promise<void> {
  await request.delete(`${API_BASE}/api/sales/invoices/${invoiceId}`, {
    headers: getAuthHeaders(['sales:write']),
  });
}

// ==========================================
// Inventory Helpers
// ==========================================

/**
 * Create a test inventory item via API.
 */
export async function createTestInventoryItem(
  request: APIRequestContext,
  data: Partial<{
    item_name: string;
    item_code: string;
    item_group: string;
    stock_uom: string;
    is_stock_item: boolean;
  }> = {}
): Promise<{ id: number; item_name: string; item_code: string }> {
  const response = await request.post(`${API_BASE}/api/inventory/items`, {
    headers: getAuthHeaders(['inventory:write']),
    data: {
      item_name: data.item_name || `Test Item ${Date.now()}`,
      item_code: data.item_code || `ITEM-${Date.now()}`,
      item_group: data.item_group || 'Products',
      stock_uom: data.stock_uom || 'Nos',
      is_stock_item: data.is_stock_item ?? true,
    },
  });

  if (!response.ok()) {
    throw new Error(`Failed to create test inventory item: ${response.status()}`);
  }

  return response.json();
}

/**
 * Delete a test inventory item via API.
 */
export async function deleteTestInventoryItem(
  request: APIRequestContext,
  itemId: number
): Promise<void> {
  await request.delete(`${API_BASE}/api/inventory/items/${itemId}`, {
    headers: getAuthHeaders(['inventory:write']),
  });
}

/**
 * Create a test warehouse via API.
 */
export async function createTestWarehouse(
  request: APIRequestContext,
  data: Partial<{
    warehouse_name: string;
    warehouse_type: string;
    is_active: boolean;
  }> = {}
): Promise<{ id: number; warehouse_name: string }> {
  const response = await request.post(`${API_BASE}/api/inventory/warehouses`, {
    headers: getAuthHeaders(['inventory:write']),
    data: {
      warehouse_name: data.warehouse_name || `Test Warehouse ${Date.now()}`,
      warehouse_type: data.warehouse_type || 'Stores',
      is_active: data.is_active ?? true,
    },
  });

  if (!response.ok()) {
    throw new Error(`Failed to create test warehouse: ${response.status()}`);
  }

  return response.json();
}

/**
 * Delete a test warehouse via API.
 */
export async function deleteTestWarehouse(
  request: APIRequestContext,
  warehouseId: number
): Promise<void> {
  await request.delete(`${API_BASE}/api/inventory/warehouses/${warehouseId}`, {
    headers: getAuthHeaders(['inventory:write']),
  });
}

/**
 * Create a test stock entry via API.
 */
export async function createTestStockEntry(
  request: APIRequestContext,
  data: Partial<{
    purpose: string;
    items: Array<{ item_code: string; qty: number; warehouse: string }>;
    posting_date: string;
  }> = {}
): Promise<{ id: number; stock_entry_number: string }> {
  const response = await request.post(`${API_BASE}/api/inventory/stock-entries`, {
    headers: getAuthHeaders(['inventory:write']),
    data: {
      purpose: data.purpose || 'Material Receipt',
      items: data.items || [
        { item_code: 'ITEM-001', qty: 10, warehouse: 'Main Warehouse' },
      ],
      posting_date: data.posting_date || new Date().toISOString().split('T')[0],
    },
  });

  if (!response.ok()) {
    throw new Error(`Failed to create test stock entry: ${response.status()}`);
  }

  return response.json();
}

// ==========================================
// Projects Helpers
// ==========================================

/**
 * Create a test project via API.
 */
export async function createTestProject(
  request: APIRequestContext,
  data: Partial<{
    project_name: string;
    status: string;
    expected_start_date: string;
    expected_end_date: string;
  }> = {}
): Promise<{ id: number; project_name: string; status: string }> {
  const response = await request.post(`${API_BASE}/api/projects`, {
    headers: getAuthHeaders(['projects:write']),
    data: {
      project_name: data.project_name || `Test Project ${Date.now()}`,
      status: data.status || 'Open',
      expected_start_date: data.expected_start_date || new Date().toISOString().split('T')[0],
      expected_end_date: data.expected_end_date || new Date(Date.now() + 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    },
  });

  if (!response.ok()) {
    throw new Error(`Failed to create test project: ${response.status()}`);
  }

  return response.json();
}

/**
 * Delete a test project via API.
 */
export async function deleteTestProject(
  request: APIRequestContext,
  projectId: number
): Promise<void> {
  await request.delete(`${API_BASE}/api/projects/${projectId}`, {
    headers: getAuthHeaders(['projects:write']),
  });
}

/**
 * Create a test project task via API.
 */
export async function createTestProjectTask(
  request: APIRequestContext,
  projectId: number,
  data: Partial<{
    subject: string;
    status: string;
    priority: string;
    expected_time: number;
  }> = {}
): Promise<{ id: number; subject: string; status: string }> {
  const response = await request.post(`${API_BASE}/api/projects/${projectId}/tasks`, {
    headers: getAuthHeaders(['projects:write']),
    data: {
      subject: data.subject || `Test Task ${Date.now()}`,
      status: data.status || 'Open',
      priority: data.priority || 'Medium',
      expected_time: data.expected_time || 4,
    },
  });

  if (!response.ok()) {
    throw new Error(`Failed to create test project task: ${response.status()}`);
  }

  return response.json();
}

// ==========================================
// Accounting Helpers
// ==========================================

/**
 * Create a test journal entry via API.
 */
export async function createTestJournalEntry(
  request: APIRequestContext,
  data: Partial<{
    posting_date: string;
    reference_number: string;
    accounts: Array<{ account: string; debit: number; credit: number }>;
  }> = {}
): Promise<{ id: number; entry_number: string; status: string }> {
  const response = await request.post(`${API_BASE}/api/accounting/journal-entries`, {
    headers: getAuthHeaders(['accounting:write']),
    data: {
      posting_date: data.posting_date || new Date().toISOString().split('T')[0],
      reference_number: data.reference_number || `JV-${Date.now()}`,
      accounts: data.accounts || [
        { account: 'Cash', debit: 1000, credit: 0 },
        { account: 'Sales', debit: 0, credit: 1000 },
      ],
    },
  });

  if (!response.ok()) {
    throw new Error(`Failed to create test journal entry: ${response.status()}`);
  }

  return response.json();
}

/**
 * Delete a test journal entry via API.
 */
export async function deleteTestJournalEntry(
  request: APIRequestContext,
  entryId: number
): Promise<void> {
  await request.delete(`${API_BASE}/api/accounting/journal-entries/${entryId}`, {
    headers: getAuthHeaders(['accounting:write']),
  });
}

// ==========================================
// Inbox Helpers
// ==========================================

/**
 * Create a test conversation via API.
 */
export async function createTestConversation(
  request: APIRequestContext,
  data: Partial<{
    contact_id: number;
    channel: string;
    subject: string;
    initial_message: string;
  }> = {}
): Promise<{ id: number; channel: string; status: string }> {
  const response = await request.post(`${API_BASE}/api/inbox/conversations`, {
    headers: getAuthHeaders(['inbox:write']),
    data: {
      contact_id: data.contact_id || 1,
      channel: data.channel || 'email',
      subject: data.subject || `Test Conversation ${Date.now()}`,
      initial_message: data.initial_message || 'This is a test message',
    },
  });

  if (!response.ok()) {
    throw new Error(`Failed to create test conversation: ${response.status()}`);
  }

  return response.json();
}

/**
 * Delete a test conversation via API.
 */
export async function deleteTestConversation(
  request: APIRequestContext,
  conversationId: number
): Promise<void> {
  await request.delete(`${API_BASE}/api/inbox/conversations/${conversationId}`, {
    headers: getAuthHeaders(['inbox:write']),
  });
}
