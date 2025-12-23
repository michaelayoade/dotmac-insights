/**
 * Expenses & Approvals E2E Tests
 *
 * Comprehensive tests for the Expenses module including:
 * - Transaction list with actions (exclude, mark personal)
 * - Approvals bulk actions with success/error toasts
 * - Statements import and error handling
 * - Cash advances flow
 */

import { test, expect, setupAuth } from './fixtures/auth';

async function ensureRowsOrSkip(
  page: import('@playwright/test').Page,
  rows: import('@playwright/test').Locator,
  emptyStatePattern: RegExp,
  skipReason: string
): Promise<void> {
  const emptyState = page.getByText(emptyStatePattern);
  await expect(rows.first().or(emptyState)).toBeVisible({ timeout: 10000 });
  if (await rows.count() === 0) {
    test.skip(true, skipReason);
  }
}

test.describe('Expenses - Authenticated', () => {
  test.describe.configure({ mode: 'serial' });
  test.beforeEach(async ({ page }) => {
    await setupAuth(page, ['hr:read', 'hr:write', 'customers:read']);
  });

  test.describe('Expenses Overview', () => {
    test('renders expenses dashboard', async ({ page }) => {
      await page.goto('/expenses');

      // Verify page structure
      await expect(page.getByRole('heading', { name: /expense/i })).toBeVisible();

      // Verify key sections exist
      await expect(page.locator('[class*="card"], [class*="stat"]').first()).toBeVisible();
    });

    test('displays summary statistics', async ({ page }) => {
      await page.goto('/expenses');

      // Should show expense stats cards
      await expect(page.getByText(/total|pending|approved/i).first()).toBeVisible();
    });
  });

  test.describe('Transactions List', () => {
    test('renders transactions with filters', async ({ page }) => {
      await page.goto('/expenses/transactions');

      await expect(page.getByRole('heading', { name: /transaction/i })).toBeVisible();

      // Verify filter controls
      await expect(page.locator('select').first()).toBeVisible();
    });

    test('transaction actions menu works', async ({ page }) => {
      await page.goto('/expenses/transactions');

      // Wait for transactions to load
      const row = page.locator('table tbody tr, [class*="transaction"]').first();
      await ensureRowsOrSkip(
        page,
        page.locator('table tbody tr, [class*="transaction"]'),
        /no transactions|no data|empty/i,
        'No expense transactions available in this environment.'
      );
      const moreButton = row.locator('button').filter({ hasText: /./ }).last();
      await moreButton.click();

      await expect(page.getByText(/exclude|personal|dispute/i).first()).toBeVisible({
        timeout: 3000,
      });
    });

    test('exclude action shows toast feedback', async ({ page }) => {
      await page.goto('/expenses/transactions');

      const row = page.locator('table tbody tr').first();
      await ensureRowsOrSkip(
        page,
        page.locator('table tbody tr'),
        /no transactions|no data|empty/i,
        'No expense transactions available in this environment.'
      );
      const moreButton = row.locator('button').last();
      await moreButton.click();

      const excludeOption = page.getByRole('button', { name: /exclude/i });
      await expect(excludeOption).toBeVisible({ timeout: 2000 });
      await excludeOption.click();

      await expect(page.getByText(/excluded|success/i).first()).toBeVisible({ timeout: 5000 });
    });

    test('mark personal action updates status', async ({ page }) => {
      await page.goto('/expenses/transactions');

      const row = page.locator('table tbody tr').first();
      await ensureRowsOrSkip(
        page,
        page.locator('table tbody tr'),
        /no transactions|no data|empty/i,
        'No expense transactions available in this environment.'
      );
      const moreButton = row.locator('button').last();
      await moreButton.click();

      const personalOption = page.getByRole('button', { name: /personal/i });
      await expect(personalOption).toBeVisible({ timeout: 2000 });
      await personalOption.click();

      await expect(page.getByText(/personal|success/i).first()).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('Approvals', () => {
    test('renders pending approvals list', async ({ page }) => {
      await page.goto('/expenses/approvals');

      await expect(page.getByRole('heading', { name: /approval|pending/i })).toBeVisible();

      // Verify summary cards
      await expect(page.getByText(/total|pending|amount/i).first()).toBeVisible();
    });

    test('bulk select all works', async ({ page }) => {
      await page.goto('/expenses/approvals');

      // Find select all checkbox
      const selectAll = page.locator('input[type="checkbox"]').first();
      await expect(
        selectAll.or(page.getByText(/no approvals|no pending|no data|empty/i))
      ).toBeVisible({ timeout: 10000 });
      if (await selectAll.isHidden()) {
        test.skip(true, 'No approvals available in this environment.');
      }
      await selectAll.check();

      await expect(page.getByText(/selected/i)).toBeVisible({ timeout: 3000 });
    });

    test('bulk approve shows success toast', async ({ page }) => {
      await page.goto('/expenses/approvals');

      // Select first item
      const checkbox = page.locator('input[type="checkbox"]').nth(1); // Skip select-all
      await expect(
        checkbox.or(page.getByText(/no approvals|no pending|no data|empty/i))
      ).toBeVisible({ timeout: 10000 });
      if (await checkbox.isHidden()) {
        test.skip(true, 'No approvals available in this environment.');
      }
      await checkbox.check();

      const approveButton = page.getByRole('button', { name: /approve/i });
      await approveButton.click();

      await expect(page.getByText(/approved|success/i).first()).toBeVisible({ timeout: 5000 });
    });

    test('bulk reject requires reason', async ({ page }) => {
      await page.goto('/expenses/approvals');

      const checkbox = page.locator('input[type="checkbox"]').nth(1);
      await expect(
        checkbox.or(page.getByText(/no approvals|no pending|no data|empty/i))
      ).toBeVisible({ timeout: 10000 });
      if (await checkbox.isHidden()) {
        test.skip(true, 'No approvals available in this environment.');
      }
      await checkbox.check();

      const rejectButton = page.getByRole('button', { name: /reject/i });
      await rejectButton.click();

      await expect(page.getByLabel(/reason/i).or(page.getByPlaceholder(/reason/i))).toBeVisible({
        timeout: 3000,
      });
    });

    test('individual approve works', async ({ page }) => {
      await page.goto('/expenses/approvals');

      // Find individual approve button
      const approveIcon = page.locator('button[title*="Approve"], button:has(svg)').first();
      await expect(
        approveIcon.or(page.getByText(/no approvals|no pending|no data|empty/i))
      ).toBeVisible({ timeout: 10000 });
      if (await approveIcon.isHidden()) {
        test.skip(true, 'No approvals available in this environment.');
      }
      await approveIcon.click();

      await expect(page.getByText(/approved|success/i).first()).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('Statements', () => {
    test('renders statements list', async ({ page }) => {
      await page.goto('/expenses/statements');

      await expect(page.getByRole('heading', { name: /statement/i })).toBeVisible();

      // Verify import button exists
      await expect(
        page.getByRole('link', { name: /import/i }).or(
          page.getByRole('button', { name: /import/i })
        )
      ).toBeVisible();
    });

    test('statement actions menu works', async ({ page }) => {
      await page.goto('/expenses/statements');

      const row = page.locator('table tbody tr').first();
      await ensureRowsOrSkip(
        page,
        page.locator('table tbody tr'),
        /no statements|no data|empty/i,
        'No statements available in this environment.'
      );
      const moreButton = row.locator('button').last();
      await moreButton.click();

      await expect(page.getByText(/view|reconcile|close/i).first()).toBeVisible({
        timeout: 3000,
      });
    });
  });

  test.describe('Reports', () => {
    test('renders reports page with export options', async ({ page }) => {
      await page.goto('/expenses/reports');

      await expect(page.getByRole('heading', { name: /report/i })).toBeVisible();

      // Verify date range controls
      await expect(page.getByLabel(/start.*date/i)).toBeVisible();
      await expect(page.getByLabel(/end.*date/i)).toBeVisible();

      // Verify export button
      await expect(
        page.getByRole('button', { name: /export|download/i })
      ).toBeVisible();
    });

    test('date presets update date range', async ({ page }) => {
      await page.goto('/expenses/reports');

      // Click a preset button
      const thisMonth = page.getByRole('button', { name: /this month/i });
      await expect(thisMonth).toBeVisible();
      await thisMonth.click();

      const startInput = page.getByLabel(/start.*date/i);
      await expect(startInput).not.toHaveValue('');
    });

    test('export shows loading state', async ({ page }) => {
      await page.goto('/expenses/reports');

      const exportButton = page.getByRole('button', { name: /export|download/i });
      await exportButton.click();

      // Should show loading state
      await expect(
        page.getByText(/generating|loading/i).or(
          page.locator('[class*="spin"], [class*="animate"]')
        ).first()
      ).toBeVisible({ timeout: 5000 });
    });

  });

  test.describe('Cash Advances', () => {
    test('renders advances list', async ({ page }) => {
      await page.goto('/expenses/advances');

      await expect(page.getByRole('heading', { name: /advance/i })).toBeVisible();
    });

    test('create advance form validates required fields', async ({ page }) => {
      await page.goto('/expenses/advances/new');

      // Submit empty form
      await page.getByRole('button', { name: /create|save|submit/i }).click();

      await expect(
        page.getByText(/required|cannot be empty|please enter/i).first()
      ).toBeVisible({ timeout: 5000 });
    });
  });
});
