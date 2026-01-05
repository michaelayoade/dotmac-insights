import { Page, Locator, expect } from '@playwright/test';
import { BasePage } from './base.page';

/**
 * Page object for Subscriptions module.
 *
 * Handles:
 * - Subscription list with search and filters
 * - Subscription detail with tabs (billing, usage, sessions, etc.)
 * - Tariff/Plan management
 * - Provisioning status
 */
export class SubscriptionsPage extends BasePage {
  // URL patterns
  readonly listUrl = '/subscriptions';
  readonly dashboardUrl = '/subscriptions/dashboard';
  readonly tariffsUrl = '/subscriptions/tariffs';
  readonly createUrl = '/subscriptions/new';

  // List page elements
  readonly subscriptionsTable: Locator;
  readonly subscriptionSearch: Locator;
  readonly statusFilter: Locator;
  readonly statusFilterButton: Locator;
  readonly tariffFilter: Locator;
  readonly newSubscriptionButton: Locator;

  // Stats elements
  readonly statActive: Locator;
  readonly statSuspended: Locator;
  readonly statExpiring: Locator;
  readonly statTotal: Locator;

  // Subscription form elements
  readonly subscriptionForm: Locator;
  readonly partySelect: Locator;
  readonly tariffSelect: Locator;
  readonly startDateInput: Locator;
  readonly usernameInput: Locator;
  readonly passwordInput: Locator;
  readonly ipAddressInput: Locator;
  readonly routerSelect: Locator;

  // Subscription detail elements
  readonly subscriptionHeader: Locator;
  readonly subscriptionStatus: Locator;
  readonly subscriptionTariff: Locator;
  readonly subscriptionParty: Locator;

  // Detail tabs
  readonly tabBilling: Locator;
  readonly tabUsage: Locator;
  readonly tabSessions: Locator;
  readonly tabProvisioning: Locator;
  readonly tabSettings: Locator;

  // Action buttons
  readonly renewButton: Locator;
  readonly suspendButton: Locator;
  readonly activateButton: Locator;
  readonly provisionButton: Locator;
  readonly changePlanButton: Locator;

  // Tariffs page elements
  readonly tariffsTable: Locator;
  readonly tariffSearch: Locator;
  readonly newTariffButton: Locator;

  constructor(page: Page) {
    super(page);

    // List page
    this.subscriptionsTable = page.locator('[data-testid="subscriptions-table"] table');
    this.subscriptionSearch = page.locator('[data-testid="subscription-search"]');
    this.statusFilter = page.locator('[data-testid="status-filter"]');
    this.statusFilterButton = page.locator('[data-testid="status-filter-button"]');
    this.tariffFilter = page.locator('[data-testid="tariff-filter"]');
    this.newSubscriptionButton = page.locator('[data-testid="new-subscription"]');

    // Stats
    this.statActive = page.locator('[data-testid="stat-active"], .stat-active');
    this.statSuspended = page.locator('[data-testid="stat-suspended"], .stat-suspended');
    this.statExpiring = page.locator('[data-testid="stat-expiring"], .stat-expiring');
    this.statTotal = page.locator('[data-testid="stat-total"], .stat-total');

    // Form
    this.subscriptionForm = page.locator('[data-testid="subscription-form"]');
    this.partySelect = page.locator('[data-testid="party-select"]');
    this.tariffSelect = page.locator('[data-testid="tariff-select"]');
    this.startDateInput = page.locator('input[name="start_date"]');
    this.usernameInput = page.locator('input[name="ppp_username"]');
    this.passwordInput = page.locator('input[name="ppp_password"]');
    this.ipAddressInput = page.locator('input[name="ip_address"]');
    this.routerSelect = page.locator('select[name="router_id"]');

    // Detail page
    this.subscriptionHeader = page.locator('[data-testid="page-title"]');
    this.subscriptionStatus = page.locator('[data-testid="subscription-status"]');
    this.subscriptionTariff = page.locator('[data-testid="subscription-tariff"]');
    this.subscriptionParty = page.locator('[data-testid="subscription-party"]');

    // Tabs
    this.tabBilling = page.locator('a[href*="billing"], button:has-text("Billing")');
    this.tabUsage = page.locator('a[href*="usage"], button:has-text("Usage")');
    this.tabSessions = page.locator('a[href*="sessions"], button:has-text("Sessions")');
    this.tabProvisioning = page.locator('a[href*="provisioning"], button:has-text("Provisioning")');
    this.tabSettings = page.locator('a[href*="settings"], button:has-text("Settings")');

    // Actions
    this.renewButton = page.locator('[data-testid="renew-btn"]');
    this.suspendButton = page.locator('[data-testid="suspend-btn"]');
    this.activateButton = page.locator('[data-testid="status-active-button"]');
    this.provisionButton = page.locator('[data-testid="provision-btn"]');
    this.changePlanButton = page.locator('[data-testid="change-plan-btn"]');

    // Tariffs
    this.tariffsTable = page.locator('[data-testid="tariffs-table"] table');
    this.tariffSearch = page.locator('[data-testid="tariff-search"]');
    this.newTariffButton = page.locator('[data-testid="new-tariff"]');
  }

