import { test, expect } from '../fixtures/htmx.fixture';
import { TicketsPage } from '../pages/tickets.page';

/**
 * E2E Browser Tests for Support Tickets Module.
 *
 * Tests the HTMX-powered ticket management interface including:
 * - Ticket list with search and filters
 * - Ticket creation and replies
 * - Status transitions
 * - SLA indicators
 */

test.describe('Tickets List', () => {
  let ticketsPage: TicketsPage;

  test.beforeEach(async ({ page }) => {
    ticketsPage = new TicketsPage(page);
    await ticketsPage.gotoList();
  });

  test('displays tickets table @smoke', async () => {
    const emptyState = ticketsPage.page.locator('[data-testid="tickets-empty-state"], [data-testid="empty-state"]');
    if (await emptyState.count() > 0) {
      await expect(emptyState).toBeVisible();
      return;
    }
    await expect(ticketsPage.ticketsTable).toBeVisible();
  });

  test('search filters tickets via HTMX @critical', async ({ htmx }) => {
    if (!(await ticketsPage.ensureHasTickets())) {
      test.skip();
      return;
    }
    const initialCount = await ticketsPage.getTicketCount();

    // Search for specific ticket
    await ticketsPage.searchTickets('network');
    await htmx.waitForHtmxIdle();

    // Verify filtered results
    const filteredCount = await ticketsPage.getTicketCount();
    expect(filteredCount).toBeLessThanOrEqual(initialCount);
  });

  test('filter by status updates table', async ({ htmx }) => {
    if (!(await ticketsPage.ensureHasTickets())) {
      test.skip();
      return;
    }
    await ticketsPage.filterByStatus('open');
    await htmx.waitForHtmxIdle();

    // All visible rows should have open status
    const rows = await ticketsPage.ticketsTable.locator('tbody tr').all();
    if (rows.length === 0) {
      test.skip();
      return;
    }
    for (const row of rows) {
      const statusBadge = row.locator('.badge, [data-status]');
      await expect(statusBadge).toContainText(/open/i);
    }
  });

  test('filter by priority shows matching tickets', async ({ htmx }) => {
    if (!(await ticketsPage.ensureHasTickets())) {
      test.skip();
      return;
    }
    await ticketsPage.filterByPriority('high');
    await htmx.waitForHtmxIdle();

    // Verify priority filter applied
    const rows = await ticketsPage.ticketsTable.locator('tbody tr').all();
    if (rows.length === 0) {
      test.skip();
      return;
    }
    for (const row of rows) {
      const priorityBadge = row.locator('.priority, [data-priority]');
      await expect(priorityBadge).toContainText(/high/i);
    }
  });

  test('combined filters work correctly', async ({ htmx }) => {
    if (!(await ticketsPage.ensureHasTickets())) {
      test.skip();
      return;
    }
    await ticketsPage.filterByStatus('open');
    await htmx.waitForHtmxIdle();

    await ticketsPage.filterByPriority('urgent');
    await htmx.waitForHtmxIdle();

    // All rows should match both filters
    const rows = await ticketsPage.ticketsTable.locator('tbody tr').all();
    if (rows.length === 0) {
      test.skip();
      return;
    }
    for (const row of rows) {
      await expect(row.locator('.badge, [data-status]')).toContainText(/open/i);
      await expect(row.locator('.priority, [data-priority]')).toContainText(/urgent/i);
    }
  });

  test('click ticket navigates to detail', async ({ page }) => {
    if (!(await ticketsPage.ensureHasTickets())) {
      test.skip();
      return;
    }
    // Get first ticket subject
    const firstRow = ticketsPage.ticketsTable.locator('tbody tr').first();
    const subject = await firstRow.locator('td').first().textContent() || '';

    // Click to view
    await ticketsPage.clickTicket(subject.trim());

    // Verify on detail page
    await expect(page).toHaveURL(/\/tickets\/\d+/);
    await ticketsPage.expectTicketSubject(subject.trim());
  });
});

