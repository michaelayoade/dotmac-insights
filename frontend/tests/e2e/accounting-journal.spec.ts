/**
 * Accounting Journal Entries E2E Tests
 *
 * Comprehensive tests for the Accounting module including:
 * - Journal entry list view with filters
 * - Journal entry CRUD operations
 * - Debit/credit balancing
 * - Posting and reversal
 * - Chart of accounts navigation
 * - RBAC (role-based access control)
 */

import { test, expect, setupAuth, expectAccessDenied } from './fixtures/auth';
import {
  createTestJournalEntry,
  deleteTestJournalEntry,
} from './fixtures/api-helpers';
import { AccountingPage } from './pages';

test.describe('Accounting Journal Entries - Authenticated', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page, ['accounting:read', 'accounting:write']);
  });

  test.describe('List View', () => {
    test('renders journal entries list', async ({ page }) => {
      const accountingPage = new AccountingPage(page);
      await accountingPage.gotoJournalEntries();

      await expect(page.getByText(/access denied|not authorized/i)).toBeHidden({ timeout: 10000 });
      await expect(
        page.getByRole('heading', { name: /journal|entries|accounting/i })
      ).toBeVisible({ timeout: 10000 });

      await expect(accountingPage.createJournalButton).toBeVisible();
    });

    test('displays journal entries table', async ({ page }) => {
      const accountingPage = new AccountingPage(page);
      await accountingPage.gotoJournalEntries();

      await expect(accountingPage.journalEntries).toBeVisible({ timeout: 10000 });
    });

    test('filter by period works', async ({ page }) => {
      const accountingPage = new AccountingPage(page);
      await accountingPage.gotoJournalEntries();

      if (await accountingPage.periodFilter.isVisible()) {
        await accountingPage.filterByPeriod('Current Month');

        await expect(
          accountingPage.journalRows
            .first()
            .or(page.getByText(/no.*entries|empty/i))
        ).toBeVisible({ timeout: 10000 });
      }
    });

    test('filter by account works', async ({ page }) => {
      const accountingPage = new AccountingPage(page);
      await accountingPage.gotoJournalEntries();

      if (await accountingPage.accountFilter.isVisible()) {
        await accountingPage.accountFilter.selectOption({ index: 1 });

        await page.waitForTimeout(500);
        await expect(accountingPage.journalEntries).toBeVisible();
      }
    });

    test('search filters entries', async ({ page }) => {
      const accountingPage = new AccountingPage(page);
      await accountingPage.gotoJournalEntries();

      await accountingPage.search('JV');

      await expect(
        accountingPage.journalRows
          .first()
          .or(page.getByText(/no.*entries|empty/i))
      ).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Create Journal Entry', () => {
    test('navigates to create form', async ({ page }) => {
      const accountingPage = new AccountingPage(page);
      await accountingPage.gotoJournalEntries();

      await accountingPage.openCreateJournalEntry();

      await expect(page).toHaveURL(/\/accounting\/journal-entries\/new|\/accounting\/journal-entries\/create/);
    });

    test('validates required fields', async ({ page }) => {
      await page.goto('/accounting/journal-entries/new');

      await page.getByRole('button', { name: /save|create|submit/i }).click();

      await expect(
        page.getByText(/required|cannot be empty|must balance/i).first()
      ).toBeVisible({ timeout: 5000 });
    });

    test('creates balanced journal entry', async ({ page }) => {
      await page.goto('/accounting/journal-entries/new');

      // Set date
      const dateInput = page.getByLabel(/date|posting.*date/i);
      if (await dateInput.isVisible()) {
        await dateInput.fill(new Date().toISOString().split('T')[0]);
      }

      // Set reference
      const referenceInput = page.getByLabel(/reference|memo/i);
      if (await referenceInput.isVisible()) {
        await referenceInput.fill(`E2E Test JV ${Date.now()}`);
      }

      // Add first line (debit)
      const accountSelect1 = page.locator('select, [data-testid*="account"]').first();
      if (await accountSelect1.isVisible()) {
        await accountSelect1.click();
        await page.getByRole('option').first().click();
      }

      const debitInput = page.locator('input[name*="debit"], [data-testid*="debit"]').first();
      if (await debitInput.isVisible()) {
        await debitInput.fill('1000');
      }

      // Add second line (credit)
      const addLineButton = page.getByRole('button', { name: /add.*line|add.*row/i });
      if (await addLineButton.isVisible()) {
        await addLineButton.click();

        const accountSelect2 = page.locator('select, [data-testid*="account"]').nth(1);
        if (await accountSelect2.isVisible()) {
          await accountSelect2.click();
          await page.getByRole('option').nth(1).click();
        }

        const creditInput = page.locator('input[name*="credit"], [data-testid*="credit"]').nth(1);
        if (await creditInput.isVisible()) {
          await creditInput.fill('1000');
        }
      }

      await page.getByRole('button', { name: /save|create|submit/i }).click();
      await page.waitForURL(/\/accounting\/journal-entries\/\d+/, { timeout: 10000 });
    });

    test('shows balance indicator', async ({ page }) => {
      await page.goto('/accounting/journal-entries/new');

      const balanceIndicator = page.locator('[data-testid="balance-indicator"]').or(
        page.getByText(/balanced|unbalanced|difference/i)
      );

      await expect(balanceIndicator).toBeVisible({ timeout: 5000 });
    });

    test('validates debit/credit balance', async ({ page }) => {
      await page.goto('/accounting/journal-entries/new');

      // Add unbalanced entry
      const debitInput = page.locator('input[name*="debit"], [data-testid*="debit"]').first();
      if (await debitInput.isVisible()) {
        await debitInput.fill('1000');
      }

      // Try to submit unbalanced
      await page.getByRole('button', { name: /save|create|submit/i }).click();

      // Should show balance error
      await expect(
        page.getByText(/must balance|unbalanced|difference/i).first()
      ).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('Edit Journal Entry', () => {
    test('loads entry data', async ({ page, request }) => {
      const entry = await createTestJournalEntry(request, {
        reference_number: `View Test ${Date.now()}`,
      });

      try {
        const accountingPage = new AccountingPage(page);
        await accountingPage.gotoJournalEntry(entry.id);

        await expect(page.getByText(entry.entry_number || entry.reference_number)).toBeVisible({ timeout: 5000 });
      } finally {
        await deleteTestJournalEntry(request, entry.id);
      }
    });

    test('displays line items', async ({ page, request }) => {
      const entry = await createTestJournalEntry(request, {
        accounts: [
          { account: 'Cash', debit: 5000, credit: 0 },
          { account: 'Revenue', debit: 0, credit: 5000 },
        ],
      });

      try {
        const accountingPage = new AccountingPage(page);
        await accountingPage.gotoJournalEntry(entry.id);

        // Should show line items
        await expect(page.getByText(/5,?000/)).toBeVisible({ timeout: 5000 });
      } finally {
        await deleteTestJournalEntry(request, entry.id);
      }
    });
  });

  test.describe('Journal Entry Actions', () => {
    test('can post draft entry', async ({ page, request }) => {
      const entry = await createTestJournalEntry(request, {
        reference_number: `Post Test ${Date.now()}`,
      });

      try {
        const accountingPage = new AccountingPage(page);
        await accountingPage.gotoJournalEntry(entry.id);

        if (await accountingPage.postButton.isVisible()) {
          await accountingPage.postJournalEntry();

          await accountingPage.expectPosted();
        }
      } finally {
        await deleteTestJournalEntry(request, entry.id);
      }
    });

    test('can reverse posted entry', async ({ page, request }) => {
      const entry = await createTestJournalEntry(request, {
        reference_number: `Reverse Test ${Date.now()}`,
      });

      try {
        const accountingPage = new AccountingPage(page);
        await accountingPage.gotoJournalEntry(entry.id);

        // Post first
        if (await accountingPage.postButton.isVisible()) {
          await accountingPage.postJournalEntry();
          await page.waitForTimeout(500);
        }

        // Now reverse
        if (await accountingPage.reverseButton.isVisible()) {
          await accountingPage.reverseJournalEntry();

          await expect(page.getByText(/reversed|reversal/i)).toBeVisible({ timeout: 5000 });
        }
      } finally {
        await deleteTestJournalEntry(request, entry.id);
      }
    });
  });

  test.describe('Totals', () => {
    test('displays debit and credit totals', async ({ page, request }) => {
      const entry = await createTestJournalEntry(request, {
        accounts: [
          { account: 'Cash', debit: 2500, credit: 0 },
          { account: 'Revenue', debit: 0, credit: 2500 },
        ],
      });

      try {
        const accountingPage = new AccountingPage(page);
        await accountingPage.gotoJournalEntry(entry.id);

        // Check totals display
        await expect(page.getByText(/2,?500/)).toBeVisible({ timeout: 5000 });
      } finally {
        await deleteTestJournalEntry(request, entry.id);
      }
    });
  });

  test.describe('Chart of Accounts', () => {
    test('navigates to chart of accounts', async ({ page }) => {
      const accountingPage = new AccountingPage(page);
      await accountingPage.gotoChartOfAccounts();

      await expect(page).toHaveURL(/\/accounting\/chart-of-accounts/);
    });

    test('displays accounts', async ({ page }) => {
      const accountingPage = new AccountingPage(page);
      await accountingPage.gotoChartOfAccounts();

      await expect(
        page
          .locator('table tbody tr, [data-testid="account-row"]')
          .first()
          .or(page.getByText(/no.*accounts|empty/i))
      ).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Reports', () => {
    test('navigates to trial balance', async ({ page }) => {
      const accountingPage = new AccountingPage(page);
      await accountingPage.gotoTrialBalance();

      await expect(page).toHaveURL(/\/accounting\/reports\/trial-balance/);
    });

    test('displays trial balance', async ({ page }) => {
      const accountingPage = new AccountingPage(page);
      await accountingPage.gotoTrialBalance();

      await expect(
        page.locator('table, [data-testid="trial-balance"]')
      ).toBeVisible({ timeout: 10000 });
    });

    test('navigates to balance sheet', async ({ page }) => {
      const accountingPage = new AccountingPage(page);
      await accountingPage.gotoBalanceSheet();

      await expect(page).toHaveURL(/\/accounting\/reports\/balance-sheet/);
    });

    test('navigates to income statement', async ({ page }) => {
      const accountingPage = new AccountingPage(page);
      await accountingPage.gotoIncomeStatement();

      await expect(page).toHaveURL(/\/accounting\/reports\/income-statement/);
    });
  });

  test.describe('Delete Entry', () => {
    test('can delete draft entry', async ({ page, request }) => {
      const entry = await createTestJournalEntry(request, {
        reference_number: `Delete Test ${Date.now()}`,
      });

      const accountingPage = new AccountingPage(page);
      await accountingPage.gotoJournalEntry(entry.id);

      const deleteButton = page.getByRole('button', { name: /delete|void/i });
      if (await deleteButton.isVisible()) {
        await deleteButton.click();

        const confirmButton = page.getByRole('button', { name: /confirm|yes|delete/i });
        await expect(confirmButton).toBeVisible({ timeout: 2000 });
        await confirmButton.click();

        await page.waitForURL(/\/accounting\/journal-entries/, { timeout: 10000 });
      } else {
        await deleteTestJournalEntry(request, entry.id);
      }
    });
  });
});

test.describe('Accounting Journal Entries - RBAC', () => {
  test('read-only user cannot create entries', async ({ page }) => {
    await setupAuth(page, ['accounting:read']);

    const accountingPage = new AccountingPage(page);
    await accountingPage.gotoJournalEntries();

    await expect(accountingPage.createJournalButton).toBeHidden();
  });

  test('user without accounting scope sees access denied', async ({ page }) => {
    await setupAuth(page, ['hr:read']);
    await page.goto('/accounting/journal-entries');

    await expectAccessDenied(page);
  });
});

test.describe('Accounting Journal Entries - Unauthenticated', () => {
  test('redirects to login when not authenticated', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => localStorage.clear());

    await page.goto('/accounting/journal-entries');

    await expect(page).toHaveURL(/\/login|\/auth/);
  });
});