  // =========================================================================
  // NAVIGATION
  // =========================================================================

  async gotoList(): Promise<void> {
    await this.goto(this.listUrl);
  }

  async gotoDashboard(): Promise<void> {
    await this.goto(this.dashboardUrl);
  }

  async gotoCreate(): Promise<void> {
    await this.goto(this.createUrl);
  }

  async gotoSubscription(id: number): Promise<void> {
    await this.goto(`${this.listUrl}/${id}`);
  }

  async gotoTariffs(): Promise<void> {
    await this.goto(this.tariffsUrl);
  }

  async gotoTariff(id: number): Promise<void> {
    await this.goto(`${this.tariffsUrl}/${id}`);
  }

  // =========================================================================
  // SUBSCRIPTIONS LIST
  // =========================================================================

  async searchSubscriptions(query: string): Promise<void> {
    await this.subscriptionSearch.fill(query);
    await this.page.waitForTimeout(400);
    await this.waitForHtmxComplete();
  }

  async filterByStatus(status: 'active' | 'suspended' | 'expired' | 'pending'): Promise<void> {
    const select = this.statusFilter.first();
    if (await select.count() > 0) {
      await select.selectOption(status);
      await this.waitForHtmxComplete();
      return;
    }

    await this.statusFilterButton.click();
    const option = this.page.locator(`[data-testid="status-option-${status.replace(/\\s+/g, '-')}"]`);
    await option.click();
    await this.waitForHtmxComplete();
  }

  async filterByTariff(tariffId: string): Promise<void> {
    await this.tariffFilter.selectOption(tariffId);
    await this.waitForHtmxComplete();
  }

  async getSubscriptionCount(): Promise<number> {
    return await this.getTableRowCount(this.subscriptionsTable);
  }

  async hasSubscriptions(): Promise<boolean> {
    return (await this.subscriptionsTable.locator('tbody tr').count()) > 0;
  }

  async ensureHasSubscriptions(): Promise<boolean> {
    if (await this.hasSubscriptions()) {
      return true;
    }
    const emptyState = this.page.locator('[data-testid="empty-state"]');
    if (await emptyState.count() > 0) {
      return false;
    }
    await this.page.waitForTimeout(300);
    return await this.hasSubscriptions();
  }

  async clickSubscription(username: string): Promise<void> {
    const link = this.subscriptionsTable.locator('[data-testid="subscription-name"]', { hasText: username }).first();
    await this.htmxClick(link);
  }

