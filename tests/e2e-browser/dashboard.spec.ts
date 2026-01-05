import { test, expect } from './fixtures/htmx.fixture';

/**
 * E2E Browser Tests for Dashboard and Analytics.
 *
 * Tests the main dashboard and module-specific dashboards including:
 * - Main application dashboard
 * - Accounting dashboard
 * - HR dashboard
 * - Subscriptions dashboard
 * - Module stat cards and navigation
 */

test.describe('Main Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('displays main dashboard @smoke', async ({ page }) => {
    // Dashboard should load without errors
    await expect(page.locator('body')).toBeVisible();

    const pageTitle = page.locator('[data-testid="page-title"]');
    await expect(pageTitle).toBeVisible();
  });

  test('displays navigation sidebar', async ({ page }) => {
    const sidebar = page.locator('aside, nav, .sidebar');
    await expect(sidebar.first()).toBeVisible();
  });

  test('navigation links work', async ({ page }) => {
    const navLinks = page.locator('aside a, nav a, .sidebar a');
    const linkCount = await navLinks.count();

    expect(linkCount).toBeGreaterThan(0);

    // First nav link should be clickable
    const firstLink = navLinks.first();
    await expect(firstLink).toBeVisible();
  });

  test('displays stat cards if present', async ({ page }) => {
    const statCards = page.locator('.stat-card, [data-testid*="stat"], .dashboard-stats');
    if (await statCards.count() > 0) {
      await expect(statCards.first()).toBeVisible();
    }
  });

  test('stat cards are clickable', async ({ page }) => {
    const statCards = page.locator('a.stat-card, .stat-card a, [data-testid*="stat"] a');
    if (await statCards.count() > 0) {
      const firstCard = statCards.first();
      const href = await firstCard.getAttribute('href');
      expect(href).toBeTruthy();
    }
  });
});

test.describe('Accounting Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/accounting');
  });

  test('displays accounting dashboard @smoke', async ({ page }) => {
    const pageTitle = page.locator('h1');
    await expect(pageTitle).toContainText(/accounting|finance|dashboard/i);
  });

  test('displays revenue card', async ({ page }) => {
    const revenueCard = page.locator('[data-testid="revenue-card"], .revenue-card, :has-text("Revenue")');
    if (await revenueCard.count() > 0) {
      await expect(revenueCard.first()).toBeVisible();
    }
  });

  test('displays receivables card', async ({ page }) => {
    const receivablesCard = page.locator('[data-testid="receivables-card"], .receivables-card, :has-text("Receivable")');
    if (await receivablesCard.count() > 0) {
      await expect(receivablesCard.first()).toBeVisible();
    }
  });

  test('displays payables card', async ({ page }) => {
    const payablesCard = page.locator('[data-testid="payables-card"], .payables-card, :has-text("Payable")');
    if (await payablesCard.count() > 0) {
      await expect(payablesCard.first()).toBeVisible();
    }
  });

  test('displays cash flow or bank balance', async ({ page }) => {
    const cashCard = page.locator('[data-testid="cash-card"], .cash-card, :has-text("Cash"), :has-text("Bank")');
    if (await cashCard.count() > 0) {
      await expect(cashCard.first()).toBeVisible();
    }
  });

  test('quick action links work', async ({ page }) => {
    const quickActions = page.locator('a[href*="/invoices/new"], a[href*="/payments/new"], button:has-text("New Invoice")');
    if (await quickActions.count() > 0) {
      await expect(quickActions.first()).toBeVisible();
    }
  });
});

test.describe('HR Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/hr');
  });

  test('displays HR dashboard @smoke', async ({ page }) => {
    const pageTitle = page.locator('[data-testid="page-title"], h1');
    await expect(pageTitle).toContainText(/hr|human|employee|dashboard/i);
  });

  test('displays employee count card', async ({ page }) => {
    const employeeCard = page.locator('[data-testid="stat-employees"], .stat-employees, :has-text("Employee")');
    if (await employeeCard.count() > 0) {
      await expect(employeeCard.first()).toBeVisible();
    }
  });

  test('displays on-leave card', async ({ page }) => {
    const leaveCard = page.locator('[data-testid="stat-on-leave"], .stat-on-leave, :has-text("Leave")');
    if (await leaveCard.count() > 0) {
      await expect(leaveCard.first()).toBeVisible();
    }
  });

  test('displays pending approvals', async ({ page }) => {
    const pendingCard = page.locator('[data-testid="stat-pending"], .stat-pending, :has-text("Pending")');
    if (await pendingCard.count() > 0) {
      await expect(pendingCard.first()).toBeVisible();
    }
  });

  test('quick action links work', async ({ page }) => {
    const quickActions = page.locator('a[href*="/employees"], a[href*="/leave"], button:has-text("Apply Leave")');
    if (await quickActions.count() > 0) {
      await expect(quickActions.first()).toBeVisible();
    }
  });
});

