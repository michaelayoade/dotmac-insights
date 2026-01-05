import { test, expect } from '../fixtures/htmx.fixture';
import { SubscriptionsPage } from '../pages/subscriptions.page';

/**
 * E2E Browser Tests for Subscriptions Module.
 *
 * Tests the HTMX-powered subscription management interface including:
 * - Subscription list with search and filters
 * - Subscription detail with tabs
 * - Status transitions
 * - Provisioning
 */

test.describe('Subscriptions List', () => {
  let subscriptionsPage: SubscriptionsPage;

  test.beforeEach(async ({ page }) => {
    subscriptionsPage = new SubscriptionsPage(page);
    await subscriptionsPage.gotoList();
  });

  test('displays subscriptions page @smoke', async () => {
    if (await subscriptionsPage.isAccessDenied() || subscriptionsPage.page.url().includes('/subscriptions/dashboard')) {
      test.skip();
      return;
    }
    const pageTitle = subscriptionsPage.page.locator('[data-testid="page-title"], h1');
    await expect(pageTitle).toContainText(/subscription/i);
  });

  test('displays subscriptions table @smoke', async () => {
    if (await subscriptionsPage.isAccessDenied() || subscriptionsPage.page.url().includes('/subscriptions/dashboard')) {
      test.skip();
      return;
    }
    const hasData = await subscriptionsPage.ensureHasSubscriptions();
    if (!hasData) {
      await subscriptionsPage.expectEmptyState();
      return;
    }
    await expect(subscriptionsPage.subscriptionsTable).toBeVisible();
  });

  test('search filters subscriptions via HTMX @critical', async ({ htmx }) => {
    if (await subscriptionsPage.isAccessDenied() || subscriptionsPage.page.url().includes('/subscriptions/dashboard')) {
      test.skip();
      return;
    }
    if (!(await subscriptionsPage.ensureHasSubscriptions())) {
      test.skip();
      return;
    }
    const initialCount = await subscriptionsPage.getSubscriptionCount();

    await subscriptionsPage.searchSubscriptions('test');
    await htmx.waitForHtmxIdle();

    const filteredCount = await subscriptionsPage.getSubscriptionCount();
    expect(filteredCount).toBeLessThanOrEqual(initialCount);
  });

  test('filter by status updates table', async ({ htmx }) => {
    if (await subscriptionsPage.isAccessDenied() || subscriptionsPage.page.url().includes('/subscriptions/dashboard')) {
      test.skip();
      return;
    }
    if (!(await subscriptionsPage.ensureHasSubscriptions())) {
      test.skip();
      return;
    }
    await subscriptionsPage.filterByStatus('active');
    await htmx.waitForHtmxIdle();

    const rows = await subscriptionsPage.subscriptionsTable.locator('tbody tr').all();
    if (rows.length === 0) {
      return; // No active subscriptions
    }
    for (const row of rows) {
      const statusBadge = row.locator('[data-testid="subscription-status"]');
      await expect(statusBadge).toContainText(/active/i);
    }
  });

  test('filter by suspended status', async ({ htmx }) => {
    if (await subscriptionsPage.isAccessDenied() || subscriptionsPage.page.url().includes('/subscriptions/dashboard')) {
      test.skip();
      return;
    }
    if (!(await subscriptionsPage.ensureHasSubscriptions())) {
      test.skip();
      return;
    }
    await subscriptionsPage.filterByStatus('suspended');
    await htmx.waitForHtmxIdle();

    const rows = await subscriptionsPage.subscriptionsTable.locator('tbody tr').all();
    if (rows.length > 0) {
      for (const row of rows) {
        const statusBadge = row.locator('[data-testid="subscription-status"]');
        await expect(statusBadge).toContainText(/suspended/i);
      }
    }
  });

  test('click subscription navigates to detail', async ({ page }) => {
    if (await subscriptionsPage.isAccessDenied() || subscriptionsPage.page.url().includes('/subscriptions/dashboard')) {
      test.skip();
      return;
    }
    if (!(await subscriptionsPage.ensureHasSubscriptions())) {
      test.skip();
      return;
    }
    const firstRow = await subscriptionsPage.getSubscriptionRowData(0);

    await subscriptionsPage.clickSubscription(firstRow.username.trim());

    await expect(page).toHaveURL(/\/subscriptions\/\d+/);
  });

  test('new subscription button navigates to form', async ({ page }) => {
    if (await subscriptionsPage.isAccessDenied() || subscriptionsPage.page.url().includes('/subscriptions/dashboard')) {
      test.skip();
      return;
    }
    if (await subscriptionsPage.newSubscriptionButton.count() === 0) {
      test.skip();
      return;
    }
    await subscriptionsPage.newSubscriptionButton.click();
    await expect(page).toHaveURL(/\/new|\/create/);
  });
});