  async getSubscriptionRowData(index: number): Promise<{
    username: string;
    party: string;
    tariff: string;
    status: string;
  }> {
    const row = this.subscriptionsTable.locator('tbody tr').nth(index);
    const nameLink = row.locator('[data-testid="subscription-name"]').first();
    return {
      username: (await nameLink.textContent()) || (await row.locator('td').nth(0).textContent()) || '',
      party: await row.locator('td').nth(1).textContent() || '',
      tariff: await row.locator('td').nth(2).textContent() || '',
      status: await row.locator('[data-testid="subscription-status"]').textContent() || '',
    };
  }

  async expectEmptyState(): Promise<void> {
    const emptyState = this.page.locator('.empty-state, [data-testid="empty-state"]');
    await expect(emptyState).toBeVisible();
  }

  // =========================================================================
  // SUBSCRIPTION DETAIL TABS
  // =========================================================================

  async switchToTab(tab: 'billing' | 'usage' | 'sessions' | 'provisioning' | 'settings'): Promise<void> {
    const tabLocator = {
      billing: this.tabBilling,
      usage: this.tabUsage,
      sessions: this.tabSessions,
      provisioning: this.tabProvisioning,
      settings: this.tabSettings,
    }[tab];
    await this.htmxClick(tabLocator);
  }

  // =========================================================================
  // SUBSCRIPTION ACTIONS
  // =========================================================================

  async renewSubscription(): Promise<void> {
    await this.renewButton.click();
    // Wait for modal if exists
    const modal = this.page.locator('[role="dialog"], .modal');
    if (await modal.count() > 0) {
      await expect(modal).toBeVisible();
      const confirmBtn = modal.locator('button:has-text("Confirm"), button:has-text("Renew")');
      await confirmBtn.click();
    }
    await this.waitForHtmxComplete();
  }

  async suspendSubscription(): Promise<void> {
    await this.suspendButton.click();
    const modal = this.page.locator('[role="dialog"], .modal');
    if (await modal.count() > 0) {
      await expect(modal).toBeVisible();
      const confirmBtn = modal.locator('button:has-text("Confirm"), button:has-text("Suspend")');
      await confirmBtn.click();
    }
    await this.waitForHtmxComplete();
  }

  async activateSubscription(): Promise<void> {
    await this.activateButton.click();
    const modal = this.page.locator('[role="dialog"], .modal');
    if (await modal.count() > 0) {
      await expect(modal).toBeVisible();
      const confirmBtn = modal.locator('button:has-text("Confirm"), button:has-text("Activate")');
      await confirmBtn.click();
    }
    await this.waitForHtmxComplete();
  }

  async provisionSubscription(): Promise<void> {
    await this.provisionButton.click();
    await this.waitForHtmxComplete();
  }

  // =========================================================================
  // TARIFFS
  // =========================================================================

  async searchTariffs(query: string): Promise<void> {
    await this.tariffSearch.fill(query);
    await this.page.waitForTimeout(400);
    await this.waitForHtmxComplete();
  }

  async getTariffCount(): Promise<number> {
    return await this.getTableRowCount(this.tariffsTable);
  }

  async hasTariffs(): Promise<boolean> {
    return (await this.tariffsTable.locator('tbody tr').count()) > 0;
  }

  async clickTariff(name: string): Promise<void> {
    const link = this.tariffsTable.locator('[data-testid="tariff-name"]', { hasText: name }).first();
    await this.htmxClick(link);
  }

  // =========================================================================
  // ASSERTIONS
  // =========================================================================

  async expectSubscriptionStatus(status: string): Promise<void> {
    await expect(this.subscriptionStatus.first()).toContainText(status, { ignoreCase: true });
  }

  async expectSubscriptionInList(username: string): Promise<void> {
    const link = this.subscriptionsTable.locator('[data-testid="subscription-name"]', { hasText: username }).first();
    await expect(link).toBeVisible();
  }

  async expectEmptyState(): Promise<void> {
    const emptyState = this.page.locator('[data-testid="empty-state"]');
    await expect(emptyState).toBeVisible();
  }

  async expectStatsVisible(): Promise<void> {
    const stats = this.page.locator('[data-testid="subscription-stats"]');
    await expect(stats.first()).toBeVisible();
  }
}
