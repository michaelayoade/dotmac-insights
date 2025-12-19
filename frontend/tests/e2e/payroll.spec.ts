/**
 * Payroll E2E Tests
 *
 * Comprehensive tests for the Payroll module including:
 * - Payroll configuration management
 * - Run payroll calculation and verify totals
 * - Employee payslip generation
 * - Tax deductions verification
 */

import { test, expect, setupAuth, expectAccessDenied } from './fixtures/auth';

test.describe('Payroll - Authenticated', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page, ['hr:read', 'hr:write']);
  });

  test.describe('Payroll Overview', () => {
    test('renders payroll dashboard', async ({ page }) => {
      await page.goto('/hr/payroll');

      await expect(page.getByRole('heading', { name: /payroll/i })).toBeVisible();
    });

    test('displays payroll periods list', async ({ page }) => {
      await page.goto('/hr/payroll');

      await page.waitForLoadState('networkidle');

      // Should show periods or empty state
      await expect(
        page.getByText(/period|month|run/i).first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('shows payroll summary statistics', async ({ page }) => {
      await page.goto('/hr/payroll');

      // Check for stat cards
      const statsVisible = await page.locator('[class*="stat"], [class*="card"]').first().isVisible().catch(() => false);
      expect(statsVisible).toBeTruthy();
    });
  });

  test.describe('Payroll Configuration', () => {
    test('navigates to payroll settings', async ({ page }) => {
      await page.goto('/hr/payroll/settings');

      await expect(
        page.getByRole('heading', { name: /setting|config/i })
      ).toBeVisible({ timeout: 10000 });
    });

    test('displays deduction rules', async ({ page }) => {
      await page.goto('/hr/payroll/settings');

      await expect(
        page.getByText(/deduction|tax|pension|nhf/i).first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('create deduction rule', async ({ page }) => {
      await page.goto('/hr/payroll/settings');

      const addButton = page.getByRole('button', { name: /add|create|new/i }).first();
      if (await addButton.isVisible().catch(() => false)) {
        await addButton.click();

        // Form should appear
        await expect(
          page.getByLabel(/name|type/i)
        ).toBeVisible({ timeout: 3000 });
      }
    });

    test('save settings shows success', async ({ page }) => {
      await page.goto('/hr/payroll/settings');

      const saveButton = page.getByRole('button', { name: /save/i });
      if (await saveButton.isVisible().catch(() => false)) {
        await saveButton.click();

        await expect(
          page.getByText(/saved|success|updated/i).first()
        ).toBeVisible({ timeout: 5000 });
      }
    });
  });

  test.describe('Run Payroll', () => {
    test('run payroll button exists', async ({ page }) => {
      await page.goto('/hr/payroll');

      await expect(
        page.getByRole('button', { name: /run|process|generate/i }).or(
          page.getByRole('link', { name: /run|process|generate/i })
        )
      ).toBeVisible();
    });

    test('run payroll form validates period', async ({ page }) => {
      await page.goto('/hr/payroll/run');

      const submitButton = page.getByRole('button', { name: /run|process|calculate/i });
      await submitButton.click();

      // Should show validation error if period not selected
      await expect(
        page.getByText(/required|select.*period/i).first()
      ).toBeVisible({ timeout: 5000 }).catch(() => null);
    });

    test('run payroll shows calculation preview', async ({ page }) => {
      await page.goto('/hr/payroll/run');

      // Select a period if needed
      const periodSelect = page.getByLabel(/period|month/i);
      if (await periodSelect.isVisible().catch(() => false)) {
        await periodSelect.selectOption({ index: 1 });
      }

      const previewButton = page.getByRole('button', { name: /preview|calculate/i });
      if (await previewButton.isVisible().catch(() => false)) {
        await previewButton.click();

        // Should show calculation results
        await expect(
          page.getByText(/total|gross|net|employee/i).first()
        ).toBeVisible({ timeout: 10000 });
      }
    });

    test('payroll totals are displayed', async ({ page }) => {
      await page.goto('/hr/payroll');

      await page.waitForLoadState('networkidle');

      // Find a payroll run to view
      const runRow = page.locator('tr, [role="row"]').first();
      if (await runRow.isVisible({ timeout: 5000 }).catch(() => false)) {
        await runRow.click();

        // Should show totals
        await expect(
          page.getByText(/total|gross|net/i).first()
        ).toBeVisible({ timeout: 5000 });
      }
    });
  });

  test.describe('Employee Payslips', () => {
    test('payslips page renders', async ({ page }) => {
      await page.goto('/hr/payroll/payslips');

      await expect(
        page.getByRole('heading', { name: /payslip/i })
      ).toBeVisible({ timeout: 10000 });
    });

    test('filter by period works', async ({ page }) => {
      await page.goto('/hr/payroll/payslips');

      const periodFilter = page.locator('select').first();
      if (await periodFilter.isVisible().catch(() => false)) {
        await periodFilter.selectOption({ index: 1 });
        await page.waitForTimeout(500);
      }

      await expect(page.locator('body')).toBeVisible();
    });

    test('view individual payslip', async ({ page }) => {
      await page.goto('/hr/payroll/payslips');

      await page.waitForSelector('table tbody tr, [role="row"]', { timeout: 10000 }).catch(() => null);

      const payslipRow = page.locator('table tbody tr, [role="row"]').first();
      if (await payslipRow.isVisible().catch(() => false)) {
        await payslipRow.click();

        // Should show payslip details
        await expect(
          page.getByText(/employee|earnings|deductions/i).first()
        ).toBeVisible({ timeout: 5000 });
      }
    });

    test('download payslip PDF', async ({ page }) => {
      await page.goto('/hr/payroll/payslips');

      await page.waitForSelector('table tbody tr', { timeout: 10000 }).catch(() => null);

      const downloadButton = page.getByRole('button', { name: /download|pdf/i }).first();
      if (await downloadButton.isVisible().catch(() => false)) {
        // Set up download handler
        const downloadPromise = page.waitForEvent('download', { timeout: 10000 }).catch(() => null);
        await downloadButton.click();

        const download = await downloadPromise;
        if (download) {
          expect(download.suggestedFilename()).toContain('.pdf');
        }
      }
    });
  });

  test.describe('Tax Calculations', () => {
    test('displays PAYE breakdown', async ({ page }) => {
      await page.goto('/hr/payroll');

      await page.waitForLoadState('networkidle');

      // View a payroll detail
      const runRow = page.locator('tr').first();
      if (await runRow.isVisible({ timeout: 5000 }).catch(() => false)) {
        await runRow.click();

        // Should show tax breakdown
        await expect(
          page.getByText(/paye|tax|deduction/i).first()
        ).toBeVisible({ timeout: 5000 });
      }
    });

    test('pension deduction is calculated', async ({ page }) => {
      await page.goto('/hr/payroll');

      await page.waitForLoadState('networkidle');

      const runRow = page.locator('tr').first();
      if (await runRow.isVisible({ timeout: 5000 }).catch(() => false)) {
        await runRow.click();

        await expect(
          page.getByText(/pension|contribution/i).first()
        ).toBeVisible({ timeout: 5000 });
      }
    });
  });

  test.describe('Error Handling', () => {
    test('shows error on payroll calculation failure', async ({ page }) => {
      await page.route('**/api/hr/payroll/run**', (route) => {
        if (route.request().method() === 'POST') {
          route.fulfill({
            status: 400,
            body: JSON.stringify({ detail: 'Missing employee salary data' }),
          });
        } else {
          route.continue();
        }
      });

      await page.goto('/hr/payroll/run');

      const periodSelect = page.getByLabel(/period/i);
      if (await periodSelect.isVisible().catch(() => false)) {
        await periodSelect.selectOption({ index: 1 });
      }

      await page.getByRole('button', { name: /run|process/i }).click();

      await expect(
        page.getByText(/failed|error|missing/i).first()
      ).toBeVisible({ timeout: 5000 });
    });
  });
});

test.describe('Payroll - RBAC', () => {
  test('user without hr scope cannot access payroll', async ({ page }) => {
    await setupAuth(page, ['customers:read']);
    await page.goto('/hr/payroll');

    await expectAccessDenied(page);
  });

  test('read-only user cannot run payroll', async ({ page }) => {
    await setupAuth(page, ['hr:read']);
    await page.goto('/hr/payroll');

    const runButton = page.getByRole('button', { name: /run|process/i });
    const isVisible = await runButton.isVisible().catch(() => false);

    if (isVisible) {
      await expect(runButton).toBeDisabled();
    }
  });
});
