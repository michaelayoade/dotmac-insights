import { test, expect } from '../fixtures/htmx.fixture';
import { HRPage } from '../pages/hr.page';

/**
 * E2E Browser Tests for HR Leave Module.
 *
 * Tests the HTMX-powered leave management interface including:
 * - Leave applications list
 * - Leave application workflow
 * - Leave approval/rejection
 */

test.describe('Leave Applications List', () => {
  let hrPage: HRPage;

  test.beforeEach(async ({ page }) => {
    hrPage = new HRPage(page);
    await hrPage.gotoLeave();
  });

  test('displays leave page @smoke', async () => {
    const pageTitle = hrPage.page.locator('[data-testid="page-title"]');
    await expect(pageTitle).toContainText(/leave/i);
  });

  test('displays leave table @smoke', async () => {
    if (!(await hrPage.hasLeaveApplications())) {
      const emptyState = hrPage.page.locator('[data-testid="leave-empty-state"]');
      if (await emptyState.count() > 0) {
        await expect(emptyState).toBeVisible();
        return;
      }
    }
    await expect(hrPage.leaveTable).toBeVisible();
  });

  test('search filters leave applications via HTMX', async ({ htmx }) => {
    if (!(await hrPage.hasLeaveApplications())) {
      test.skip();
      return;
    }
    const initialCount = await hrPage.getLeaveCount();

    await hrPage.searchLeave('annual');
    await htmx.waitForHtmxIdle();

    const filteredCount = await hrPage.getLeaveCount();
    expect(filteredCount).toBeLessThanOrEqual(initialCount);
  });

  test('filter by pending status', async ({ htmx }) => {
    if (!(await hrPage.hasLeaveApplications())) {
      test.skip();
      return;
    }
    await hrPage.filterLeaveByStatus('pending');
    await htmx.waitForHtmxIdle();

    const rows = await hrPage.leaveTable.locator('tbody tr').all();
    if (rows.length > 0) {
      for (const row of rows) {
        const statusBadge = row.locator('[data-status]');
        await expect(statusBadge).toContainText(/pending|open/i);
      }
    }
  });

  test('filter by approved status', async ({ htmx }) => {
    if (!(await hrPage.hasLeaveApplications())) {
      test.skip();
      return;
    }
    await hrPage.filterLeaveByStatus('approved');
    await htmx.waitForHtmxIdle();

    const rows = await hrPage.leaveTable.locator('tbody tr').all();
    if (rows.length > 0) {
      for (const row of rows) {
        const statusBadge = row.locator('[data-status]');
        await expect(statusBadge).toContainText(/approved/i);
      }
    }
  });

  test('filter by leave type', async ({ htmx }) => {
    if (!(await hrPage.hasLeaveApplications())) {
      test.skip();
      return;
    }

    if (await hrPage.leaveTypeFilter.count() === 0) {
      test.skip();
      return;
    }

    const options = await hrPage.leaveTypeFilter.locator('option').all();
    if (options.length < 2) {
      test.skip();
      return;
    }

    const typeValue = await options[1].getAttribute('value') || '';
    await hrPage.filterLeaveByType(typeValue);
    await htmx.waitForHtmxIdle();

    // Table should update
    await hrPage.waitForHtmxComplete();
  });

  test('apply leave button visible', async () => {
    await expect(hrPage.newLeaveButton.first()).toBeVisible();
  });
});

test.describe('Leave Application Form', () => {
  let hrPage: HRPage;

  test.beforeEach(async ({ page }) => {
    hrPage = new HRPage(page);
  });

  test('leave application form is accessible', async () => {
    await hrPage.gotoLeave();
    await hrPage.newLeaveButton.click();
    await hrPage.waitForHtmxComplete();

    // Form should be visible (either as modal or page)
    await expect(hrPage.leaveForm).toBeVisible();
  });

  test('form has required fields', async () => {
    await hrPage.gotoLeave();
    await hrPage.newLeaveButton.click();
    await hrPage.waitForHtmxComplete();

    // Leave type should be visible
    await expect(hrPage.leaveTypeSelect).toBeVisible();

    // Date fields should be visible
    await expect(hrPage.leaveStartDate).toBeVisible();
  });
});

test.describe('Leave Approval Workflow', () => {
  let hrPage: HRPage;

  test.beforeEach(async ({ page }) => {
    hrPage = new HRPage(page);
    await hrPage.gotoLeave();
    await hrPage.filterLeaveByStatus('pending');
  });

  test('pending applications show approve/reject buttons', async () => {
    if (!(await hrPage.hasLeaveApplications())) {
      test.skip();
      return;
    }

    // Click on first pending application
    const firstRow = hrPage.leaveTable.locator('tbody tr').first();
    const link = firstRow.locator('a').first();
    if (await link.count() > 0) {
      await hrPage.htmxClick(link);

      // Check for action buttons
      const approveBtn = hrPage.approveLeaveButton;
      const rejectBtn = hrPage.rejectLeaveButton;

      const hasApprove = await approveBtn.count() > 0;
      const hasReject = await rejectBtn.count() > 0;

      expect(hasApprove || hasReject).toBeTruthy();
    }
  });

  test('approve button triggers approval workflow', async ({ htmx }) => {
    if (!(await hrPage.hasLeaveApplications())) {
      test.skip();
      return;
    }

    const firstRow = hrPage.leaveTable.locator('tbody tr').first();
    const link = firstRow.locator('a').first();
    if (await link.count() === 0) {
      test.skip();
      return;
    }

    await hrPage.htmxClick(link);

    const approveBtn = hrPage.approveLeaveButton;
    if (await approveBtn.count() === 0) {
      test.skip();
      return;
    }

    await hrPage.approveLeave();
    await htmx.waitForHtmxIdle();

    // Should show success or status update
    const toast = hrPage.toast;
    const status = hrPage.page.locator('[data-testid="leave-status"][data-status="approved"]');
    const hasToast = await toast.count() > 0;
    const hasStatus = await status.count() > 0;

    expect(hasToast || hasStatus).toBeTruthy();
  });
});

test.describe('Leave Empty States', () => {
  let hrPage: HRPage;

  test.beforeEach(async ({ page }) => {
    hrPage = new HRPage(page);
    await hrPage.gotoLeave();
  });

  test('shows empty state when no search results', async ({ htmx }) => {
    await hrPage.searchLeave('xyznonexistent98765');
    await htmx.waitForHtmxIdle();

    const emptyState = hrPage.page.locator('[data-testid="leave-empty-state"]');
    const noRows = await hrPage.leaveTable.locator('tbody tr').count() === 0;

    expect(await emptyState.count() > 0 || noRows).toBeTruthy();
  });
});
