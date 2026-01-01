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
  readonly listUrl = '/crm/contacts';
  readonly createUrl = '/crm/contacts/new';

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
    this.contactsTable = page.locator('#contacts-table, table[data-testid="contacts-table"]');
    this.searchInput = page.locator('input[name="search"], input[hx-get*="search"]');
    this.typeFilter = page.locator('select[name="contact_type"], [data-filter="type"]');
    this.statusFilter = page.locator('select[name="status"], [data-filter="status"]');
    this.createButton = page.locator('a[href*="/new"], button:has-text("New Contact")');
    this.bulkActions = page.locator('.bulk-actions, [data-bulk-actions]');

    // Form
    this.contactForm = page.locator('form[hx-post*="contacts"], form[hx-put*="contacts"]');
    this.nameInput = page.locator('input[name="name"]');
    this.emailInput = page.locator('input[name="email"]');
    this.phoneInput = page.locator('input[name="phone"]');
    this.typeSelect = page.locator('select[name="contact_type"]');
    this.categorySelect = page.locator('select[name="category"]');
    this.companyInput = page.locator('input[name="company_name"]');
    this.saveButton = page.locator('button[type="submit"]:has-text("Save"), button:has-text("Create")');
    this.cancelButton = page.locator('a:has-text("Cancel"), button:has-text("Cancel")');

    // Detail page
    this.contactHeader = page.locator('.contact-header, [data-testid="contact-header"]');
    this.contactTabs = page.locator('.tabs, [role="tablist"]');
    this.activityTimeline = page.locator('.activity-timeline, [data-testid="activity"]');
    this.editButton = page.locator('a:has-text("Edit"), button:has-text("Edit")');
    this.deleteButton = page.locator('button:has-text("Delete")');
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

  async filterByType(type: 'lead' | 'prospect' | 'customer' | 'churned'): Promise<void> {
    await this.typeFilter.selectOption(type);
    await this.waitForHtmxComplete();
  }

  async filterByStatus(status: 'active' | 'inactive' | 'suspended'): Promise<void> {
    await this.statusFilter.selectOption(status);
    await this.waitForHtmxComplete();
  }

  async clearFilters(): Promise<void> {
    await this.searchInput.clear();
    await this.typeFilter.selectOption('');
    await this.statusFilter.selectOption('');
    await this.waitForHtmxComplete();
  }

  // =========================================================================
  // CONTACT LIST
  // =========================================================================

  async getContactCount(): Promise<number> {
    return await this.getTableRowCount(this.contactsTable);
  }

  async getContactRowByName(name: string): Promise<Locator> {
    return this.contactsTable.locator(`tbody tr:has-text("${name}")`);
  }

  async clickContact(name: string): Promise<void> {
    const row = await this.getContactRowByName(name);
    const link = row.locator('a').first();
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
      name: await row.locator('td').nth(0).textContent() || '',
      email: await row.locator('td').nth(1).textContent() || '',
      phone: await row.locator('td').nth(2).textContent() || '',
      type: await row.locator('td').nth(3).textContent() || '',
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
    if (data.category) await this.categorySelect.selectOption(data.category);
    if (data.company) await this.companyInput.fill(data.company);
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
    const selectAll = this.contactsTable.locator('thead input[type="checkbox"]');
    await selectAll.check();
  }

  async bulkDelete(): Promise<void> {
    const deleteBtn = this.bulkActions.locator('button:has-text("Delete")');
    await this.htmxClick(deleteBtn);
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
    const badge = this.contactHeader.locator('.badge, [data-type]');
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
    const emptyState = this.page.locator('.empty-state, [data-testid="empty-state"]');
    await expect(emptyState).toBeVisible();
  }

  async expectFormError(field: string, message?: string): Promise<void> {
    const error = this.page.locator(`[data-error="${field}"], .field-error:near(input[name="${field}"])`);
    if (message) {
      await expect(error).toContainText(message);
    } else {
      await expect(error).toBeVisible();
    }
  }
}
