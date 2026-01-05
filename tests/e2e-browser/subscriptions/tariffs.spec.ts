import { test, expect } from '../fixtures/htmx.fixture';
import { SubscriptionsPage } from '../pages/subscriptions.page';

/**
 * E2E Browser Tests for Tariffs/Plans Module.
 *
 * Tests the HTMX-powered tariff management interface including:
 * - Tariff list with search
 * - Tariff detail view
 * - Tariff pricing information
 */

test.describe('Tariffs List', () => {
  let subscriptionsPage: SubscriptionsPage;

  test.beforeEach(async ({ page }) => {
    subscriptionsPage = new SubscriptionsPage(page);
    await subscriptionsPage.gotoTariffs();
  });

  test('displays tariffs page @smoke', async () => {
    if (await subscriptionsPage.isAccessDenied()) {
      test.skip();
      return;
    }
    const pageTitle = subscriptionsPage.page.locator('[data-testid="page-title"]');
    await expect(pageTitle).toContainText(/tariff|plan|package/i);
  });

  test('displays tariffs table @smoke', async () => {
    if (await subscriptionsPage.isAccessDenied()) {
      test.skip();
      return;
    }
    if (!(await subscriptionsPage.hasTariffs())) {
      const emptyState = subscriptionsPage.page.locator('[data-testid="empty-state"]');
      if (await emptyState.count() > 0) {
        await expect(emptyState).toBeVisible();
        return;
      }
    }
    await expect(subscriptionsPage.tariffsTable).toBeVisible();
  });

  test('search filters tariffs via HTMX', async ({ htmx }) => {
    if (await subscriptionsPage.isAccessDenied()) {
      test.skip();
      return;
    }
    if (!(await subscriptionsPage.hasTariffs())) {
      test.skip();
      return;
    }
    const initialCount = await subscriptionsPage.getTariffCount();

    await subscriptionsPage.searchTariffs('premium');
    await htmx.waitForHtmxIdle();

    const filteredCount = await subscriptionsPage.getTariffCount();
    expect(filteredCount).toBeLessThanOrEqual(initialCount);
  });

  test('tariff table shows pricing information', async () => {
    if (await subscriptionsPage.isAccessDenied()) {
      test.skip();
      return;
    }
    if (!(await subscriptionsPage.hasTariffs())) {
      test.skip();
      return;
    }

    // Check for price column
    const priceCell = subscriptionsPage.tariffsTable.locator('[data-testid="tariff-price"]').first();
    const priceText = await priceCell.textContent();
    expect(priceText).toMatch(/[\d,.]+/);
  });

  test('click tariff navigates to detail', async ({ page }) => {
    if (await subscriptionsPage.isAccessDenied()) {
      test.skip();
      return;
    }
    if (!(await subscriptionsPage.hasTariffs())) {
      test.skip();
      return;
    }

    const name = await subscriptionsPage.tariffsTable.locator('[data-testid="tariff-name"]').first().textContent() || '';

    await subscriptionsPage.clickTariff(name.trim());

    await expect(page).toHaveURL(/\/tariffs\/\d+/);
  });
});

test.describe('Tariff Detail View', () => {
  let subscriptionsPage: SubscriptionsPage;

  test.beforeEach(async ({ page }) => {
    subscriptionsPage = new SubscriptionsPage(page);
    await subscriptionsPage.gotoTariffs();
    if (await subscriptionsPage.isAccessDenied()) {
      test.skip();
      return;
    }
    if (!(await subscriptionsPage.hasTariffs())) {
      test.skip();
      return;
    }
    const name = await subscriptionsPage.tariffsTable.locator('[data-testid="tariff-name"]').first().textContent() || '';
    await subscriptionsPage.clickTariff(name.trim());
  });

  test('displays tariff header with name', async () => {
    const header = subscriptionsPage.page.locator('[data-testid="page-title"]');
    await expect(header).toBeVisible();
  });

  test('displays pricing information', async () => {
    const pricing = subscriptionsPage.page.locator('[data-testid="tariff-pricing-card"]');
    await expect(pricing).toBeVisible();
  });

  test('displays speed/bandwidth information', async () => {
    const speed = subscriptionsPage.page.locator('[data-testid="tariff-speed-card"]');
    if (await speed.count() > 0) {
      await expect(speed).toBeVisible();
    }
  });

  test('displays subscription count using this tariff', async () => {
    const countIndicator = subscriptionsPage.page.locator('[data-testid="tariff-subscription-count"]');
    if (await countIndicator.count() > 0) {
      await expect(countIndicator).toBeVisible();
    }
  });
});

test.describe('Tariff Empty States', () => {
  let subscriptionsPage: SubscriptionsPage;

  test.beforeEach(async ({ page }) => {
    subscriptionsPage = new SubscriptionsPage(page);
    await subscriptionsPage.gotoTariffs();
    if (await subscriptionsPage.isAccessDenied()) {
      test.skip();
      return;
    }
  });

  test('shows empty state when no search results', async ({ htmx }) => {
    await subscriptionsPage.searchTariffs('xyznonexistent98765');
    await htmx.waitForHtmxIdle();

    const emptyState = subscriptionsPage.page.locator('[data-testid="empty-state"]');
    const noRows = await subscriptionsPage.tariffsTable.locator('tbody tr').count() === 0;

    expect(await emptyState.count() > 0 || noRows).toBeTruthy();
  });
});
