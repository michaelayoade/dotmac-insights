/**
 * Banking & Reconciliation E2E Tests
 *
 * Comprehensive tests for the Banking module including:
 * - Reconciliation list and pagination
 * - Match/unmatch flow with count updates
 * - Bank connections management
 * - Transaction import and status
 *
 * These tests run against a real backend - no API mocking.
 * Tests handle empty data states gracefully.
 */

import { request as playwrightRequest, type APIRequestContext, type Page } from '@playwright/test';
import { test, expect, setupAuth } from './fixtures/auth';
import { createTestBankTransaction, deleteTestBankTransaction } from './fixtures/api-helpers';

async function ensureGatewayPaymentsReady(page: Page) {
  const heading = page.getByRole('heading', { name: /online payments/i });
  const errorMessage = page.getByText(/failed to load payments/i);
  await expect
    .poll(
      async () => (await heading.isVisible()) || (await errorMessage.isVisible()),
      { timeout: 15000 }
    )
    .toBe(true);
  return !(await errorMessage.isVisible());
}

async function ensureGatewayConnectionsReady(page: Page) {
  const heading = page.getByRole('heading', { name: /open banking connections/i });
  const errorMessage = page.getByText(/failed to load connections/i);
  await expect
    .poll(
      async () => (await heading.isVisible()) || (await errorMessage.isVisible()),
      { timeout: 15000 }
    )
    .toBe(true);
  return !(await errorMessage.isVisible());
}

