import { Page, Locator, expect } from '@playwright/test';
import { BasePage } from './base.page';

/**
 * Page object for Support Tickets module.
 *
 * Handles:
 * - Ticket list with HTMX-powered filtering
 * - Ticket detail view with replies
 * - Ticket creation and updates
 * - Status transitions
 */
export class TicketsPage extends BasePage {
  // URL patterns
  readonly listUrl = '/support/tickets';
  readonly createUrl = '/support/tickets/new';

  // List page elements
  readonly ticketsTable: Locator;
  readonly searchInput: Locator;
  readonly statusFilter: Locator;
  readonly priorityFilter: Locator;
  readonly assigneeFilter: Locator;
  readonly createButton: Locator;
  readonly ticketCards: Locator;

  // Form elements
  readonly ticketForm: Locator;
  readonly subjectInput: Locator;
  readonly descriptionInput: Locator;
  readonly prioritySelect: Locator;
  readonly customerSelect: Locator;
  readonly submitButton: Locator;

  // Detail page elements
  readonly ticketHeader: Locator;
  readonly ticketStatus: Locator;
  readonly ticketPriority: Locator;
  readonly repliesSection: Locator;
  readonly replyForm: Locator;
  readonly replyInput: Locator;
  readonly sendReplyButton: Locator;
  readonly internalNoteToggle: Locator;
  readonly statusDropdown: Locator;
  readonly assignDropdown: Locator;
  readonly slaIndicator: Locator;

  constructor(page: Page) {
    super(page);

    // List page
    this.ticketsTable = page.locator('[data-testid="tickets-table"] table, #tickets-table');
    this.ticketCards = page.locator('.ticket-card, [data-testid="ticket-card"]');
    this.searchInput = page.locator('[data-testid="ticket-search"], input[name="q"]');
    this.statusFilter = page.locator('[data-testid="status-filter"], select[name="status"]');
    this.priorityFilter = page.locator('[data-testid="priority-filter"], select[name="priority"]');
    this.assigneeFilter = page.locator('[data-testid="my-tickets-filter"], select[name="assignee"]');
    this.createButton = page.locator('[data-testid="new-ticket-btn"], a[href*="/new"], button:has-text("New Ticket")');

    // Form
    this.ticketForm = page.locator('[data-testid="ticket-form"], form[action*="/support/tickets"]');
    this.subjectInput = page.locator('input[name="subject"]');
    this.descriptionInput = page.locator('textarea[name="description"]');
    this.prioritySelect = page.locator('select[name="priority"]');
    this.customerSelect = page.locator('select[name="customer_id"], input[name="customer"]');
    this.submitButton = page.locator('button[type="submit"]:has-text("Create")');

    // Detail page
    this.ticketHeader = page.locator('.ticket-header, [data-testid="ticket-header"]');
    this.ticketStatus = page.locator('.ticket-status, [data-testid="status"]');
    this.ticketPriority = page.locator('.ticket-priority, [data-testid="priority"]');
    this.repliesSection = page.locator('#replies, .replies-section');
    this.replyForm = page.locator('form[hx-post*="replies"], form[hx-post*="comments"]');
    this.replyInput = page.locator('textarea[name="message"], textarea[name="comment"]');
    this.sendReplyButton = page.locator('button:has-text("Send"), button:has-text("Reply")');
    this.internalNoteToggle = page.locator('input[name="is_internal"], [data-toggle="internal"]');
    this.statusDropdown = page.locator('[data-status-dropdown], select[name="status"]');
    this.assignDropdown = page.locator('[data-assign-dropdown], select[name="assigned_to"]');
    this.slaIndicator = page.locator('.sla-indicator, [data-sla]');
  }

  // =========================================================================
  // NAVIGATION
  // =========================================================================

  async gotoList(): Promise<void> {
    await this.goto(this.listUrl);
  }

  async gotoCreate(): Promise<void> {
    await this.goto(this.createUrl);
  }

  async gotoTicket(id: number): Promise<void> {
    await this.goto(`${this.listUrl}/${id}`);
  }

  // =========================================================================
  // SEARCH & FILTER
  // =========================================================================

  async searchTickets(query: string): Promise<void> {
    await this.searchInput.fill(query);
    await this.page.waitForTimeout(400);
    await this.waitForHtmxComplete();
  }

  async filterByStatus(status: 'open' | 'replied' | 'on_hold' | 'resolved' | 'closed'): Promise<void> {
    const select = this.page.locator('select[name="status"]');
    if (await select.count() > 0) {
      await select.selectOption(status);
      await this.waitForHtmxComplete();
      return;
    }

    await this.openDropdownAndSelect(this.statusFilter, this.toTitleCase(status));
  }

  async filterByPriority(priority: 'low' | 'medium' | 'high' | 'urgent'): Promise<void> {
    const select = this.page.locator('select[name="priority"]');
    if (await select.count() > 0) {
      await select.selectOption(priority);
      await this.waitForHtmxComplete();
      return;
    }

    await this.openDropdownAndSelect(this.priorityFilter, this.toTitleCase(priority));
  }

  async filterByAssignee(assigneeId: string): Promise<void> {
    const select = this.page.locator('select[name="assignee"]');
    if (await select.count() > 0) {
      await select.selectOption(assigneeId);
      await this.waitForHtmxComplete();
      return;
    }

    const checkbox = this.page.locator('[data-testid="my-tickets-filter"]');
    if (await checkbox.count() > 0 && ['me', 'self'].includes(assigneeId)) {
      await checkbox.check();
      await this.waitForHtmxComplete();
    }
  }

