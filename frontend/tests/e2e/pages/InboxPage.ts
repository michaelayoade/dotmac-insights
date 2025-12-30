/**
 * Inbox Page Object
 *
 * Page object for inbox/conversations views.
 */

import { type Page, type Locator, expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class InboxPage extends BasePage {
  // Inbox-specific selectors
  readonly conversationList: Locator;
  readonly conversationItems: Locator;
  readonly messageThread: Locator;
  readonly messageInput: Locator;
  readonly sendButton: Locator;
  readonly channelFilter: Locator;
  readonly statusFilter: Locator;
  readonly assigneeFilter: Locator;
  readonly conversationDetails: Locator;
  readonly assignButton: Locator;
  readonly closeButton: Locator;
  readonly snoozeButton: Locator;
  readonly createTicketButton: Locator;
  readonly attachmentButton: Locator;
  readonly emojiButton: Locator;
  readonly cannedResponseButton: Locator;

  constructor(page: Page) {
    super(page);

    this.conversationList = page.locator('[data-testid="conversation-list"]');
    this.conversationItems = page.locator('[data-testid="conversation-item"]');
    this.messageThread = page.locator('[data-testid="message-thread"]');
    this.messageInput = page.locator('[data-testid="message-input"]').or(
      page.getByPlaceholder(/type.*message|reply/i)
    );
    this.sendButton = page.getByRole('button', { name: /send/i });
    this.channelFilter = page.locator('select').filter({ hasText: /channel/i }).first();
    this.statusFilter = page.locator('select').filter({ hasText: /status/i }).first();
    this.assigneeFilter = page.locator('select').filter({ hasText: /assignee|agent/i }).first();
    this.conversationDetails = page.locator('[data-testid="conversation-details"]');
    this.assignButton = page.getByRole('button', { name: /assign/i });
    this.closeButton = page.getByRole('button', { name: /close|resolve/i });
    this.snoozeButton = page.getByRole('button', { name: /snooze/i });
    this.createTicketButton = page.getByRole('button', { name: /create ticket/i });
    this.attachmentButton = page.getByRole('button', { name: /attach/i });
    this.emojiButton = page.getByRole('button', { name: /emoji/i });
    this.cannedResponseButton = page.getByRole('button', { name: /canned|template/i });
  }

  get url(): string {
    return '/inbox';
  }

  /**
   * Navigate to a specific conversation
   */
  async gotoConversation(conversationId: number): Promise<void> {
    await this.page.goto(`/inbox/${conversationId}`);
  }

  /**
   * Wait for inbox to load
   */
  async waitForInbox(timeout = 10000): Promise<void> {
    await this.waitForPageLoad(timeout);
    await this.conversationList.waitFor({ state: 'visible', timeout });
  }

  /**
   * Get count of conversations in list
   */
  async getConversationCount(): Promise<number> {
    return await this.conversationItems.count();
  }

  /**
   * Click a conversation by contact name
   */
  async clickConversation(contactName: string): Promise<void> {
    await this.conversationList.getByText(contactName).first().click();
  }

  /**
   * Filter by channel
   */
  async filterByChannel(channel: string): Promise<void> {
    await this.channelFilter.selectOption({ label: channel });
    await this.page.waitForTimeout(500);
  }

  /**
   * Filter by status
   */
  async filterByStatus(status: string): Promise<void> {
    await this.statusFilter.selectOption({ label: status });
    await this.page.waitForTimeout(500);
  }

  /**
   * Filter by assignee
   */
  async filterByAssignee(assignee: string): Promise<void> {
    await this.assigneeFilter.selectOption({ label: assignee });
    await this.page.waitForTimeout(500);
  }

  /**
   * Send a message in the current conversation
   */
  async sendMessage(message: string): Promise<void> {
    await this.messageInput.fill(message);
    await this.sendButton.click();
    // Wait for message to appear in thread
    await this.page.waitForTimeout(500);
  }

  /**
   * Assign conversation to an agent
   */
  async assignToAgent(agentName: string): Promise<void> {
    await this.assignButton.click();
    await this.page.getByRole('option', { name: new RegExp(agentName, 'i') }).click();
  }

  /**
   * Close/resolve the conversation
   */
  async closeConversation(): Promise<void> {
    await this.closeButton.click();
    await this.confirmModal();
  }

  /**
   * Snooze the conversation
   */
  async snoozeConversation(duration: string): Promise<void> {
    await this.snoozeButton.click();
    await this.page.getByRole('option', { name: new RegExp(duration, 'i') }).click();
  }

  /**
   * Create a ticket from conversation
   */
  async createTicket(data: {
    subject: string;
    priority?: string;
    type?: string;
  }): Promise<void> {
    await this.createTicketButton.click();
    await this.fillField('subject', data.subject);

    if (data.priority) {
      await this.selectDropdown('priority', data.priority);
    }
    if (data.type) {
      await this.selectDropdown('type', data.type);
    }

    await this.submitForm();
  }

  /**
   * Use a canned response
   */
  async useCannedResponse(responseName: string): Promise<void> {
    await this.cannedResponseButton.click();
    await this.page.getByText(responseName).click();
  }

  /**
   * Get message count in thread
   */
  async getMessageCount(): Promise<number> {
    return await this.messageThread.locator('[data-testid="message"]').count();
  }

  /**
   * Verify message exists in thread
   */
  async expectMessageInThread(messageText: string): Promise<void> {
    await expect(this.messageThread.getByText(messageText)).toBeVisible();
  }

  /**
   * Verify conversation status
   */
  async expectConversationStatus(status: string): Promise<void> {
    await expect(this.conversationDetails.getByText(new RegExp(status, 'i'))).toBeVisible();
  }

  /**
   * Verify conversation is assigned to agent
   */
  async expectAssignedTo(agentName: string): Promise<void> {
    await expect(this.conversationDetails.getByText(new RegExp(agentName, 'i'))).toBeVisible();
  }
}

export default InboxPage;
