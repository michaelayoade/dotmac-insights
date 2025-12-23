/**
 * Support Tickets E2E Tests
 *
 * Comprehensive tests for the Support module including:
 * - Ticket list with filters (status, priority)
 * - Create ticket from inbox conversation
 * - Update status and resolution
 * - SLA tracking
 */

import { test, expect, setupAuth, expectAccessDenied } from './fixtures/auth';
import { createTestTicket, createTestContact, deleteTestContact, deleteTestTicket } from './fixtures/api-helpers';

test.describe('Support Tickets - Authenticated', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page, ['support:read', 'support:write']);
  });

  test.describe('Tickets List', () => {
    test('renders tickets list with filters', async ({ page }) => {
      await page.goto('/support/tickets');

      // Verify page structure
      await expect(page.getByRole('heading', { name: /ticket|support/i })).toBeVisible();

      // Verify filter controls
      await expect(page.locator('select, [role="combobox"]').first()).toBeVisible();

      // Verify table/list structure
      await expect(page.locator('table, [role="grid"], [role="list"]').first()).toBeVisible();
    });

    test('filters by status', async ({ page }) => {
      await page.goto('/support/tickets');

      // Find status filter
      const statusFilter = page.locator('select').filter({ hasText: /status|all/i }).first();
      await expect(statusFilter).toBeVisible();
      await statusFilter.selectOption({ label: /open/i });

      // Table should still be visible
      await expect(page.locator('table, [role="grid"]').first()).toBeVisible();
    });

    test('filters by priority', async ({ page }) => {
      await page.goto('/support/tickets');

      // Find priority filter
      const priorityFilter = page.locator('select').filter({ hasText: /priority|all/i }).first();
      await expect(priorityFilter).toBeVisible();
      await priorityFilter.selectOption({ label: /high|urgent/i });

      // Table should still be visible
      await expect(page.locator('table, [role="grid"]').first()).toBeVisible();
    });

    test('displays ticket count and pagination', async ({ page }) => {
      await page.goto('/support/tickets');

      // Wait for data to load
      await page.waitForSelector('table tbody tr, [role="row"]', { timeout: 10000 });

      await expect(page.getByText(/showing|total|results/i).first()).toBeVisible();
      await expect(
        page
          .locator('[aria-label*="page"], button:has-text("Next"), button:has-text("Previous")')
          .first()
      ).toBeVisible();
    });

    test('search filters tickets', async ({ page }) => {
      await page.goto('/support/tickets');

      const searchInput = page.getByPlaceholder(/search/i);
      await expect(searchInput).toBeVisible();
      await searchInput.fill('test');

      // Table should update
      await expect(page.locator('table, [role="grid"]').first()).toBeVisible();
    });

    test('clicking ticket navigates to detail view', async ({ page }) => {
      await page.goto('/support/tickets');

      // Wait for tickets to load
      const ticketRow = page.locator('table tbody tr, [role="row"]').first();
      await ticketRow.waitFor({ timeout: 10000 });

      await expect(ticketRow).toBeVisible();
      await ticketRow.click();
      await page.waitForURL(/\/support\/tickets\/\d+/, { timeout: 5000 });
    });
  });

  test.describe('Ticket Detail', () => {
    test('displays ticket information', async ({ page, request }) => {
      const ticket = await createTestTicket(request, {
        subject: `Detail Test ${Date.now()}`,
        priority: 'high',
      });

      try {
        await page.goto(`/support/tickets/${ticket.id}`);

        await expect(page.getByText(ticket.subject)).toBeVisible();
        await expect(page.getByText(/high/i)).toBeVisible();
      } finally {
        await deleteTestTicket(request, ticket.id);
      }
    });

    test('update status reflects in UI', async ({ page, request }) => {
      const ticket = await createTestTicket(request, {
        subject: `Status Test ${Date.now()}`,
      });

      try {
        await page.goto(`/support/tickets/${ticket.id}`);

        // Find status dropdown or button
        const statusControl = page.locator('select, button').filter({ hasText: /status|open|pending/i }).first();
        await expect(statusControl).toBeVisible();
        await statusControl.click();

        const resolvedOption = page.getByRole('option', { name: /resolved|closed/i }).or(
          page.getByText(/resolved|closed/i)
        );
        await expect(resolvedOption).toBeVisible({ timeout: 2000 });
        await resolvedOption.click();

        await expect(page.getByText(/resolved|closed/i).first()).toBeVisible();
      } finally {
        await deleteTestTicket(request, ticket.id);
      }
    });

    test('add resolution updates ticket', async ({ page, request }) => {
      const ticket = await createTestTicket(request, {
        subject: `Resolution Test ${Date.now()}`,
      });

      try {
        await page.goto(`/support/tickets/${ticket.id}`);

        // Find resolution input
        const resolutionInput = page.getByLabel(/resolution|notes/i).or(
          page.getByPlaceholder(/resolution|notes/i)
        );
        await expect(resolutionInput).toBeVisible();
        await resolutionInput.fill('Issue resolved via E2E test');

        const saveButton = page.getByRole('button', { name: /save|update|submit/i });
        await saveButton.click();

        await expect(page.getByText(/saved|updated|success/i).first()).toBeVisible({ timeout: 5000 });
      } finally {
        await deleteTestTicket(request, ticket.id);
      }
    });
  });

  test.describe('Create Ticket', () => {
    test('create ticket form validates required fields', async ({ page }) => {
      await page.goto('/support/tickets/new');

      const submitButton = page.getByRole('button', { name: /create|save|submit/i });
      await submitButton.click();

      // Should show validation error
      await expect(
        page.getByText(/required|cannot be empty/i).first()
      ).toBeVisible({ timeout: 5000 });
    });

    test('creates ticket successfully', async ({ page, request }) => {
      // Create a contact first for association
      const contact = await createTestContact(request, {
        name: `Ticket Contact ${Date.now()}`,
      });

      try {
        await page.goto('/support/tickets/new');

        const subject = `E2E Test Ticket ${Date.now()}`;
        await page.getByLabel(/subject/i).fill(subject);
        await page.getByLabel(/description/i).fill('Test ticket description');

        // Select priority
        const prioritySelect = page.getByLabel(/priority/i);
        await expect(prioritySelect).toBeVisible();
        await prioritySelect.selectOption({ label: /medium/i });

        await page.getByRole('button', { name: /create|save|submit/i }).click();

        // Should redirect to ticket detail or list
        await page.waitForURL(/\/support\/tickets\/\d+/, { timeout: 10000 });
        await expect(page.getByText(subject)).toBeVisible();

        const createdIdMatch = page.url().match(/\/support\/tickets\/(\d+)/);
        if (createdIdMatch) {
          await deleteTestTicket(request, Number(createdIdMatch[1]));
        }
      } finally {
        await deleteTestContact(request, contact.id);
      }
    });
  });

  test.describe('Inbox Integration', () => {
    test('can create ticket from inbox conversation', async ({ page }) => {
      await page.goto('/inbox');

      // Wait for conversations to load
      await page.waitForSelector('[role="listbox"], [role="list"]', { timeout: 10000 });

      const conversation = page.locator('[role="option"], [role="listitem"]').first();
      await expect(conversation).toBeVisible({ timeout: 5000 });
      await conversation.click();

      const moreButton = page.getByRole('button', { name: /more|actions/i });
      await expect(moreButton).toBeVisible();
      await moreButton.click();

      const createTicketOption = page.getByRole('button', { name: /create.*ticket/i });
      await expect(createTicketOption).toBeVisible({ timeout: 2000 });
      await createTicketOption.click();

      await expect(page.getByText(/ticket created/i)).toBeVisible({ timeout: 5000 });
    });
  });
});

test.describe('Support Settings', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page, ['support:read', 'support:write', 'admin:read', 'admin:write']);
  });

  test('loads settings page with CSAT section', async ({ page }) => {
    await page.goto('/support/settings');

    await expect(page.getByRole('heading', { name: /Support Settings/i })).toBeVisible();
    await expect(page.getByText(/CSAT Survey Settings/i)).toBeVisible();
  });

  test('can update survey trigger settings', async ({ page }) => {
    await page.goto('/support/settings');

    const triggerSelect = page.locator('select').filter({ hasText: /trigger/i }).first();
    await expect(triggerSelect).toBeVisible();
    await triggerSelect.selectOption({ index: 1 });

    const saveButton = page.getByRole('button', { name: /save/i });
    await saveButton.click();

    await expect(page.getByText(/saved|updated|success/i).first()).toBeVisible({ timeout: 5000 });
  });
});

test.describe('Support - RBAC', () => {
  test('user without admin scope cannot access settings', async ({ page }) => {
    await setupAuth(page, ['support:read']);
    await page.goto('/support/settings');

    await expectAccessDenied(page);
  });
});