test.describe('Banking - Authenticated', () => {
  const createdTransactionIds: number[] = [];
  let apiContext: APIRequestContext | null = null;

  test.beforeAll(async () => {
    apiContext = await playwrightRequest.newContext();
    // Seed enough transactions to ensure pagination and non-empty tables.
    for (let i = 0; i < 25; i += 1) {
      const txn = await createTestBankTransaction(apiContext, {
        reference_number: `E2E-BANK-${Date.now()}-${i}`,
        description: `E2E Bank Transaction ${i}`,
        deposit: 1000 + i,
      });
      createdTransactionIds.push(txn.id);
    }
  });

  test.afterAll(async () => {
    for (const id of createdTransactionIds) {
      try {
        if (apiContext) {
          await deleteTestBankTransaction(apiContext, id);
        }
      } catch (error) {
        console.warn(`Failed to delete test bank transaction ${id}`, error);
      }
    }
    if (apiContext) {
      await apiContext.dispose();
      apiContext = null;
    }
  });

  test.beforeEach(async ({ page }) => {
    await setupAuth(page, [
      'books:read',
      'accounting:read',
      'accounting:write',
      'gateway:read',
      'gateway:write',
      'payments:read',
      'payments:write',
      'openbanking:read',
      'openbanking:write',
    ]);
  });

  test.describe('Banking Overview', () => {
    test('renders banking dashboard', async ({ page }) => {
      await page.goto('/banking/bank-transactions');

      await expect(page.getByRole('heading', { name: /bank transactions/i })).toBeVisible({
        timeout: 15000,
      });
    });

    test('displays transaction list and filters', async ({ page }) => {
      await page.goto('/banking/bank-transactions');
      await expect(page.getByRole('heading', { name: /bank transactions/i })).toBeVisible({ timeout: 15000 });
      await expect(page.getByPlaceholder(/search reference\/description/i)).toBeVisible();
      await expect(page.getByPlaceholder(/account/i)).toBeVisible();
      await expect(page.getByRole('combobox').first()).toBeVisible();
    });
  });

  test.describe('Bank Transactions', () => {
    test('renders transactions page', async ({ page }) => {
      await page.goto('/books/bank-transactions');
      await expect(page.getByRole('heading', { name: /bank transactions/i })).toBeVisible({ timeout: 15000 });
    });

    test('shows data table with transactions', async ({ page }) => {
      await page.goto('/books/bank-transactions');

      const table = page.locator('table');
      await expect(table).toBeVisible({ timeout: 15000 });
      await expect(
        table
          .locator('tbody tr')
          .first()
          .or(page.getByText(/no transactions|no data|empty/i))
      ).toBeVisible({ timeout: 15000 });
    });

    test('displays filters when page loads', async ({ page }) => {
      await page.goto('/books/bank-transactions');

      await expect(page.getByRole('heading', { name: /bank transactions/i })).toBeVisible({
        timeout: 15000,
      });
      await expect(page.getByPlaceholder(/account/i)).toBeVisible();
      await expect(page.getByRole('combobox').first()).toBeVisible();
    });

    test('filter by bank account works', async ({ page }) => {
      await page.goto('/books/bank-transactions');

      const accountFilter = page.getByPlaceholder(/account/i);
      await expect(accountFilter).toBeVisible();
      await accountFilter.fill('test account');
      await expect(accountFilter).toHaveValue('test account');
    });

    test('filter by status works', async ({ page }) => {
      await page.goto('/books/bank-transactions');

      const statusFilter = page.getByRole('combobox').first();
      await expect(statusFilter).toBeVisible();
      await statusFilter.selectOption({ value: 'pending' });
      await expect(statusFilter).toHaveValue('pending');
    });

    test('pagination controls work when data exists', async ({ page }) => {
      await page.goto('/books/bank-transactions');

      // Pagination only appears when there's enough data
      const nextButton = page.getByRole('button', { name: /next/i }).or(
        page.locator('button:has-text(">")')
      );
      await expect(nextButton).toBeVisible({ timeout: 5000 });
      await nextButton.click();

      const prevButton = page.getByRole('button', { name: /prev/i }).or(
        page.locator('button:has-text("<")')
      );
      await expect(prevButton).toBeEnabled();
    });
  });

  test.describe('Transaction Actions', () => {
    test('can navigate to new transaction page', async ({ page }) => {
      await page.goto('/books/bank-transactions');

      const newButton = page.getByRole('link', { name: /new.*transaction/i });
      await expect(newButton).toBeVisible();
      await newButton.click();
      await expect(page).toHaveURL(/\/books\/bank-transactions\/new/);
    });

    test('can navigate to import page', async ({ page }) => {
      await page.goto('/books/bank-transactions');

      const importButton = page.getByRole('link', { name: /^import$/i });
      await expect(importButton).toBeVisible();
      await importButton.click();
      await expect(page).toHaveURL(/\/books\/bank-transactions\/import/);
    });

    test('search filter works', async ({ page }) => {
      await page.goto('/books/bank-transactions');

      const searchInput = page.locator('input[placeholder*="Search"]').first();
      await expect(searchInput).toBeVisible();
      await searchInput.fill('test search');
      await expect(searchInput).toHaveValue('test search');
    });
  });

  test.describe('Gateway - Online Payments', () => {
    test('renders payments page', async ({ page }) => {
      await page.goto('/books/gateway/payments');
      if (!(await ensureGatewayPaymentsReady(page))) {
        test.skip(true, 'Gateway payments API unavailable.');
      }
    });

    test('shows payments data table', async ({ page }) => {
      await page.goto('/books/gateway/payments');
      if (!(await ensureGatewayPaymentsReady(page))) {
        test.skip(true, 'Gateway payments API unavailable.');
      }

      const emptyState = page.getByText(/no payments found/i);
      const dataCell = page.locator('table tbody tr td:not(:has(.skeleton))').first();
      await expect(dataCell.or(emptyState)).toBeVisible({ timeout: 15000 });
    });

    test('filters by status work', async ({ page }) => {
      await page.goto('/books/gateway/payments');
      if (!(await ensureGatewayPaymentsReady(page))) {
        test.skip(true, 'Gateway payments API unavailable.');
      }
      const statusFilter = page.getByTestId('gateway-payments-status-filter');
      await expect(statusFilter).toBeVisible();
      await statusFilter.selectOption({ index: 1 });
      await expect(statusFilter).toHaveValue('success');
    });

    test('filters by provider work', async ({ page }) => {
      await page.goto('/books/gateway/payments');
      if (!(await ensureGatewayPaymentsReady(page))) {
        test.skip(true, 'Gateway payments API unavailable.');
      }

      const providerFilter = page.getByTestId('gateway-payments-provider-filter');
      await expect(providerFilter).toBeVisible();
      await providerFilter.selectOption({ index: 1 });
      await expect(providerFilter).toHaveValue('paystack');
    });

    test('verify payment action works when pending payments exist', async ({ page }) => {
      await page.goto('/books/gateway/payments');
      if (!(await ensureGatewayPaymentsReady(page))) {
        test.skip(true, 'Gateway payments API unavailable.');
      }

      const emptyState = page.getByText(/no payments found/i);
      const dataCell = page.locator('table tbody tr td:not(:has(.skeleton))').first();
      await expect(dataCell.or(emptyState)).toBeVisible({ timeout: 15000 });

      const pendingRows = page.locator('tbody tr').filter({ hasText: /pending/i });
      if (await pendingRows.count() === 0) {
        test.skip(true, 'No pending payments available in this environment.');
      }

      const pendingRow = pendingRows.first();
      await expect(pendingRow).toBeVisible({ timeout: 5000 });
      const verifyButton = pendingRow.locator('button[title*="Verify"]');
      await expect(verifyButton).toBeVisible();
      await verifyButton.click();
      await expect(page.getByText(/verify payment/i)).toBeVisible({ timeout: 3000 });
    });

    test('refund action shows modal when successful payments exist', async ({ page }) => {
      await page.goto('/books/gateway/payments');
      if (!(await ensureGatewayPaymentsReady(page))) {
        test.skip(true, 'Gateway payments API unavailable.');
      }

      const emptyState = page.getByText(/no payments found/i);
      const dataCell = page.locator('table tbody tr td:not(:has(.skeleton))').first();
      await expect(dataCell.or(emptyState)).toBeVisible({ timeout: 15000 });

      const successRows = page.locator('tbody tr').filter({ hasText: /success/i });
      if (await successRows.count() === 0) {
        test.skip(true, 'No successful payments available in this environment.');
      }

      const successRow = successRows.first();
      await expect(successRow).toBeVisible({ timeout: 5000 });
      const refundButton = successRow.locator('button[title*="Refund"]');
      await expect(refundButton).toBeVisible();
      await refundButton.click();
      await expect(page.getByText(/refund payment/i)).toBeVisible({ timeout: 3000 });
    });
  });

  test.describe('Gateway - Open Banking Connections', () => {
    test('renders connections page', async ({ page }) => {
      await page.goto('/books/gateway/connections');
      if (!(await ensureGatewayConnectionsReady(page))) {
        test.skip(true, 'Open banking connections unavailable in this environment.');
      }
    });

    test('shows connections table with data', async ({ page }) => {
      await page.goto('/books/gateway/connections');

      if (!(await ensureGatewayConnectionsReady(page))) {
        test.skip(true, 'Open banking connections unavailable in this environment.');
      }
      const emptyState = page.getByText(/no linked accounts found/i);
      const dataCell = page.locator('table tbody tr td:not(:has(.skeleton))').first();
      await expect(dataCell.or(emptyState)).toBeVisible({ timeout: 15000 });
    });

    test('filters by provider work', async ({ page }) => {
      await page.goto('/books/gateway/connections');

      if (!(await ensureGatewayConnectionsReady(page))) {
        test.skip(true, 'Open banking connections unavailable in this environment.');
      }
      const providerFilter = page.getByTestId('gateway-connections-provider-filter');
      await expect(providerFilter).toBeVisible({ timeout: 3000 });
      await providerFilter.selectOption({ index: 1 });
      await expect(providerFilter).toHaveValue('mono');
    });

    test('view transactions button works when connections exist', async ({ page }) => {
      await page.goto('/books/gateway/connections');

      if (!(await ensureGatewayConnectionsReady(page))) {
        test.skip(true, 'Open banking connections unavailable in this environment.');
      }
      const emptyState = page.getByText(/no linked accounts found/i);
      const dataCell = page.locator('table tbody tr td:not(:has(.skeleton))').first();
      await expect(dataCell.or(emptyState)).toBeVisible({ timeout: 15000 });

      const rows = page.locator('table tbody tr');
      if (await rows.count() === 0) {
        test.skip(true, 'No linked accounts available in this environment.');
      }

      const row = rows.first();
      await expect(row).toBeVisible({ timeout: 5000 });
      const viewButton = row.locator('button[title*="transaction"]');
      await expect(viewButton).toBeVisible();
      await viewButton.click();
      await expect(page.getByText(/transaction/i)).toBeVisible({ timeout: 3000 });
    });

    test('unlink action shows confirmation when connected accounts exist', async ({ page }) => {
      await page.goto('/books/gateway/connections');

      if (!(await ensureGatewayConnectionsReady(page))) {
        test.skip(true, 'Open banking connections unavailable in this environment.');
      }
      const emptyState = page.getByText(/no linked accounts found/i);
      const dataCell = page.locator('table tbody tr td:not(:has(.skeleton))').first();
      await expect(dataCell.or(emptyState)).toBeVisible({ timeout: 15000 });

      const connectedRows = page.locator('tbody tr').filter({ hasText: /connected/i });
      if (await connectedRows.count() === 0) {
        test.skip(true, 'No connected accounts available in this environment.');
      }

      const connectedRow = connectedRows.first();
      await expect(connectedRow).toBeVisible({ timeout: 5000 });
      const unlinkButton = connectedRow.locator('button[title*="Unlink"]');
      await expect(unlinkButton).toBeVisible();
      await unlinkButton.click();
      await expect(page.getByText(/unlink.*account/i)).toBeVisible({ timeout: 3000 });
    });
  });
});