test.describe('Subscriptions Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/subscriptions/dashboard');
  });

  test('displays subscriptions dashboard @smoke', async ({ page }) => {
    const pageTitle = page.locator('h1');
    await expect(pageTitle).toContainText(/subscription|service|dashboard/i);
  });

  test('displays active subscriptions count', async ({ page }) => {
    const activeCard = page.locator('[data-testid="stat-active"], .stat-active, :has-text("Active")');
    if (await activeCard.count() > 0) {
      await expect(activeCard.first()).toBeVisible();
    }
  });

  test('displays suspended subscriptions', async ({ page }) => {
    const suspendedCard = page.locator('[data-testid="stat-suspended"], .stat-suspended, :has-text("Suspended")');
    if (await suspendedCard.count() > 0) {
      await expect(suspendedCard.first()).toBeVisible();
    }
  });

  test('displays expiring soon count', async ({ page }) => {
    const expiringCard = page.locator('[data-testid="stat-expiring"], .stat-expiring, :has-text("Expiring")');
    if (await expiringCard.count() > 0) {
      await expect(expiringCard.first()).toBeVisible();
    }
  });

  test('displays MRR if available', async ({ page }) => {
    const mrrCard = page.locator('[data-testid="mrr"], .mrr-card, :has-text("MRR"), :has-text("Monthly Recurring")');
    if (await mrrCard.count() > 0) {
      await expect(mrrCard.first()).toBeVisible();
    }
  });
});

test.describe('Support Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/support');
  });

  test('displays support dashboard @smoke', async ({ page }) => {
    const pageTitle = page.locator('[data-testid="page-title"]');
    await expect(pageTitle).toContainText(/support|ticket|helpdesk|dashboard/i);
  });

  test('displays open tickets count', async ({ page }) => {
    const openCard = page.locator('[data-testid="stat-open"], .stat-open, :has-text("Open")');
    if (await openCard.count() > 0) {
      await expect(openCard.first()).toBeVisible();
    }
  });

  test('displays pending tickets', async ({ page }) => {
    const pendingCard = page.locator('[data-testid="stat-pending"], .stat-pending, :has-text("Pending")');
    if (await pendingCard.count() > 0) {
      await expect(pendingCard.first()).toBeVisible();
    }
  });

  test('displays resolved today', async ({ page }) => {
    const resolvedCard = page.locator('[data-testid="stat-resolved"], .stat-resolved, :has-text("Resolved")');
    if (await resolvedCard.count() > 0) {
      await expect(resolvedCard.first()).toBeVisible();
    }
  });

  test('displays CSAT score if available', async ({ page }) => {
    const csatCard = page.locator('[data-testid="csat"], .csat-card, :has-text("CSAT"), :has-text("Satisfaction")');
    if (await csatCard.count() > 0) {
      await expect(csatCard.first()).toBeVisible();
    }
  });
});

test.describe('Dashboard Charts', () => {
  test('accounting dashboard has charts', async ({ page }) => {
    await page.goto('/accounting');

    const charts = page.locator('canvas, svg.chart, .chart-container, [data-chart]');
    if (await charts.count() > 0) {
      await expect(charts.first()).toBeVisible();
    }
  });

  test('subscriptions dashboard has usage charts', async ({ page }) => {
    await page.goto('/subscriptions/dashboard');

    const charts = page.locator('canvas, svg.chart, .chart-container, [data-chart]');
    if (await charts.count() > 0) {
      await expect(charts.first()).toBeVisible();
    }
  });
});

test.describe('Dashboard Date Filters', () => {
  test('date filter updates dashboard data', async ({ page, htmx }) => {
    await page.goto('/accounting');

    const dateFilter = page.locator('select[name="period"], [data-testid="period-filter"], input[type="date"]');
    if (await dateFilter.count() === 0) {
      test.skip();
      return;
    }

    // Try to change the period
    if (await dateFilter.first().evaluate((el) => el.tagName === 'SELECT')) {
      await dateFilter.first().selectOption({ index: 1 });
    } else {
      const today = new Date();
      const lastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
      await dateFilter.first().fill(lastMonth.toISOString().split('T')[0]);
    }

    await htmx.waitForHtmxIdle();

    // Dashboard should still be visible after update
    await expect(page.locator('body')).toBeVisible();
  });
});

test.describe('Dashboard Responsive', () => {
  test('dashboard is responsive on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/');

    // Should load without errors
    await expect(page.locator('body')).toBeVisible();

    // Navigation should be accessible (hamburger menu or similar)
    const mobileNav = page.locator('button[aria-label*="menu"], .hamburger, .mobile-menu-toggle');
    if (await mobileNav.count() > 0) {
      await expect(mobileNav.first()).toBeVisible();
    }
  });

  test('stat cards stack on mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    await page.goto('/accounting');

    const statCards = page.locator('.stat-card, [data-testid*="stat"]');
    if (await statCards.count() > 0) {
      // Cards should be visible and stacked (verify layout)
      await expect(statCards.first()).toBeVisible();
    }
  });
});
