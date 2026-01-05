import { test, expect } from './fixtures/htmx.fixture';
import { TicketsPage } from './pages/tickets.page';

/**
 * Comprehensive Smoke Tests for DotMac BOS.
 *
 * These tests verify critical paths are working after deployment:
 * - Dashboard/home page accessibility
 * - Parties (CRM) module
 * - Support tickets module
 * - Application health
 *
 * Run with: npx playwright test --grep @smoke
 */

// ============================================================================
// DASHBOARD / HOME PAGE
// ============================================================================

test.describe('Dashboard @smoke', () => {
  test('home page loads successfully', async ({ page }) => {
    await page.goto('/');

    // Page should load without errors
    await expect(page.locator('body')).toBeVisible();

    // No server errors
    const errorPage = page.locator('text=/500|502|503|504|Server Error/i');
    expect(await errorPage.count()).toBe(0);
  });

  test('navigation elements visible', async ({ page }) => {
    await page.goto('/');

    // Should have some navigation
    const nav = page.locator('nav, aside, .sidebar, header');
    await expect(nav.first()).toBeVisible();
  });

  test('authenticated user sees dashboard content', async ({ page }) => {
    await page.goto('/');

    // Should not be on login page (auth working)
    const url = page.url();
    expect(url).not.toContain('/login');

    // Should see some dashboard content
    const content = page.locator('main, .content, [role="main"]');
    await expect(content.first()).toBeVisible();
  });
});

// ============================================================================
// PARTIES MODULE (CRM)
// ============================================================================

test.describe('Parties @smoke', () => {
  test('parties list page loads', async ({ page }) => {
    await page.goto('/parties');

    // Page should load - either table or empty state
    const table = page.locator('table, [data-testid="parties-table"]');
    const emptyState = page.locator('[data-testid="empty-state"], .empty-state');

    const hasTable = await table.count() > 0;
    const hasEmptyState = await emptyState.count() > 0;

    // Either table or empty state should be visible
    expect(hasTable || hasEmptyState).toBeTruthy();
  });

  test('parties table displays @smoke', async ({ page }) => {
    await page.goto('/parties');

    const emptyState = page.locator('[data-testid="empty-state"], .empty-state');
    if (await emptyState.count() > 0) {
      await expect(emptyState).toBeVisible();
      return;
    }

    const table = page.locator('table');
    await expect(table.first()).toBeVisible();
  });

  test('party detail page accessible', async ({ page }) => {
    await page.goto('/parties');

    // Try to click on first party if table has data
    const firstRow = page.locator('table tbody tr').first();
    if (await firstRow.count() > 0) {
      const link = firstRow.locator('a').first();
      if (await link.count() > 0) {
        await link.click();
        await expect(page).toHaveURL(/\/parties\/\d+/);
      }
    }
  });
});

// ============================================================================
// SUPPORT MODULE - TICKETS CRUD
// ============================================================================

test.describe('Support Tickets @smoke', () => {
  let ticketsPage: TicketsPage;

  test.beforeEach(async ({ page }) => {
    ticketsPage = new TicketsPage(page);
  });

  test('tickets list page loads', async () => {
    await ticketsPage.gotoList();

    // Page should load - either table or empty state
    const table = ticketsPage.ticketsTable;
    const emptyState = ticketsPage.page.locator('[data-testid="tickets-empty-state"], [data-testid="empty-state"], .empty-state');

    const hasTable = await table.count() > 0;
    const hasEmptyState = await emptyState.count() > 0;

    expect(hasTable || hasEmptyState).toBeTruthy();
  });

  test('tickets table displays @smoke', async () => {
    await ticketsPage.gotoList();
    const emptyState = ticketsPage.page.locator('[data-testid="tickets-empty-state"], [data-testid="empty-state"]');
    if (await emptyState.count() > 0) {
      await expect(emptyState).toBeVisible();
      return;
    }
    await expect(ticketsPage.ticketsTable).toBeVisible();
  });

  test('create ticket form accessible', async () => {
    await ticketsPage.gotoCreate();
    if (await ticketsPage.isAccessDenied()) {
      test.skip();
      return;
    }

    // Form fields should be visible
    await expect(ticketsPage.subjectInput).toBeVisible();
    await expect(ticketsPage.descriptionInput).toBeVisible();
  });

  test('create new ticket @critical', async ({ htmx, page }) => {
    await ticketsPage.gotoCreate();
    if (await ticketsPage.isAccessDenied()) {
      test.skip();
      return;
    }

    const testTicket = {
      subject: `Smoke Test Ticket ${Date.now()}`,
      description: 'This is a smoke test ticket created by automated tests.',
      priority: 'medium',
    };

    await ticketsPage.createTicket(testTicket);
    await htmx.waitForHtmxIdle();

    // Verify redirect to detail or list
    await expect(page).toHaveURL(/\/support\/tickets/);

    // Verify success message if toast exists
    const toast = ticketsPage.toast;
    if (await toast.count() > 0) {
      await ticketsPage.expectSuccessToast(/created|saved/i);
    }
  });
});

// ============================================================================
// HEALTH CHECK
// ============================================================================

test.describe('Application Health @smoke', () => {
  test('health endpoint responds', async ({ page }) => {
    const response = await page.goto('/health');
    expect(response?.status()).toBe(200);
  });

  test('API health check', async ({ request }) => {
    const response = await request.get('/health');
    expect(response.status()).toBe(200);
  });

  test('no console errors on page load', async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto('/');

    // Allow for some known errors, but fail on critical ones
    const criticalErrors = consoleErrors.filter(
      (err) => !err.includes('favicon') && !err.includes('404')
    );

    expect(criticalErrors).toHaveLength(0);
  });
});

// ============================================================================
// MODULE ACCESSIBILITY
// ============================================================================

test.describe('Module Access @smoke', () => {
  const modules = [
    { name: 'Accounting', path: '/accounting' },
    { name: 'HR', path: '/hr' },
    { name: 'Subscriptions', path: '/subscriptions' },
    { name: 'Projects', path: '/projects' },
    { name: 'Support', path: '/support' },
  ];

  for (const mod of modules) {
    test(`${mod.name} module loads`, async ({ page }) => {
      await page.goto(mod.path);

      // Should not be redirected to login
      expect(page.url()).not.toContain('/login');

      // Should not show server error
      const errorPage = page.locator('text=/500|502|503|504|Server Error/i');
      expect(await errorPage.count()).toBe(0);

      // Page body should be visible
      await expect(page.locator('body')).toBeVisible();
    });
  }
});
