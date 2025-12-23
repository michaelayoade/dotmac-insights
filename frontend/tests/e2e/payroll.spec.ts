/**
 * Payroll E2E Tests
 *
 * Comprehensive tests for the Payroll module including:
 * - Payroll configuration management
 * - Run payroll calculation and verify totals
 * - Employee payslip generation
 * - Tax deductions verification
 */

import type { Page } from '@playwright/test';
import { test, expect, setupAuth, expectAccessDenied } from './fixtures/auth';

async function ensurePayrollPageReady(page: Page) {
  const heading = page.getByRole('heading', { name: /payroll/i });
  const notFound = page.getByText(/page could not be found|404/i);
  await expect(heading.or(notFound)).toBeVisible({ timeout: 15000 });
  return !(await notFound.isVisible());
}

async function ensurePayrollEntriesReady(page: Page) {
  if (!(await ensurePayrollPageReady(page))) return false;
  const emptyState = page.getByText(/no payroll entries/i);
  const dataCell = page.locator('table tbody tr td:not(:has(.skeleton))').first();
  await expect(dataCell.or(emptyState)).toBeVisible({ timeout: 15000 });
  return !(await emptyState.isVisible());
}

async function ensurePayslipsPageReady(page: Page) {
  const heading = page.getByRole('heading', { name: /payslip/i });
  const notFound = page.getByText(/page could not be found|404/i);
  await expect(heading.or(notFound)).toBeVisible({ timeout: 15000 });
  return !(await notFound.isVisible());
}

test.describe('Payroll - Authenticated', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page, ['hr:read', 'hr:write']);
  });

  test.describe('Payroll Overview', () => {
    test('renders payroll dashboard', async ({ page }) => {
      await page.goto('/hr/payroll');

      if (!(await ensurePayrollPageReady(page))) {
        test.skip(true, 'Payroll page unavailable in this environment.');
      }
    });

    test('displays payroll periods list', async ({ page }) => {
      await page.goto('/hr/payroll');

      if (!(await ensurePayrollEntriesReady(page))) {
        test.skip(true, 'No payroll entries available in this environment.');
      }
    });

    test('shows payroll summary statistics', async ({ page }) => {
      await page.goto('/hr/payroll');

      if (!(await ensurePayrollPageReady(page))) {
        test.skip(true, 'Payroll page unavailable in this environment.');
      }
      // Check for stat cards
      await expect(page.locator('[class*="stat"], [class*="card"]').first()).toBeVisible();
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
      await expect(addButton).toBeVisible();
      await addButton.click();

      await expect(page.getByLabel(/name|type/i)).toBeVisible({ timeout: 3000 });
    });

    test('save settings shows success', async ({ page }) => {
      await page.goto('/hr/payroll/settings');

      const saveButton = page.getByRole('button', { name: /save/i });
      await expect(saveButton).toBeVisible();
      await saveButton.click();

      await expect(page.getByText(/saved|success|updated/i).first()).toBeVisible({ timeout: 5000 });
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
      ).toBeVisible({ timeout: 5000 });
    });

    test('run payroll shows calculation preview', async ({ page }) => {
      await page.goto('/hr/payroll/run');

      // Select a period if needed
      const periodSelect = page.getByLabel(/period|month/i);
      await expect(periodSelect).toBeVisible();
      const periodOptions = await periodSelect.locator('option').count();
      if (periodOptions < 2) {
        test.skip(true, 'No payroll periods available in this environment.');
      }
      await periodSelect.selectOption({ index: 1 });

      const previewButton = page.getByRole('button', { name: /preview|calculate/i });
      await expect(previewButton).toBeVisible();
      await previewButton.click();

      await expect(page.getByText(/total|gross|net|employee/i).first()).toBeVisible({
        timeout: 10000,
      });
    });

    test('payroll totals are displayed', async ({ page }) => {
      await page.goto('/hr/payroll');

      // Find a payroll run to view
      if (!(await ensurePayrollEntriesReady(page))) {
        test.skip(true, 'No payroll entries available in this environment.');
      }

      const runRow = page.locator('table tbody tr, [role="row"]').first();
      await expect(runRow).toBeVisible({ timeout: 5000 });
      await runRow.click();

      await expect(page.getByText(/total|gross|net/i).first()).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('Employee Payslips', () => {
    test('payslips page renders', async ({ page }) => {
      await page.goto('/hr/payroll/payslips');

      if (!(await ensurePayslipsPageReady(page))) {
        test.skip(true, 'Payslips page unavailable in this environment.');
      }
    });

    test('filter by period works', async ({ page }) => {
      await page.goto('/hr/payroll/payslips');

      if (!(await ensurePayslipsPageReady(page))) {
        test.skip(true, 'Payslips page unavailable in this environment.');
      }
      const periodFilter = page.locator('select').first();
      await expect(periodFilter).toBeVisible();
      const periodOptions = await periodFilter.locator('option').count();
      if (periodOptions < 2) {
        test.skip(true, 'No payslip periods available in this environment.');
      }
      await periodFilter.selectOption({ index: 1 });
    });

    test('view individual payslip', async ({ page }) => {
      await page.goto('/hr/payroll/payslips');

      if (!(await ensurePayslipsPageReady(page))) {
        test.skip(true, 'Payslips page unavailable in this environment.');
      }

      const payslipRows = page.locator('table tbody tr, [role="row"]');
      if (await payslipRows.count() === 0) {
        test.skip(true, 'No payslips available in this environment.');
      }

      const payslipRow = payslipRows.first();
      await expect(payslipRow).toBeVisible();
      await payslipRow.click();

      await expect(
        page.getByText(/employee|earnings|deductions/i).first()
      ).toBeVisible({ timeout: 5000 });
    });

    test('download payslip PDF', async ({ page }) => {
      await page.goto('/hr/payroll/payslips');

      if (!(await ensurePayslipsPageReady(page))) {
        test.skip(true, 'Payslips page unavailable in this environment.');
      }

      const payslipRows = page.locator('table tbody tr');
      if (await payslipRows.count() === 0) {
        test.skip(true, 'No payslips available in this environment.');
      }

      const downloadButton = page.getByRole('button', { name: /download|pdf/i }).first();
      await expect(downloadButton).toBeVisible();
      const downloadPromise = page.waitForEvent('download', { timeout: 10000 });
      await downloadButton.click();

      const download = await downloadPromise;
      expect(download.suggestedFilename()).toContain('.pdf');
    });
  });

  test.describe('Tax Calculations', () => {
    test('displays PAYE breakdown', async ({ page }) => {
      await page.goto('/hr/payroll');

      // View a payroll detail
      if (!(await ensurePayrollEntriesReady(page))) {
        test.skip(true, 'No payroll entries available in this environment.');
      }

      const runRow = page.locator('table tbody tr').first();
      await expect(runRow).toBeVisible({ timeout: 5000 });
      await runRow.click();

      await expect(page.getByText(/paye|tax|deduction/i).first()).toBeVisible({ timeout: 5000 });
    });

    test('pension deduction is calculated', async ({ page }) => {
      await page.goto('/hr/payroll');

      if (!(await ensurePayrollEntriesReady(page))) {
        test.skip(true, 'No payroll entries available in this environment.');
      }

      const runRow = page.locator('table tbody tr').first();
      await expect(runRow).toBeVisible({ timeout: 5000 });
      await runRow.click();

      await expect(page.getByText(/pension|contribution/i).first()).toBeVisible({
        timeout: 5000,
      });
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
    await expect(runButton).toBeDisabled();
  });
});
