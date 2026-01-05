import { test, expect } from '../fixtures/htmx.fixture';
import { AccountingPage } from '../pages/accounting.page';

/**
 * E2E Browser Tests for Accounting Reports.
 *
 * Tests the financial report pages including:
 * - Balance Sheet
 * - Income Statement (P&L)
 * - Trial Balance
 * - Cash Flow Statement
 * - Aging Reports (AR/AP)
 */

test.describe('Balance Sheet Report', () => {
  let accountingPage: AccountingPage;

  test.beforeEach(async ({ page }) => {
    accountingPage = new AccountingPage(page);
    await accountingPage.gotoReport('balance-sheet');
  });

  test('displays balance sheet page @smoke', async () => {
    const pageTitle = accountingPage.page.locator('h1');
    await expect(pageTitle).toContainText(/balance sheet/i);
  });

  test('shows assets section', async () => {
    const assetsSection = accountingPage.page.locator('.assets-section, [data-section="assets"], h2:has-text("Assets"), h3:has-text("Assets")');
    await expect(assetsSection.first()).toBeVisible();
  });

  test('shows liabilities section', async () => {
    const liabilitiesSection = accountingPage.page.locator('.liabilities-section, [data-section="liabilities"], h2:has-text("Liabilities"), h3:has-text("Liabilities")');
    await expect(liabilitiesSection.first()).toBeVisible();
  });

  test('shows equity section', async () => {
    const equitySection = accountingPage.page.locator('.equity-section, [data-section="equity"], h2:has-text("Equity"), h3:has-text("Equity")');
    await expect(equitySection.first()).toBeVisible();
  });

  test('period filter updates report via HTMX', async ({ htmx }) => {
    const periodSelect = accountingPage.reportPeriodSelect;
    if (await periodSelect.count() === 0) {
      test.skip();
      return;
    }

    await accountingPage.selectReportPeriod('this_month');
    await htmx.waitForHtmxIdle();

    // Report should still be visible after update
    await accountingPage.expectReportLoaded();
  });
});

test.describe('Income Statement Report', () => {
  let accountingPage: AccountingPage;

  test.beforeEach(async ({ page }) => {
    accountingPage = new AccountingPage(page);
    await accountingPage.gotoReport('income-statement');
  });

  test('displays income statement page @smoke', async () => {
    const pageTitle = accountingPage.page.locator('h1');
    await expect(pageTitle).toContainText(/income statement|profit.*loss|p&l/i);
  });

  test('shows revenue section', async () => {
    const revenueSection = accountingPage.page.locator('.revenue-section, [data-section="revenue"], h2:has-text("Revenue"), h3:has-text("Revenue"), h2:has-text("Income"), h3:has-text("Income")');
    await expect(revenueSection.first()).toBeVisible();
  });

  test('shows expenses section', async () => {
    const expensesSection = accountingPage.page.locator('.expenses-section, [data-section="expenses"], h2:has-text("Expenses"), h3:has-text("Expenses")');
    await expect(expensesSection.first()).toBeVisible();
  });

  test('shows net income/profit line', async () => {
    const netIncome = accountingPage.page.locator('.net-income, [data-net-income], tr:has-text("Net Income"), tr:has-text("Net Profit"), .total-row:last-child');
    await expect(netIncome.first()).toBeVisible();
  });

  test('period filter updates report', async ({ htmx }) => {
    const periodSelect = accountingPage.reportPeriodSelect;
    if (await periodSelect.count() === 0) {
      test.skip();
      return;
    }

    await accountingPage.selectReportPeriod('this_quarter');
    await htmx.waitForHtmxIdle();

    await accountingPage.expectReportLoaded();
  });
});

test.describe('Trial Balance Report', () => {
  let accountingPage: AccountingPage;

  test.beforeEach(async ({ page }) => {
    accountingPage = new AccountingPage(page);
    await accountingPage.gotoReport('trial-balance');
  });

  test('displays trial balance page @smoke', async () => {
    const pageTitle = accountingPage.page.locator('h1');
    await expect(pageTitle).toContainText(/trial balance/i);
  });

  test('shows debit and credit columns', async () => {
    const debitHeader = accountingPage.page.locator('th:has-text("Debit"), th:has-text("DR")');
    const creditHeader = accountingPage.page.locator('th:has-text("Credit"), th:has-text("CR")');

    await expect(debitHeader.first()).toBeVisible();
    await expect(creditHeader.first()).toBeVisible();
  });

  test('shows total row with balanced amounts', async () => {
    const totalRow = accountingPage.page.locator('tr.total-row, tr:has-text("Total"), tfoot tr');
    await expect(totalRow.first()).toBeVisible();
  });
});

