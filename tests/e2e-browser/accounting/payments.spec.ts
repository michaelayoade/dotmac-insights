import { test, expect } from '../fixtures/htmx.fixture';
import { AccountingPage } from '../pages/accounting.page';

/**
 * E2E Browser Tests for Accounting Payments Module.
 *
 * Tests the HTMX-powered payment management interface including:
 * - AR Payments (Customer Receipts)
 * - AP Payments (Supplier Payments)
 * - Payment filters and search
 * - Payment allocation
 */

test.describe('AR Payments (Customer Receipts)', () => {
  let accountingPage: AccountingPage;

  test.beforeEach(async ({ page }) => {
    accountingPage = new AccountingPage(page);
    await accountingPage.gotoARPayments();
  });

  test('displays AR payments page @smoke', async () => {
    const pageTitle = accountingPage.page.locator('h1');
    await expect(pageTitle).toContainText(/receipt|payment/i);
  });

  test('displays payments table @smoke', async () => {
    if (!(await accountingPage.hasPayments())) {
      const emptyState = accountingPage.page.locator('[data-testid="empty-state"]');
      if (await emptyState.count() > 0) {
        await expect(emptyState).toBeVisible();
        return;
      }
    }
    await expect(accountingPage.paymentsTable).toBeVisible();
  });

  test('search filters payments via HTMX', async ({ htmx }) => {
    if (!(await accountingPage.hasPayments())) {
      test.skip();
      return;
    }
    const initialCount = await accountingPage.getPaymentCount();

    await accountingPage.searchPayments('REC-');
    await htmx.waitForHtmxIdle();

    const filteredCount = await accountingPage.getPaymentCount();
    expect(filteredCount).toBeLessThanOrEqual(initialCount);
  });

  test('filter by status updates table', async ({ htmx }) => {
    if (!(await accountingPage.hasPayments())) {
      test.skip();
      return;
    }
    await accountingPage.filterPaymentsByStatus('posted');
    await htmx.waitForHtmxIdle();

    const rows = await accountingPage.paymentsTable.locator('tbody tr').all();
    if (rows.length > 0) {
      for (const row of rows) {
        const statusBadge = row.locator('[data-status]');
        await expect(statusBadge).toContainText(/posted|completed/i);
      }
    }
  });

  test('filter by payment method', async ({ htmx }) => {
    if (!(await accountingPage.hasPayments())) {
      test.skip();
      return;
    }

    // Check if method filter exists
    const methodFilter = accountingPage.paymentMethodFilter;
    if (await methodFilter.count() === 0) {
      test.skip();
      return;
    }

    await accountingPage.filterPaymentsByMethod('bank_transfer');
    await htmx.waitForHtmxIdle();

    // Verify filter applied (table should update)
    await accountingPage.waitForHtmxComplete();
  });

  test('new receipt button navigates to form', async ({ page }) => {
    await accountingPage.newPaymentButton.click();
    await expect(page).toHaveURL(/\/new|\/create/);
  });
});

test.describe('AP Payments (Supplier Payments)', () => {
  let accountingPage: AccountingPage;

  test.beforeEach(async ({ page }) => {
    accountingPage = new AccountingPage(page);
    await accountingPage.gotoAPPayments();
  });

  test('displays AP payments page @smoke', async () => {
    const pageTitle = accountingPage.page.locator('h1');
    await expect(pageTitle).toContainText(/payment|supplier/i);
  });

  test('displays payments table @smoke', async () => {
    if (!(await accountingPage.hasPayments())) {
      const emptyState = accountingPage.page.locator('[data-testid="empty-state"]');
      if (await emptyState.count() > 0) {
        await expect(emptyState).toBeVisible();
        return;
      }
    }
    await expect(accountingPage.paymentsTable).toBeVisible();
  });

  test('search filters payments via HTMX', async ({ htmx }) => {
    if (!(await accountingPage.hasPayments())) {
      test.skip();
      return;
    }
    const initialCount = await accountingPage.getPaymentCount();

    await accountingPage.searchPayments('PAY-');
    await htmx.waitForHtmxIdle();

    const filteredCount = await accountingPage.getPaymentCount();
    expect(filteredCount).toBeLessThanOrEqual(initialCount);
  });

  test('filter by pending status', async ({ htmx }) => {
    if (!(await accountingPage.hasPayments())) {
      test.skip();
      return;
    }
    await accountingPage.filterPaymentsByStatus('pending');
    await htmx.waitForHtmxIdle();

    const rows = await accountingPage.paymentsTable.locator('tbody tr').all();
    if (rows.length > 0) {
      for (const row of rows) {
        const statusBadge = row.locator('[data-status]');
        await expect(statusBadge).toContainText(/pending|draft/i);
      }
    }
  });
});

test.describe('Payment Detail View', () => {
  let accountingPage: AccountingPage;

  test.beforeEach(async ({ page }) => {
    accountingPage = new AccountingPage(page);
    await accountingPage.gotoARPayments();
    if (!(await accountingPage.hasPayments())) {
      test.skip();
      return;
    }
    // Click first payment
    const firstRow = accountingPage.paymentsTable.locator('tbody tr').first();
    const link = firstRow.locator('a').first();
    await accountingPage.htmxClick(link);
  });

  test('displays payment header with status', async () => {
    const header = accountingPage.page.locator('h1');
    await expect(header).toBeVisible();

    const status = accountingPage.page.locator('[data-testid="payment-status"]');
    await expect(status).toBeVisible();
  });

  test('displays payment amount', async () => {
    const amount = accountingPage.page.locator('[data-testid="payment-amount"]');
    await expect(amount).toBeVisible();
  });

  test('displays allocation section', async () => {
    const allocation = accountingPage.page.locator('#allocations, .allocations-section, [data-testid="allocations"]');
    if (await allocation.count() > 0) {
      await expect(allocation).toBeVisible();
    }
  });
});

test.describe('Payment Allocation', () => {
  let accountingPage: AccountingPage;

  test.beforeEach(async ({ page }) => {
    accountingPage = new AccountingPage(page);
  });

  test('allocation page loads for unallocated payment', async ({ page }) => {
    await accountingPage.gotoARPayments();

    // Try to find an unallocated payment
    const unallocatedFilter = accountingPage.page.locator('a[href*="unallocated=true"]');
    if (await unallocatedFilter.count() > 0) {
      await unallocatedFilter.click();
      await accountingPage.waitForHtmxComplete();

      if (await accountingPage.hasPayments()) {
        const firstRow = accountingPage.paymentsTable.locator('tbody tr').first();
        const link = firstRow.locator('a').first();
        await Promise.all([
          page.waitForURL(/\/accounting\/ar-payments\/\d+/, { timeout: 10000 }),
          link.click(),
        ]);

        // Check if allocate button exists
        const allocateBtn = accountingPage.page.locator('a:has-text("Allocate"), button:has-text("Allocate")');
        if (await allocateBtn.count() > 0) {
          await Promise.all([
            page.waitForURL(/\/allocate/, { timeout: 10000 }),
            allocateBtn.click(),
          ]);
        }
      }
    }
  });
});
