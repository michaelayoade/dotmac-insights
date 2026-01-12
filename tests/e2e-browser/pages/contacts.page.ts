import { Page, Locator, expect } from '@playwright/test';
import { BasePage } from './base.page';

/**
 * Page object for Contacts/CRM module.
 *
 * Handles:
 * - Contact list with HTMX-powered search/filter
 * - Contact detail view
 * - Contact create/edit forms
 * - Bulk operations
 */
export class ContactsPage extends BasePage {
  // URL patterns
  readonly listUrl = '/crm/parties';
  readonly createUrl = '/crm/parties/new';

  // List page elements
  readonly contactsTable: Locator;
  readonly searchInput: Locator;
  readonly typeFilter: Locator;
  readonly statusFilter: Locator;
  readonly createButton: Locator;
  readonly bulkActions: Locator;

  // Form elements
  readonly contactForm: Locator;
  readonly nameInput: Locator;
  readonly emailInput: Locator;
  readonly phoneInput: Locator;
  readonly typeSelect: Locator;
  readonly categorySelect: Locator;
  readonly companyInput: Locator;
  readonly saveButton: Locator;
  readonly cancelButton: Locator;

  // Detail page elements
  readonly contactHeader: Locator;
  readonly contactTabs: Locator;
  readonly activityTimeline: Locator;
  readonly editButton: Locator;
  readonly deleteButton: Locator;