  private toTitleCase(value: string): string {
    return value
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }

  private async openDropdownAndSelect(dropdownButton: Locator, label: string): Promise<void> {
    await dropdownButton.click();
    const container = dropdownButton.locator('..');
    const option = container.locator('a', { hasText: label }).first();
    await this.htmxClick(option);
  }

  // =========================================================================
  // TICKET LIST
  // =========================================================================

  async getTicketCount(): Promise<number> {
    // Support both table and card views
    const tableCount = await this.getTableRowCount(this.ticketsTable);
    if (tableCount > 0) return tableCount;
    return await this.ticketCards.count();
  }

  async getTicketRowBySubject(subject: string): Promise<Locator> {
    return this.ticketsTable.locator(`tbody tr:has-text("${subject}")`);
  }

  async hasTickets(): Promise<boolean> {
    return (await this.ticketsTable.locator('tbody tr').count()) > 0;
  }

  async ensureHasTickets(): Promise<boolean> {
    if (await this.hasTickets()) {
      return true;
    }
    const emptyState = this.page.locator('[data-testid="tickets-empty-state"], [data-testid="empty-state"]');
    if (await emptyState.count() > 0) {
      return false;
    }
    await this.page.waitForTimeout(300);
    return await this.hasTickets();
  }

  async clickTicket(subject: string): Promise<void> {
    const row = await this.getTicketRowBySubject(subject);
    const link = row.locator('a').first();
    await this.htmxClick(link);
  }

  // =========================================================================
  // CREATE TICKET
  // =========================================================================

  async createTicket(data: {
    subject: string;
    description: string;
    priority?: string;
    customer?: string;
  }): Promise<void> {
    await this.gotoCreate();
    await this.subjectInput.fill(data.subject);
    await this.descriptionInput.fill(data.description);
    if (data.priority) await this.prioritySelect.selectOption(data.priority);
    if (data.customer) await this.customerSelect.fill(data.customer);
    await this.htmxSubmitForm(this.ticketForm);
  }

  // =========================================================================
  // TICKET DETAIL
  // =========================================================================

  async addReply(message: string, isInternal: boolean = false): Promise<void> {
    if (isInternal) {
      const toggle = this.internalNoteToggle;
      if (await toggle.count() > 0) {
        await toggle.check();
      }
    }
    await this.replyInput.fill(message);
    await this.htmxClick(this.sendReplyButton);
  }

  async changeStatus(newStatus: string): Promise<void> {
    await this.statusDropdown.selectOption(newStatus);
    await this.waitForHtmxComplete();
  }

  async assignTo(agentId: string): Promise<void> {
    await this.assignDropdown.selectOption(agentId);
    await this.waitForHtmxComplete();
  }

  async resolveTicket(resolution: string): Promise<void> {
    await this.addReply(resolution);
    await this.changeStatus('resolved');
  }

  async closeTicket(): Promise<void> {
    await this.changeStatus('closed');
  }

  async reopenTicket(): Promise<void> {
    await this.changeStatus('open');
  }

  // =========================================================================
  // REPLIES
  // =========================================================================

  async getReplyCount(): Promise<number> {
    return await this.repliesSection.locator('.reply, [data-reply]').count();
  }

  async getLatestReply(): Promise<Locator> {
    return this.repliesSection.locator('.reply, [data-reply]').last();
  }

  async expectReplyContains(text: string): Promise<void> {
    const replies = this.repliesSection.locator('.reply, [data-reply]');
    await expect(replies.filter({ hasText: text })).toBeVisible();
  }

  // =========================================================================
  // SLA
  // =========================================================================

  async getSLAStatus(): Promise<'on_track' | 'at_risk' | 'breached'> {
    const classes = await this.slaIndicator.getAttribute('class') || '';
    if (classes.includes('breached') || classes.includes('red')) return 'breached';
    if (classes.includes('at-risk') || classes.includes('yellow')) return 'at_risk';
    return 'on_track';
  }

  async expectSLAOnTrack(): Promise<void> {
    await expect(this.slaIndicator).toHaveClass(/on-track|green/);
  }

  async expectSLABreached(): Promise<void> {
    await expect(this.slaIndicator).toHaveClass(/breached|red/);
  }

  // =========================================================================
  // ASSERTIONS
  // =========================================================================

  async expectTicketStatus(status: string): Promise<void> {
    await expect(this.ticketStatus).toContainText(status, { ignoreCase: true });
  }

  async expectTicketPriority(priority: string): Promise<void> {
    await expect(this.ticketPriority).toContainText(priority, { ignoreCase: true });
  }

  async expectTicketSubject(subject: string): Promise<void> {
    await expect(this.ticketHeader).toContainText(subject);
  }

  async expectTicketInList(subject: string): Promise<void> {
    const row = await this.getTicketRowBySubject(subject);
    await expect(row).toBeVisible();
  }

  async expectEmptyState(): Promise<void> {
    const emptyState = this.page.locator('.empty-state, [data-testid="tickets-empty-state"], [data-testid="empty-state"]');
    await expect(emptyState).toBeVisible();
  }
}