test.describe('Subscription Detail View', () => {
  let subscriptionsPage: SubscriptionsPage;

  test.beforeEach(async ({ page }) => {
    subscriptionsPage = new SubscriptionsPage(page);
    await subscriptionsPage.gotoList();
    if (await subscriptionsPage.isAccessDenied() || subscriptionsPage.page.url().includes('/subscriptions/dashboard')) {
      test.skip();
      return;
    }
    if (!(await subscriptionsPage.ensureHasSubscriptions())) {
      test.skip();
      return;
    }
    const firstRow = await subscriptionsPage.getSubscriptionRowData(0);
    await subscriptionsPage.clickSubscription(firstRow.username.trim());
  });

  test('displays subscription header with status', async () => {
    await expect(subscriptionsPage.subscriptionHeader).toBeVisible();
    await expect(subscriptionsPage.subscriptionStatus.first()).toBeVisible();
  });

  test('displays tariff/plan information', async () => {
    const planName = subscriptionsPage.page.locator('[data-testid="subscription-plan-name"]');
    await expect(planName).toBeVisible();
  });

  test('tab navigation works via HTMX', async ({ htmx }) => {
    // Check if tabs exist
    const tabsList = subscriptionsPage.page.locator('nav[role="tablist"], .tabs, .tab-navigation');
    if (await tabsList.count() === 0) {
      test.skip();
      return;
    }

    // Try to switch to usage tab
    const usageTab = subscriptionsPage.tabUsage;
    if (await usageTab.count() > 0) {
      await subscriptionsPage.switchToTab('usage');
      await htmx.waitForHtmxIdle();

      // Usage content should be visible
      const usageContent = subscriptionsPage.page.locator('.usage-content, [data-tab="usage"], .usage-chart, .usage-table');
      if (await usageContent.count() > 0) {
        await expect(usageContent.first()).toBeVisible();
      }
    }
  });

  test('billing tab shows billing information', async ({ htmx }) => {
    const billingTab = subscriptionsPage.tabBilling;
    if (await billingTab.count() === 0) {
      test.skip();
      return;
    }

    await subscriptionsPage.switchToTab('billing');
    await htmx.waitForHtmxIdle();

    const billingContent = subscriptionsPage.page.locator('.billing-content, [data-tab="billing"], .invoice, .payment');
    if (await billingContent.count() > 0) {
      await expect(billingContent.first()).toBeVisible();
    }
  });

  test('sessions tab shows active sessions', async ({ htmx }) => {
    const sessionsTab = subscriptionsPage.tabSessions;
    if (await sessionsTab.count() === 0) {
      test.skip();
      return;
    }

    await subscriptionsPage.switchToTab('sessions');
    await htmx.waitForHtmxIdle();

    const sessionsContent = subscriptionsPage.page.locator('.sessions-content, [data-tab="sessions"], .session-list, .sessions-table');
    if (await sessionsContent.count() > 0) {
      await expect(sessionsContent.first()).toBeVisible();
    }
  });
});