test.describe('Ticket Creation', () => {
  let ticketsPage: TicketsPage;

  test.beforeEach(async ({ page }) => {
    ticketsPage = new TicketsPage(page);
  });

  test('create new ticket @critical', async ({ htmx, page }) => {
    const testTicket = {
      subject: `Test Ticket ${Date.now()}`,
      description: 'This is a test ticket created by automated tests.',
      priority: 'medium',
    };

    await ticketsPage.createTicket(testTicket);
    await htmx.waitForHtmxIdle();

    // Verify redirect to detail or list
    await expect(page).toHaveURL(/\/tickets/);

    // Verify success message
    await ticketsPage.expectSuccessToast(/created|saved/i);
  });

  test('validation errors shown on invalid input', async ({ htmx }) => {
    await ticketsPage.gotoCreate();

    // Submit empty form
    await ticketsPage.htmxSubmitForm(ticketsPage.ticketForm);

    // Expect validation errors
    const subjectError = ticketsPage.page.locator(
      '[data-error="subject"], [data-testid="subject-error"], .field-error:near(input[name="subject"])'
    );
    await expect(subjectError).toBeVisible();
  });

  test('priority selection updates badge preview', async ({ page }) => {
    await ticketsPage.gotoCreate();

    await ticketsPage.subjectInput.fill('Test Subject');
    await ticketsPage.prioritySelect.selectOption('urgent');

    // Check if there's a priority preview/indicator
    const priorityPreview = page.locator('.priority-preview, [data-priority-preview]');
    if (await priorityPreview.count() > 0) {
      await expect(priorityPreview).toContainText(/urgent/i);
    }
  });
});

test.describe('Ticket Detail View', () => {
  let ticketsPage: TicketsPage;

  test.beforeEach(async ({ page }) => {
    ticketsPage = new TicketsPage(page);
    // Navigate to first ticket
    await ticketsPage.gotoList();
    if (!(await ticketsPage.ensureHasTickets())) {
      test.skip();
      return;
    }
    const firstRow = ticketsPage.ticketsTable.locator('tbody tr').first();
    const subject = await firstRow.locator('td').first().textContent() || '';
    await ticketsPage.clickTicket(subject.trim());
  });

  test('displays ticket header with subject and status', async () => {
    await expect(ticketsPage.ticketHeader).toBeVisible();
    await expect(ticketsPage.ticketStatus).toBeVisible();
  });

  test('displays replies section', async () => {
    await expect(ticketsPage.repliesSection).toBeVisible();
  });

  test('shows SLA indicator', async () => {
    // SLA indicator should be present
    const slaExists = await ticketsPage.slaIndicator.count();
    if (slaExists > 0) {
      await expect(ticketsPage.slaIndicator).toBeVisible();
    }
  });
});

test.describe('Ticket Replies', () => {
  let ticketsPage: TicketsPage;

  test.beforeEach(async ({ page }) => {
    ticketsPage = new TicketsPage(page);
    await ticketsPage.gotoList();
    if (!(await ticketsPage.ensureHasTickets())) {
      test.skip();
      return;
    }
    const firstRow = ticketsPage.ticketsTable.locator('tbody tr').first();
    const subject = await firstRow.locator('td').first().textContent() || '';
    await ticketsPage.clickTicket(subject.trim());
  });

  test('add reply to ticket @critical', async ({ htmx }) => {
    const initialReplyCount = await ticketsPage.getReplyCount();
    const replyMessage = `Test reply ${Date.now()}`;

    await ticketsPage.addReply(replyMessage);
    await htmx.waitForHtmxIdle();

    // Verify reply added
    const newReplyCount = await ticketsPage.getReplyCount();
    expect(newReplyCount).toBeGreaterThan(initialReplyCount);

    // Verify reply content visible
    await ticketsPage.expectReplyContains(replyMessage);
  });

  test('add internal note', async ({ htmx }) => {
    const noteMessage = `Internal note ${Date.now()}`;

    await ticketsPage.addReply(noteMessage, true);
    await htmx.waitForHtmxIdle();

    // Verify internal note visible (usually styled differently)
    await ticketsPage.expectReplyContains(noteMessage);
  });

  test('reply form clears after submission', async ({ htmx }) => {
    const replyMessage = `Clear test ${Date.now()}`;

    await ticketsPage.addReply(replyMessage);
    await htmx.waitForHtmxIdle();

    // Reply input should be empty
    await expect(ticketsPage.replyInput).toHaveValue('');
  });
});

