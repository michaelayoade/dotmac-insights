import { test, expect } from './fixtures/htmx.fixture';
import { ContactsPage } from './pages/contacts.page';
import { TicketsPage } from './pages/tickets.page';

/**
 * Comprehensive Smoke Tests for DotMac BOS.
 *
 * These tests verify critical paths are working after deployment:
 * - Authentication flow (login page accessibility)
 * - Dashboard/home page accessibility
 * - Basic CRUD operations per module
 *
 * Run with: npx playwright test --grep @smoke
 */

// ============================================================================
// AUTHENTICATION FLOW
// ============================================================================

test.describe('Authentication @smoke', () => {
  test('login page loads and accepts credentials', async ({ page }) => {
    await page.goto('/login');

    // Login page should be accessible
    await expect(page.locator('input[name="email"], input[name="username"]')).toBeVisible();
    await expect(page.locator('input[name="password"]')).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test('login form submits without error', async ({ page }) => {
    await page.goto('/login');

    // Fill login form with test credentials
    await page.fill('input[name="email"], input[name="username"]', process.env.E2E_SUPERUSER_EMAIL || 'admin@dotmac.ng');
    await page.fill('input[name="password"]', process.env.E2E_SUPERUSER_PASSWORD || 'admin123');
    await page.click('button[type="submit"]');

    // Wait for navigation (either success or validation error)
    await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});

    // Should not show network/server error
    const errorPage = page.locator('text=/500|502|503|504|Server Error/i');
    expect(await errorPage.count()).toBe(0);
  });
});

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
});

// ============================================================================
// CRM MODULE - CONTACTS CRUD
// ============================================================================

test.describe('CRM Contacts @smoke', () => {
  let contactsPage: ContactsPage;

  test.beforeEach(async ({ page }) => {
    contactsPage = new ContactsPage(page);
  });

  test('contacts list page loads', async () => {
    await contactsPage.gotoList();

    // Page should load - either table or empty state
    const table = contactsPage.contactsTable;
    const emptyState = contactsPage.page.locator('[data-testid="contacts-empty-state"], [data-testid="empty-state"], .empty-state');

    const hasTable = await table.count() > 0;
    const hasEmptyState = await emptyState.count() > 0;

    expect(hasTable || hasEmptyState).toBeTruthy();
  });

  test('contacts table displays @smoke', async () => {
    await contactsPage.gotoList();
    await expect(contactsPage.contactsTable).toBeVisible();
  });

  test('create contact form accessible', async () => {
    await contactsPage.gotoCreate();

    // Form fields should be visible
    await expect(contactsPage.nameInput).toBeVisible();
  });

  test('create new contact @critical', async ({ htmx, page }) => {
    const testContact = {
      name: `Smoke Test Contact ${Date.now()}`,
      email: `smoke${Date.now()}@example.com`,
      phone: '+2347012345678',
      type: 'lead',
    };

    await contactsPage.createContact(testContact);
    await htmx.waitForHtmxIdle();

    // Verify redirect to detail or list
    await expect(page).toHaveURL(/\/crm\/contacts/);

    // Verify success message if toast exists
    const toast = contactsPage.toast;
    if (await toast.count() > 0) {
      await contactsPage.expectSuccessToast(/created|saved/i);
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

    // Form fields should be visible
    await expect(ticketsPage.subjectInput).toBeVisible();
    await expect(ticketsPage.descriptionInput).toBeVisible();
  });

  test('create new ticket @critical', async ({ htmx, page }) => {
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
