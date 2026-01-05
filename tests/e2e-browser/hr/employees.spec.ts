import { Locator } from '@playwright/test';
import { test, expect } from '../fixtures/htmx.fixture';
import { HRPage } from '../pages/hr.page';

/**
 * E2E Browser Tests for HR Employees Module.
 *
 * Tests the HTMX-powered employee management interface including:
 * - Employee list with search and filters
 * - Employee detail view
 * - Department and status filters
 */

test.describe('Employees List', () => {
  let hrPage: HRPage;

  test.beforeEach(async ({ page }) => {
    hrPage = new HRPage(page);
    await hrPage.gotoEmployees();
  });

  test('displays employees page @smoke', async () => {
    const pageTitle = hrPage.page.locator('[data-testid="page-title"]');
    await expect(pageTitle).toContainText(/employee/i);
  });

  test('displays employees table @smoke', async () => {
    if (!(await hrPage.hasEmployees())) {
      await hrPage.expectEmptyState();
      return;
    }
    await expect(hrPage.employeesTable).toBeVisible();
  });

  test('search filters employees via HTMX @critical', async ({ htmx }) => {
    if (!(await hrPage.hasEmployees())) {
      test.skip();
      return;
    }
    const initialCount = await hrPage.getEmployeeCount();

    await hrPage.searchEmployees('John');
    await htmx.waitForHtmxIdle();

    const filteredCount = await hrPage.getEmployeeCount();
    expect(filteredCount).toBeLessThanOrEqual(initialCount);
  });

  test('filter by department updates table', async ({ htmx }) => {
    if (!(await hrPage.hasEmployees())) {
      test.skip();
      return;
    }

    // Check if department filter exists
    if (await hrPage.departmentFilter.count() === 0) {
      test.skip();
      return;
    }

    const options = await hrPage.page.locator('[data-testid^="department-option-"]').all();
    let option: Locator | null = null;
    for (const candidate of options) {
      const testId = await candidate.getAttribute('data-testid');
      if (testId && testId !== 'department-option-all') {
        option = candidate;
        break;
      }
    }
    if (!option) {
      test.skip();
      return;
    }

    const optionTestId = await option.getAttribute('data-testid') || '';
    const departmentValue = optionTestId.replace('department-option-', '');
    await hrPage.filterByDepartment(departmentValue);
    await htmx.waitForHtmxIdle();

    // Table should update
    await hrPage.waitForHtmxComplete();
  });

  test('filter by active status', async ({ htmx }) => {
    if (!(await hrPage.hasEmployees())) {
      test.skip();
      return;
    }
    await hrPage.filterByStatus('active');
    await htmx.waitForHtmxIdle();

    const rows = await hrPage.employeesTable.locator('tbody tr').all();
    if (rows.length > 0) {
      for (const row of rows) {
        const statusBadge = row.locator('[data-status]');
        await expect(statusBadge).toContainText(/active/i);
      }
    }
  });

  test('click employee navigates to detail', async ({ page }) => {
    if (!(await hrPage.hasEmployees())) {
      test.skip();
      return;
    }
    const firstRow = await hrPage.getEmployeeRowData(0);

    await hrPage.clickEmployee(firstRow.name.trim());

    await expect(page).toHaveURL(/\/employees\/\d+/);
  });

  test('new employee button navigates to form', async ({ page }) => {
    await hrPage.newEmployeeButton.click();
    await expect(page).toHaveURL(/\/new|\/create/);
  });
});

test.describe('Employee Detail View', () => {
  let hrPage: HRPage;

  test.beforeEach(async ({ page }) => {
    hrPage = new HRPage(page);
    await hrPage.gotoEmployees();
    if (!(await hrPage.hasEmployees())) {
      test.skip();
      return;
    }
    const firstRow = await hrPage.getEmployeeRowData(0);
    await hrPage.clickEmployee(firstRow.name.trim());
  });

  test('displays employee header with name', async () => {
    await expect(hrPage.employeeHeader).toBeVisible();
  });

  test('displays employee status', async () => {
    await expect(hrPage.employeeStatus.first()).toBeVisible();
  });

  test('displays department information', async () => {
    await expect(hrPage.employeeDepartment).toBeVisible();
  });

  test('displays designation/job title', async () => {
    await expect(hrPage.employeeDesignation).toBeVisible();
  });

  test('displays contact information', async () => {
    await expect(hrPage.page.locator('[data-testid="employee-email"]')).toBeVisible();
    await expect(hrPage.page.locator('[data-testid="employee-phone"]')).toBeVisible();
  });
});

test.describe('Employee Empty States', () => {
  let hrPage: HRPage;

  test.beforeEach(async ({ page }) => {
    hrPage = new HRPage(page);
    await hrPage.gotoEmployees();
  });

  test('shows empty state when no search results', async ({ htmx }) => {
    await hrPage.searchEmployees('xyznonexistent98765');
    await htmx.waitForHtmxIdle();

    const emptyState = hrPage.page.locator('[data-testid="employees-empty-state"]');
    const noRows = await hrPage.employeesTable.locator('tbody tr').count() === 0;

    expect(await emptyState.count() > 0 || noRows).toBeTruthy();
  });
});