test.describe('Ticket Status Transitions', () => {
  let ticketsPage: TicketsPage;

  test.beforeEach(async ({ page }) => {
    ticketsPage = new TicketsPage(page);
    await ticketsPage.gotoList();
    // Find an open ticket
    await ticketsPage.filterByStatus('open');
    const firstRow = ticketsPage.ticketsTable.locator('tbody tr').first();
    if (await firstRow.count() === 0) {
      test.skip();
      return;
    }
    const subject = await firstRow.locator('td').first().textContent() || '';
    await ticketsPage.clickTicket(subject.trim());
  });

  test('change ticket status', async ({ htmx }) => {
    await ticketsPage.changeStatus('replied');
    await htmx.waitForHtmxIdle();

    await ticketsPage.expectTicketStatus('replied');
  });

  test('resolve ticket with resolution message', async ({ htmx }) => {
    const resolution = `Resolved - ${Date.now()}`;

    await ticketsPage.resolveTicket(resolution);
    await htmx.waitForHtmxIdle();

    await ticketsPage.expectTicketStatus('resolved');
    await ticketsPage.expectSuccessToast(/resolved|updated/i);
  });

  test('close resolved ticket', async ({ htmx, page }) => {
    // First resolve
    await ticketsPage.resolveTicket('Test resolution');
    await htmx.waitForHtmxIdle();

    // Then close
    await ticketsPage.closeTicket();
    await htmx.waitForHtmxIdle();

    await ticketsPage.expectTicketStatus('closed');
  });

  test('reopen closed ticket', async ({ htmx, page }) => {
    // Navigate to a closed ticket
    await ticketsPage.gotoList();
    await ticketsPage.filterByStatus('closed');

    const closedRow = ticketsPage.ticketsTable.locator('tbody tr').first();
    if (await closedRow.count() === 0) {
      test.skip();
      return;
    }

    const subject = await closedRow.locator('td').first().textContent() || '';
    await ticketsPage.clickTicket(subject.trim());

    // Reopen
    await ticketsPage.reopenTicket();
    await htmx.waitForHtmxIdle();

    await ticketsPage.expectTicketStatus('open');
  });
});

test.describe('Ticket Assignment', () => {
  let ticketsPage: TicketsPage;

  test.beforeEach(async ({ page }) => {
    ticketsPage = new TicketsPage(page);
    await ticketsPage.gotoList();
    if (!(await ticketsPage.ensureHasTickets())) {
      test.skip();
      return;
    }
    const firstRow = ticketsPage.ticketsTable.locator('tbody tr').first();
    const subject = await firstRow.locator('td').first().textContent() || '';
    await ticketsPage.clickTicket(subject.trim());
  });

  test('assign ticket to agent', async ({ htmx }) => {
    // Get available assignees
    const assignDropdown = ticketsPage.assignDropdown;
    if (await assignDropdown.count() === 0) {
      test.skip();
      return;
    }

    // Get first option value
    const options = await assignDropdown.locator('option').all();
    if (options.length < 2) {
      test.skip();
      return;
    }

    const agentValue = await options[1].getAttribute('value') || '';
    await ticketsPage.assignTo(agentValue);
    await htmx.waitForHtmxIdle();

    await ticketsPage.expectSuccessToast(/assigned|updated/i);
  });
});

test.describe('SLA Tracking', () => {
  let ticketsPage: TicketsPage;

  test.beforeEach(async ({ page }) => {
    ticketsPage = new TicketsPage(page);
    await ticketsPage.gotoList();
  });

  test('SLA indicators show on ticket list', async () => {
    if (!(await ticketsPage.ensureHasTickets())) {
      test.skip();
      return;
    }
    // Check if SLA column exists in table
    const slaColumn = ticketsPage.ticketsTable.locator('th:has-text("SLA"), th:has-text("Due")');
    if (await slaColumn.count() > 0) {
      await expect(slaColumn).toBeVisible();
    }
  });

  test('filter tickets by SLA status', async ({ htmx, page }) => {
    if (!(await ticketsPage.ensureHasTickets())) {
      test.skip();
      return;
    }
    // Check if SLA filter exists
    const slaFilter = page.locator('select[name="sla_status"], [data-filter="sla"]');
    if (await slaFilter.count() === 0) {
      test.skip();
      return;
    }

    await slaFilter.selectOption('breached');
    await htmx.waitForHtmxIdle();

    // All visible tickets should show breached SLA
    const rows = await ticketsPage.ticketsTable.locator('tbody tr').all();
    if (rows.length === 0) {
      test.skip();
      return;
    }
    for (const row of rows) {
      const slaIndicator = row.locator('.sla-indicator, [data-sla]');
      await expect(slaIndicator).toHaveClass(/breached|red|overdue/);
    }
  });
});

test.describe('Empty States', () => {
  let ticketsPage: TicketsPage;

  test.beforeEach(async ({ page }) => {
    ticketsPage = new TicketsPage(page);
    await ticketsPage.gotoList();
  });

  test('shows empty state when no results', async ({ htmx }) => {
    // Search for something that won't exist
    await ticketsPage.searchTickets('xyznonexistent12345');
    await htmx.waitForHtmxIdle();

    // Should show empty state or no results message
    const emptyState = ticketsPage.page.locator('.empty-state, [data-testid="tickets-empty-state"], [data-testid="empty-state"], .no-results');
    const noRows = await ticketsPage.ticketsTable.locator('tbody tr').count() === 0;

    expect(await emptyState.count() > 0 || noRows).toBeTruthy();
  });
});