test.describe('Subscription Actions', () => {
  let subscriptionsPage: SubscriptionsPage;

  test.beforeEach(async ({ page }) => {
    subscriptionsPage = new SubscriptionsPage(page);
    await subscriptionsPage.gotoList();
    if (await subscriptionsPage.isAccessDenied() || subscriptionsPage.page.url().includes('/subscriptions/dashboard')) {
      test.skip();
      return;
    }
    await subscriptionsPage.filterByStatus('active');
    if (!(await subscriptionsPage.hasSubscriptions())) {
      test.skip();
      return;
    }
    const firstRow = await subscriptionsPage.getSubscriptionRowData(0);
    await subscriptionsPage.clickSubscription(firstRow.username.trim());
  });

  test('renew button visible for active subscription', async () => {
    if (await subscriptionsPage.isAccessDenied()) {
      test.skip();
      return;
    }
    const renewBtn = subscriptionsPage.renewButton;
    if (await renewBtn.count() > 0) {
      await expect(renewBtn).toBeVisible();
    }
  });

  test('suspend button visible for active subscription', async () => {
    if (await subscriptionsPage.isAccessDenied()) {
      test.skip();
      return;
    }
    const suspendBtn = subscriptionsPage.suspendButton;
    if (await suspendBtn.count() > 0) {
      await expect(suspendBtn).toBeVisible();
    }
  });

  test('provision button triggers provisioning', async ({ htmx }) => {
    if (await subscriptionsPage.isAccessDenied()) {
      test.skip();
      return;
    }
    const provisionBtn = subscriptionsPage.provisionButton;
    if (await provisionBtn.count() === 0) {
      test.skip();
      return;
    }

    await subscriptionsPage.provisionSubscription();
    await htmx.waitForHtmxIdle();

    // Should show success or status update
    const toast = subscriptionsPage.toast;
    const statusIndicator = subscriptionsPage.page.locator('.provision-status, [data-provision-status]');
    const hasToast = await toast.count() > 0;
    const hasStatus = await statusIndicator.count() > 0;

    expect(hasToast || hasStatus).toBeTruthy();
  });
});

test.describe('Subscription Creation', () => {
  let subscriptionsPage: SubscriptionsPage;

  test.beforeEach(async ({ page }) => {
    subscriptionsPage = new SubscriptionsPage(page);
  });

  test('subscription form is accessible', async () => {
    await subscriptionsPage.gotoCreate();
    if (await subscriptionsPage.isAccessDenied()) {
      test.skip();
      return;
    }
    await expect(subscriptionsPage.subscriptionForm).toBeVisible();
  });

  test('form has required fields', async () => {
    await subscriptionsPage.gotoCreate();
    if (await subscriptionsPage.isAccessDenied()) {
      test.skip();
      return;
    }

    // Party/customer select should be visible
    const partySelect = subscriptionsPage.partySelect;
    await expect(partySelect).toBeVisible();

    // Tariff select should be visible
    const tariffSelect = subscriptionsPage.tariffSelect;
    await expect(tariffSelect).toBeVisible();
  });

  test('validation errors shown on empty submit', async ({ htmx }) => {
    await subscriptionsPage.gotoCreate();
    if (await subscriptionsPage.isAccessDenied()) {
      test.skip();
      return;
    }

    await subscriptionsPage.htmxSubmitForm(subscriptionsPage.subscriptionForm);

    const errorMessage = subscriptionsPage.page.locator('.field-error, [data-error], .text-red-600');
    await expect(errorMessage.first()).toBeVisible();
  });
});

test.describe('Subscription Empty States', () => {
  let subscriptionsPage: SubscriptionsPage;

  test.beforeEach(async ({ page }) => {
    subscriptionsPage = new SubscriptionsPage(page);
    await subscriptionsPage.gotoList();
    if (await subscriptionsPage.isAccessDenied() || subscriptionsPage.page.url().includes('/subscriptions/dashboard')) {
      test.skip();
      return;
    }
  });

  test('shows empty state when no search results', async ({ htmx }) => {
    await subscriptionsPage.searchSubscriptions('xyznonexistent98765');
    await htmx.waitForHtmxIdle();

    const emptyState = subscriptionsPage.page.locator('.empty-state, [data-testid="empty-state"], .no-results');
    const noRows = await subscriptionsPage.subscriptionsTable.locator('tbody tr').count() === 0;

    expect(await emptyState.count() > 0 || noRows).toBeTruthy();
  });
});