  constructor(page: Page) {
    super(page);

    // List page
    this.contactsTable = page.locator('[data-testid="contacts-table"] table');
    this.searchInput = page.locator('[data-testid="contacts-search"]');
    this.typeFilter = page.locator('[data-testid="type-filter-button"]');
    this.statusFilter = page.locator('[data-testid="status-filter-button"]');
    this.createButton = page.locator('[data-testid="new-contact-button"]');
    this.bulkActions = page.locator('[data-testid="bulk-actions-bar"]');

    // Form
    this.contactForm = page.locator('[data-testid="contact-form"]');
    this.nameInput = page.locator('input[name="name"]');
    this.emailInput = page.locator('input[name="email"]');
    this.phoneInput = page.locator('input[name="phone"]');
    this.typeSelect = page.locator('select[name="contact_type"]');
    this.categorySelect = page.locator('select[name="category"]');
    this.companyInput = page.locator('input[name="company_name"]');
    this.saveButton = page.locator('[data-testid="contact-submit-button"]');
    this.cancelButton = page.locator('[data-testid="contact-cancel-button"]');

    // Detail page
    this.contactHeader = page.locator('[data-testid="contact-header"]');
    this.contactTabs = page.locator('[role="tablist"]');
    this.activityTimeline = page.locator('[data-testid="activity"]');
    this.editButton = page.locator('[data-testid="edit-contact-button"]');
    this.deleteButton = page.locator('[data-testid="delete-contact-button"]');
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

  async gotoContact(id: number): Promise<void> {
    await this.goto(`${this.listUrl}/${id}`);
  }

  // =========================================================================
  // SEARCH & FILTER
  // =========================================================================

  async searchContacts(query: string): Promise<void> {
    await this.searchInput.fill(query);
    // HTMX triggers on keyup with debounce
    await this.page.waitForTimeout(400);
    await this.waitForHtmxComplete();
  }

  async clearSearch(): Promise<void> {
    await this.searchInput.fill('');
    await this.page.waitForTimeout(300);
    await this.waitForHtmxComplete();
  }

  async filterByType(type: 'lead' | 'prospect' | 'customer' | 'churned'): Promise<void> {
    const select = this.typeFilter;
    if (await select.count() > 0) {
      await select.selectOption(type);
      await this.waitForHtmxComplete();
      return;
    }

    await this.openDropdownAndSelect(this.typeFilter, this.toTitleCase(type));
  }

  async filterByStatus(status: 'active' | 'inactive' | 'suspended'): Promise<void> {
    const select = this.statusFilter;
    if (await select.count() > 0) {
      await select.selectOption(status);
      await this.waitForHtmxComplete();
      return;
    }

    await this.openDropdownAndSelect(this.statusFilter, this.toTitleCase(status));
  }

  async clearFilters(): Promise<void> {
    await this.searchInput.clear();
    const clearBtn = this.page.locator('button:has-text("Clear all")');
    if (await clearBtn.count() > 0) {
      await this.htmxClick(clearBtn.first());
      return;
    }

    const typeSelect = this.page.locator('select[name="contact_type"]');
    const statusSelect = this.page.locator('select[name="status"]');
    if (await typeSelect.count() > 0) await typeSelect.selectOption('');
    if (await statusSelect.count() > 0) await statusSelect.selectOption('');
    await this.waitForHtmxComplete();
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
  // CONTACT LIST
  // =========================================================================

  async getContactCount(): Promise<number> {
    return await this.getTableRowCount(this.contactsTable);
  }

  async getContactRowByName(name: string): Promise<Locator> {
    return this.contactsTable.locator('tbody tr', {
      has: this.contactsTable.locator('[data-testid="contact-name"]', { hasText: name }),
    });
  }

  async hasContacts(): Promise<boolean> {
    return (await this.contactsTable.locator('tbody tr').count()) > 0;
  }

  async ensureHasContacts(): Promise<boolean> {
    if (await this.hasContacts()) {
      return true;
    }
    const emptyState = this.page.locator('[data-testid="contacts-empty-state"], [data-testid="empty-state"]');
    if (await emptyState.count() > 0) {
      return false;
    }
    await this.page.waitForTimeout(300);
    return await this.hasContacts();
  }

  async clickContact(name: string): Promise<void> {
    const row = await this.getContactRowByName(name);
    const link = row.locator('[data-testid="contact-name"]').first();
    await this.htmxClick(link);
  }

  async getContactData(rowIndex: number): Promise<{
    name: string;
    email: string;
    phone: string;
    type: string;
  }> {
    const row = await this.getTableRow(rowIndex, this.contactsTable);
    return {
      name: await row.locator('[data-testid="contact-name"]').textContent() || '',
      email: await row.locator('[data-testid="contact-email"]').textContent() || '',
      phone: await row.locator('[data-testid="contact-phone"]').textContent() || '',
      type: await row.locator('[data-testid="contact-type"]').textContent() || '',
    };
  }

  // =========================================================================
  // CREATE/EDIT CONTACT
  // =========================================================================

  async fillContactForm(data: {
    name: string;
    email?: string;
    phone?: string;
    type?: string;
    category?: string;
    company?: string;
  }): Promise<void> {
    await this.nameInput.fill(data.name);
    if (data.email) await this.emailInput.fill(data.email);
    if (data.phone) await this.phoneInput.fill(data.phone);
    if (data.type) await this.typeSelect.selectOption(data.type);
    if (data.category && await this.categorySelect.count() > 0) {
      await this.categorySelect.selectOption(data.category);
    }
    if (data.company && await this.companyInput.count() > 0) {
      await this.companyInput.fill(data.company);
    }
  }

  async createContact(data: {
    name: string;
    email?: string;
    phone?: string;
    type?: string;
    category?: string;
    company?: string;
  }): Promise<void> {
    await this.gotoCreate();
    await this.fillContactForm(data);
    await this.htmxSubmitForm(this.contactForm);
  }

  async editContact(data: Partial<{
    name: string;
    email: string;
    phone: string;
    type: string;
    category: string;
    company: string;
  }>): Promise<void> {
    await this.htmxClick(this.editButton);
    if (data.name) await this.nameInput.fill(data.name);
    if (data.email) await this.emailInput.fill(data.email);
    if (data.phone) await this.phoneInput.fill(data.phone);
    if (data.type) await this.typeSelect.selectOption(data.type);
    await this.htmxSubmitForm(this.contactForm);
  }

  async deleteContact(): Promise<void> {
    await this.htmxClick(this.deleteButton);
    await this.confirmDialog();
  }

  // =========================================================================
  // BULK OPERATIONS
  // =========================================================================

  async selectContacts(indices: number[]): Promise<void> {
    for (const index of indices) {
      const row = await this.getTableRow(index, this.contactsTable);
      const checkbox = row.locator('input[type="checkbox"]');
      await checkbox.check();
    }
  }

  async selectAllContacts(): Promise<void> {
    const selectAll = this.contactsTable.locator('[data-testid="select-all-contacts"]');
    await selectAll.check();
  }

  async bulkDelete(): Promise<void> {
    const deleteBtn = this.bulkActions.locator('button:has-text("Delete")');
    await this.htmxClick(deleteBtn);
    const modalDelete = this.page.locator('button:has-text("Delete All")');
    if (await modalDelete.count() > 0) {
      const navPromise = this.page.waitForNavigation({ waitUntil: 'load', timeout: 10000 }).catch(() => null);
      await modalDelete.click();
      await navPromise;
      return;
    }
    await this.confirmDialog();
  }

  async bulkAssign(ownerId: string): Promise<void> {
    const assignBtn = this.bulkActions.locator('button:has-text("Assign")');
    await assignBtn.click();
    await this.expectModalOpen();
    await this.page.selectOption('select[name="owner_id"]', ownerId);
    await this.htmxClick(this.page.locator('button:has-text("Assign")'));
  }

  // =========================================================================
  // CONTACT DETAIL
  // =========================================================================

  async switchTab(tabName: string): Promise<void> {
    const tab = this.contactTabs.locator(`button:has-text("${tabName}"), a:has-text("${tabName}")`);
    await this.htmxClick(tab);
  }

  async expectContactName(name: string): Promise<void> {
    await expect(this.contactHeader).toContainText(name);
  }

  async expectContactType(type: string): Promise<void> {
    const badge = this.contactHeader.locator('[data-type]');
    await expect(badge).toContainText(type);
  }

  // =========================================================================
  // ASSERTIONS
  // =========================================================================

  async expectContactInList(name: string): Promise<void> {
    const row = await this.getContactRowByName(name);
    await expect(row).toBeVisible();
  }

  async expectContactNotInList(name: string): Promise<void> {
    const row = await this.getContactRowByName(name);
    await expect(row).not.toBeVisible();
  }

  async expectEmptyState(): Promise<void> {
    const emptyState = this.page.locator('[data-testid="contacts-empty-state"], [data-testid="empty-state"]');
    await expect(emptyState).toBeVisible();
  }

  async expectFormError(field: string, message?: string): Promise<void> {
    const error = this.page.locator(
      `[data-error="${field}"], [data-testid="${field}-error"], .field-error:near(input[name="${field}"])`
    );
    if (message) {
      await expect(error).toContainText(message);
    } else {
      await expect(error).toBeVisible();
    }
  }
}