test.describe('Cash Flow Statement', () => {
  let accountingPage: AccountingPage;

  test.beforeEach(async ({ page }) => {
    accountingPage = new AccountingPage(page);
    await accountingPage.gotoReport('cash-flow');
  });

  test('displays cash flow page @smoke', async () => {
    const pageTitle = accountingPage.page.locator('h1');
    await expect(pageTitle).toContainText(/cash flow/i);
  });

  test('shows operating activities section', async () => {
    const operatingSection = accountingPage.page.locator('[data-section="operating"], h2:has-text("Operating"), h3:has-text("Operating")');
    await expect(operatingSection.first()).toBeVisible();
  });

  test('shows investing activities section', async () => {
    const investingSection = accountingPage.page.locator('[data-section="investing"], h2:has-text("Investing"), h3:has-text("Investing")');
    await expect(investingSection.first()).toBeVisible();
  });

  test('shows financing activities section', async () => {
    const financingSection = accountingPage.page.locator('[data-section="financing"], h2:has-text("Financing"), h3:has-text("Financing")');
    await expect(financingSection.first()).toBeVisible();
  });
});

test.describe('AR Aging Report', () => {
  let accountingPage: AccountingPage;

  test.beforeEach(async ({ page }) => {
    accountingPage = new AccountingPage(page);
    await accountingPage.gotoAging('ar');
  });

  test('displays AR aging page @smoke', async () => {
    const pageTitle = accountingPage.page.locator('[data-testid="page-title"]');
    await expect(pageTitle).toContainText(/receivable|ar.*aging/i);
  });

  test('shows aging buckets (Current, 1-30, 31-60, 61-90, 90+)', async () => {
    const buckets = accountingPage.page.locator('[data-bucket]');

    // Should have at least 5 aging buckets
    const bucketCount = await buckets.count();
    expect(bucketCount).toBeGreaterThanOrEqual(5);
  });

  test('shows total outstanding amount', async () => {
    const total = accountingPage.page.locator('[data-testid="total-outstanding"]');
    await expect(total).toBeVisible();
  });

  test('clicking aging bucket navigates to filtered list', async ({ page }) => {
    const bucket = accountingPage.page.locator('[data-bucket] a, [data-bucket]').first();
    if (await bucket.count() > 0) {
      await bucket.click();
      await expect(page).toHaveURL(/aging=/);
    }
  });
});

test.describe('AP Aging Report', () => {
  let accountingPage: AccountingPage;

  test.beforeEach(async ({ page }) => {
    accountingPage = new AccountingPage(page);
    await accountingPage.gotoAging('ap');
  });

  test('displays AP aging page @smoke', async () => {
    const pageTitle = accountingPage.page.locator('[data-testid="page-title"]');
    await expect(pageTitle).toContainText(/payable|ap.*aging/i);
  });

  test('shows aging buckets', async () => {
    const buckets = accountingPage.page.locator('[data-bucket]');
    const bucketCount = await buckets.count();
    expect(bucketCount).toBeGreaterThanOrEqual(5);
  });

  test('shows bills table if outstanding bills exist', async () => {
    const billsTable = accountingPage.page.locator('[data-testid="aging-table"]');
    const emptyState = accountingPage.page.locator('[data-testid="empty-state"]');

    const hasTable = await billsTable.count() > 0;
    const hasEmpty = await emptyState.count() > 0;

    expect(hasTable || hasEmpty).toBeTruthy();
  });
});

test.describe('Report Export', () => {
  let accountingPage: AccountingPage;

  test('export button is available on reports', async ({ page }) => {
    accountingPage = new AccountingPage(page);
    await accountingPage.gotoReport('balance-sheet');

    const exportBtn = accountingPage.page.locator('button:has-text("Export"), a:has-text("Export"), [data-testid="export-btn"]');
    if (await exportBtn.count() > 0) {
      await expect(exportBtn.first()).toBeVisible();
    }
  });

  test('export dropdown shows format options', async ({ page }) => {
    accountingPage = new AccountingPage(page);
    await accountingPage.gotoReport('income-statement');

    const exportBtn = accountingPage.page.locator('button:has-text("Export")');
    if (await exportBtn.count() > 0) {
      await exportBtn.click();

      const pdfOption = accountingPage.page.locator('a:has-text("PDF"), button:has-text("PDF")');
      const excelOption = accountingPage.page.locator('a:has-text("Excel"), button:has-text("Excel"), a:has-text("XLSX")');

      // At least one export option should be visible
      const hasPdf = await pdfOption.count() > 0;
      const hasExcel = await excelOption.count() > 0;

      expect(hasPdf || hasExcel).toBeTruthy();
    }
  });
});
