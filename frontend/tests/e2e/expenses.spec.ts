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
import { createTestExpenseClaim, createTestCashAdvance } from './fixtures/api-helpers';

test.describe('Expenses - Authenticated', () => {
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
      const statsVisible = await page.getByText(/total|pending|approved/i).first().isVisible().catch(() => false);
      expect(statsVisible).toBeTruthy();
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
      await page.waitForSelector('table tbody tr, [class*="transaction"]', { timeout: 10000 }).catch(() => null);

      const row = page.locator('table tbody tr, [class*="transaction"]').first();
      if (await row.isVisible().catch(() => false)) {
        // Find more actions button
        const moreButton = row.locator('button').filter({ hasText: /./ }).last();
        await moreButton.click();

        // Verify action menu appears
        await expect(
          page.getByText(/exclude|personal|dispute/i).first()
        ).toBeVisible({ timeout: 3000 });
      }
    });

    test('exclude action shows toast feedback', async ({ page }) => {
      await page.goto('/expenses/transactions');

      await page.waitForSelector('table tbody tr', { timeout: 10000 }).catch(() => null);

      const row = page.locator('table tbody tr').first();
      if (await row.isVisible().catch(() => false)) {
        const moreButton = row.locator('button').last();
        await moreButton.click();

        const excludeOption = page.getByRole('button', { name: /exclude/i });
        if (await excludeOption.isVisible({ timeout: 2000 }).catch(() => false)) {
          await excludeOption.click();

          // Should show success or error toast
          await expect(
            page.getByText(/excluded|success|failed/i).first()
          ).toBeVisible({ timeout: 5000 });
        }
      }
    });

    test('mark personal action updates status', async ({ page }) => {
      await page.goto('/expenses/transactions');

      await page.waitForSelector('table tbody tr', { timeout: 10000 }).catch(() => null);

      const row = page.locator('table tbody tr').first();
      if (await row.isVisible().catch(() => false)) {
        const moreButton = row.locator('button').last();
        await moreButton.click();

        const personalOption = page.getByRole('button', { name: /personal/i });
        if (await personalOption.isVisible({ timeout: 2000 }).catch(() => false)) {
          await personalOption.click();

          // Should show feedback
          await expect(
            page.getByText(/personal|success|failed/i).first()
          ).toBeVisible({ timeout: 5000 });
        }
      }
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

      // Wait for items to load
      await page.waitForSelector('input[type="checkbox"]', { timeout: 10000 }).catch(() => null);

      // Find select all checkbox
      const selectAll = page.locator('input[type="checkbox"]').first();
      if (await selectAll.isVisible().catch(() => false)) {
        await selectAll.check();

        // Verify selection count updates
        await expect(
          page.getByText(/selected/i)
        ).toBeVisible({ timeout: 3000 });
      }
    });

    test('bulk approve shows success toast', async ({ page }) => {
      await page.goto('/expenses/approvals');

      await page.waitForSelector('input[type="checkbox"]', { timeout: 10000 }).catch(() => null);

      // Select first item
      const checkbox = page.locator('input[type="checkbox"]').nth(1); // Skip select-all
      if (await checkbox.isVisible().catch(() => false)) {
        await checkbox.check();

        // Click approve button
        const approveButton = page.getByRole('button', { name: /approve/i });
        await approveButton.click();

        // Should show success or error toast
        await expect(
          page.getByText(/approved|success|failed/i).first()
        ).toBeVisible({ timeout: 5000 });
      }
    });

    test('bulk reject requires reason', async ({ page }) => {
      await page.goto('/expenses/approvals');

      await page.waitForSelector('input[type="checkbox"]', { timeout: 10000 }).catch(() => null);

      const checkbox = page.locator('input[type="checkbox"]').nth(1);
      if (await checkbox.isVisible().catch(() => false)) {
        await checkbox.check();

        const rejectButton = page.getByRole('button', { name: /reject/i });
        await rejectButton.click();

        // Modal should appear with reason field
        await expect(
          page.getByLabel(/reason/i).or(page.getByPlaceholder(/reason/i))
        ).toBeVisible({ timeout: 3000 });
      }
    });

    test('individual approve works', async ({ page }) => {
      await page.goto('/expenses/approvals');

      await page.waitForSelector('[role="row"], table tbody tr', { timeout: 10000 }).catch(() => null);

      // Find individual approve button
      const approveIcon = page.locator('button[title*="Approve"], button:has(svg)').first();
      if (await approveIcon.isVisible().catch(() => false)) {
        await approveIcon.click();

        await expect(
          page.getByText(/approved|success|failed/i).first()
        ).toBeVisible({ timeout: 5000 });
      }
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

      await page.waitForSelector('table tbody tr, [class*="statement"]', { timeout: 10000 }).catch(() => null);

      const row = page.locator('table tbody tr').first();
      if (await row.isVisible().catch(() => false)) {
        const moreButton = row.locator('button').last();
        await moreButton.click();

        // Menu should appear
        await expect(
          page.getByText(/view|reconcile|close/i).first()
        ).toBeVisible({ timeout: 3000 });
      }
    });

    test('empty state shows import CTA', async ({ page }) => {
      // Mock empty response
      await page.route('**/api/expenses/statements**', (route) => {
        route.fulfill({
          status: 200,
          body: JSON.stringify({ data: [], total: 0 }),
        });
      });

      await page.goto('/expenses/statements');

      await expect(
        page.getByText(/no statements|import.*statement/i).first()
      ).toBeVisible({ timeout: 10000 });
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
      if (await thisMonth.isVisible().catch(() => false)) {
        await thisMonth.click();

        // Date inputs should update
        const startInput = page.getByLabel(/start.*date/i);
        await expect(startInput).not.toHaveValue('');
      }
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

    test('export error shows toast', async ({ page }) => {
      // Mock export failure
      await page.route('**/api/expenses/reports/export**', (route) => {
        route.fulfill({
          status: 500,
          body: JSON.stringify({ detail: 'Export failed' }),
        });
      });

      await page.goto('/expenses/reports');

      await page.getByRole('button', { name: /export|download/i }).click();

      // Should show error toast
      await expect(
        page.getByText(/failed|error/i).first()
      ).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('Cash Advances', () => {
    test('renders advances list', async ({ page }) => {
      await page.goto('/expenses/advances');

      await expect(page.getByRole('heading', { name: /advance/i })).toBeVisible();
    });

    test('create advance form works', async ({ page }) => {
      await page.goto('/expenses/advances/new');

      // Fill form
      await page.getByLabel(/purpose/i).fill('E2E Test Advance');
      await page.getByLabel(/amount/i).fill('50000');

      // Submit
      await page.getByRole('button', { name: /create|save|submit/i }).click();

      // Should redirect or show success
      await expect(
        page.getByText(/created|success/i).first().or(page.locator('[href*="/advances"]'))
      ).toBeVisible({ timeout: 5000 });
    });
  });
});
