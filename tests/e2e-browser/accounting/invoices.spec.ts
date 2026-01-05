import { test, expect } from '../fixtures/htmx.fixture';
import { AccountingPage } from '../pages/accounting.page';

/**
 * E2E Browser Tests for Accounting Invoices Module.
 *
 * Tests the HTMX-powered invoice management interface including:
 * - Invoice list with search and filters
 * - Invoice creation
 * - Invoice detail view
 * - Stats cards navigation
 */

test.describe('Invoices List', () => {
  let accountingPage: AccountingPage;

  test.beforeEach(async ({ page }) => {
    accountingPage = new AccountingPage(page);
    await accountingPage.gotoInvoices();
  });

  test('displays invoices page with stats @smoke', async () => {
    await expect(accountingPage.page.locator('[data-testid="page-title"]')).toHaveText('Invoices');
    await accountingPage.expectStatsVisible();
  });

  test('displays invoices table @smoke', async () => {
    const hasData = await accountingPage.ensureHasInvoices();
    if (!hasData) {
      await accountingPage.expectEmptyState();
      return;
    }
    await expect(accountingPage.invoicesTable).toBeVisible();
  });

  test('search filters invoices via HTMX @critical', async ({ htmx }) => {
    if (!(await accountingPage.ensureHasInvoices())) {
      test.skip();
      return;
    }
    const initialCount = await accountingPage.getInvoiceCount();

    await accountingPage.searchInvoices('INV-');
    await htmx.waitForHtmxIdle();

    const filteredCount = await accountingPage.getInvoiceCount();
    expect(filteredCount).toBeLessThanOrEqual(initialCount);
  });

  test('filter by status updates table', async ({ htmx }) => {
    if (!(await accountingPage.ensureHasInvoices())) {
      test.skip();
      return;
    }
    await accountingPage.filterInvoicesByStatus('unpaid');
    await htmx.waitForHtmxIdle();

    // All visible rows should have unpaid status
    const rows = await accountingPage.invoicesTable.locator('tbody tr').all();
    if (rows.length === 0) {
      // No unpaid invoices - that's ok
      return;
    }
    for (const row of rows) {
      const statusBadge = row.locator('.badge, [data-status]');
      await expect(statusBadge).toContainText(/unpaid|draft|pending/i);
    }
  });

  test('filter by overdue status', async ({ htmx }) => {
    if (!(await accountingPage.ensureHasInvoices())) {
      test.skip();
      return;
    }
    await accountingPage.filterInvoicesByStatus('overdue');
    await htmx.waitForHtmxIdle();

    const rows = await accountingPage.invoicesTable.locator('tbody tr').all();
    if (rows.length > 0) {
      for (const row of rows) {
        const statusBadge = row.locator('.badge, [data-status]');
        await expect(statusBadge).toContainText(/overdue/i);
      }
    }
  });

  test('stat card outstanding navigates to filtered list', async ({ page }) => {
    await accountingPage.clickStatCard('outstanding');
    await expect(page).toHaveURL(/status=unpaid/);
  });

  test('stat card overdue navigates to filtered list', async ({ page }) => {
    await accountingPage.clickStatCard('overdue');
    await expect(page).toHaveURL(/status=overdue/);
  });

  test('stat card paid navigates to filtered list', async ({ page }) => {
    await accountingPage.clickStatCard('paid');
    await expect(page).toHaveURL(/status=paid/);
  });

  test('click invoice navigates to detail', async ({ page }) => {
    if (!(await accountingPage.ensureHasInvoices())) {
      test.skip();
      return;
    }
    const firstRow = await accountingPage.getInvoiceRowData(0);

    await accountingPage.clickInvoice(firstRow.number.trim());

    await expect(page).toHaveURL(/\/invoices\/\d+/);
  });

  test('new invoice button navigates to form', async ({ page }) => {
    await accountingPage.newInvoiceButton.click();
    await expect(page).toHaveURL(/\/invoices\/new/);
  });
});

test.describe('Invoice Creation', () => {
  let accountingPage: AccountingPage;

  test.beforeEach(async ({ page }) => {
    accountingPage = new AccountingPage(page);
  });

  test('invoice form is accessible', async () => {
    await accountingPage.gotoInvoiceCreate();
    await expect(accountingPage.invoiceForm).toBeVisible();
    await expect(accountingPage.customerSelect).toBeVisible();
    const currencyLabels = accountingPage.page.locator('[data-testid="invoice-form-currency"]');
    await expect(currencyLabels).toHaveCount(2);
    const currencyText = (await currencyLabels.first().textContent())?.trim() || '';
    expect(currencyText.length).toBeGreaterThan(0);
  });

  test('validation errors shown on empty submit', async ({ htmx }) => {
    await accountingPage.gotoInvoiceCreate();

    await accountingPage.htmxSubmitForm(accountingPage.invoiceForm);

    // Expect validation error message
    const errorMessage = accountingPage.page.locator('.field-error, [data-error], .text-red-600');
    await expect(errorMessage.first()).toBeVisible();
  });
});

test.describe('Invoice Detail View', () => {
  let accountingPage: AccountingPage;

  test.beforeEach(async ({ page }) => {
    accountingPage = new AccountingPage(page);
    await accountingPage.gotoInvoices();
    if (!(await accountingPage.ensureHasInvoices())) {
      test.skip();
      return;
    }
    const firstRow = await accountingPage.getInvoiceRowData(0);
    await accountingPage.clickInvoice(firstRow.number.trim());
  });

  test('displays invoice header with status', async () => {
    await expect(accountingPage.invoiceHeader).toBeVisible();
    await expect(accountingPage.invoiceStatus).toBeVisible();
  });

  test('displays invoice amount and balance', async () => {
    const totalAmount = accountingPage.page.locator('[data-testid="total-amount"]');
    const balance = accountingPage.page.locator('[data-testid="balance"]');
    await expect(totalAmount).toBeVisible();
    await expect(balance).toBeVisible();
  });

  test('receive payment button visible for unpaid invoice', async () => {
    const status = await accountingPage.invoiceStatus.textContent();
    if (status?.toLowerCase().includes('paid')) {
      test.skip();
      return;
    }
    await expect(accountingPage.receivePaymentButton).toBeVisible();
  });
});

test.describe('Invoice Empty States', () => {
  let accountingPage: AccountingPage;

  test.beforeEach(async ({ page }) => {
    accountingPage = new AccountingPage(page);
    await accountingPage.gotoInvoices();
  });

  test('shows empty state when no search results', async ({ htmx }) => {
    await accountingPage.searchInvoices('xyznonexistent98765');
    await htmx.waitForHtmxIdle();

    const emptyState = accountingPage.page.locator('.empty-state, [data-testid="empty-state"], .no-results');
    const noRows = await accountingPage.invoicesTable.locator('tbody tr').count() === 0;

    expect(await emptyState.count() > 0 || noRows).toBeTruthy();
  });
});
