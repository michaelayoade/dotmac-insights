import { Page, Locator, expect } from '@playwright/test';

/**
 * Base page object with common HTMX patterns.
 *
 * All page objects should extend this class.
 */
export class BasePage {
  readonly page: Page;

  // Common navigation elements
  readonly sidebar: Locator;
  readonly navbar: Locator;
  readonly breadcrumb: Locator;
  readonly pageTitle: Locator;

  // Common UI elements
  readonly loadingIndicator: Locator;
  readonly toast: Locator;
  readonly modal: Locator;
  readonly confirmDialog: Locator;

  constructor(page: Page) {
    this.page = page;

    // Navigation
    this.sidebar = page.locator('aside, nav[role="navigation"], .sidebar');
    this.navbar = page.locator('header nav, .navbar');
    this.breadcrumb = page.locator('.breadcrumb, nav[aria-label="Breadcrumb"]');
    this.pageTitle = page.locator('h1, .page-title');

    // UI Elements
    this.loadingIndicator = page.locator('.htmx-indicator, .loading, [data-loading]');
    this.toast = page.locator('.toast, [role="alert"], .notification');
    this.modal = page.locator('[role="dialog"], .modal');
    this.confirmDialog = page.locator('.confirm-dialog, [data-confirm]');
  }

  // =========================================================================
  // NAVIGATION
  // =========================================================================

  async goto(path: string): Promise<void> {
    await this.page.goto(path);
    await this.waitForPageLoad();
  }

  async navigateTo(linkText: string): Promise<void> {
    await this.sidebar.getByRole('link', { name: linkText }).click();
    await this.waitForPageLoad();
  }

  async waitForPageLoad(): Promise<void> {
    // Wait for HTMX to settle
    await this.page.waitForFunction(() => {
      return document.querySelectorAll('.htmx-request').length === 0;
    }, { timeout: 10000 });

    // Wait for loading indicators to disappear
    await expect(this.loadingIndicator).toHaveCount(0, { timeout: 10000 }).catch(() => {});
  }

  // =========================================================================
  // HTMX HELPERS
  // =========================================================================

  /**
   * Click an HTMX-enabled element and wait for response.
   */
  async htmxClick(locator: Locator): Promise<void> {
    await locator.click();
    await this.waitForHtmxComplete();
  }

  /**
   * Wait for all HTMX requests to complete.
   */
  async waitForHtmxComplete(): Promise<void> {
    await this.page.waitForFunction(() => {
      return document.querySelectorAll('.htmx-request').length === 0;
    }, { timeout: 10000 });
    await this.page.waitForTimeout(100); // Buffer for DOM updates
  }

  /**
   * Submit a form via HTMX.
   */
  async htmxSubmitForm(form: Locator): Promise<void> {
    const submitBtn = form.locator('button[type="submit"]').first();
    await submitBtn.click();
    await this.waitForHtmxComplete();
  }

  // =========================================================================
  // TOASTS & NOTIFICATIONS
  // =========================================================================

  async expectToast(message: string | RegExp): Promise<void> {
    await expect(this.toast.filter({ hasText: message })).toBeVisible({ timeout: 5000 });
  }

  async expectSuccessToast(message?: string | RegExp): Promise<void> {
    const successToast = this.toast.filter({ has: this.page.locator('.success, [data-type="success"]') });
    if (message) {
      await expect(successToast.filter({ hasText: message })).toBeVisible();
    } else {
      await expect(successToast).toBeVisible();
    }
  }

  async expectErrorToast(message?: string | RegExp): Promise<void> {
    const errorToast = this.toast.filter({ has: this.page.locator('.error, [data-type="error"]') });
    if (message) {
      await expect(errorToast.filter({ hasText: message })).toBeVisible();
    } else {
      await expect(errorToast).toBeVisible();
    }
  }

  async dismissToast(): Promise<void> {
    const closeBtn = this.toast.locator('button[aria-label="Close"], .close');
    if (await closeBtn.count() > 0) {
      await closeBtn.first().click();
    }
  }

  // =========================================================================
  // MODALS & DIALOGS
  // =========================================================================

  async expectModalOpen(): Promise<void> {
    await expect(this.modal).toBeVisible();
  }

  async expectModalClosed(): Promise<void> {
    await expect(this.modal).not.toBeVisible();
  }

  async closeModal(): Promise<void> {
    const closeBtn = this.modal.locator('button[aria-label="Close"], .close, [data-dismiss="modal"]');
    await closeBtn.click();
    await this.expectModalClosed();
  }

  async confirmDialog(): Promise<void> {
    const confirmBtn = this.confirmDialog.locator('button:has-text("Confirm"), button:has-text("Yes"), button:has-text("Delete")');
    await confirmBtn.click();
    await this.waitForHtmxComplete();
  }

  async cancelDialog(): Promise<void> {
    const cancelBtn = this.confirmDialog.locator('button:has-text("Cancel"), button:has-text("No")');
    await cancelBtn.click();
  }

  // =========================================================================
  // DATA TABLES
  // =========================================================================

  getTable(name?: string): Locator {
    if (name) {
      return this.page.locator(`table[aria-label="${name}"], table:has(caption:has-text("${name}"))`);
    }
    return this.page.locator('table').first();
  }

  async getTableRowCount(table?: Locator): Promise<number> {
    const t = table || this.getTable();
    return await t.locator('tbody tr').count();
  }

  async getTableRow(index: number, table?: Locator): Promise<Locator> {
    const t = table || this.getTable();
    return t.locator('tbody tr').nth(index);
  }

  async clickTableAction(rowIndex: number, action: string, table?: Locator): Promise<void> {
    const row = await this.getTableRow(rowIndex, table);
    const actionBtn = row.locator(`button:has-text("${action}"), a:has-text("${action}"), [aria-label="${action}"]`);
    await this.htmxClick(actionBtn);
  }

  // =========================================================================
  // PAGINATION
  // =========================================================================

  getPagination(): Locator {
    return this.page.locator('.pagination, nav[aria-label="Pagination"]');
  }

  async goToNextPage(): Promise<void> {
    const nextBtn = this.getPagination().locator('a:has-text("Next"), button:has-text("Next"), [aria-label="Next page"]');
    await this.htmxClick(nextBtn);
  }

  async goToPrevPage(): Promise<void> {
    const prevBtn = this.getPagination().locator('a:has-text("Previous"), button:has-text("Previous"), [aria-label="Previous page"]');
    await this.htmxClick(prevBtn);
  }

  async goToPage(pageNum: number): Promise<void> {
    const pageBtn = this.getPagination().locator(`a:has-text("${pageNum}"), button:has-text("${pageNum}")`);
    await this.htmxClick(pageBtn);
  }

  // =========================================================================
  // FORMS
  // =========================================================================

  async fillInput(name: string, value: string): Promise<void> {
    await this.page.fill(`input[name="${name}"], textarea[name="${name}"]`, value);
  }

  async selectOption(name: string, value: string): Promise<void> {
    await this.page.selectOption(`select[name="${name}"]`, value);
  }

  async checkCheckbox(name: string): Promise<void> {
    await this.page.check(`input[name="${name}"][type="checkbox"]`);
  }

  async uncheckCheckbox(name: string): Promise<void> {
    await this.page.uncheck(`input[name="${name}"][type="checkbox"]`);
  }

  // =========================================================================
  // SEARCH & FILTERS
  // =========================================================================

  async search(query: string): Promise<void> {
    const searchInput = this.page.locator('input[type="search"], input[name="search"], input[placeholder*="Search"]');
    await searchInput.fill(query);

    // HTMX search typically triggers on keyup with delay
    await this.page.waitForTimeout(500); // Wait for debounce
    await this.waitForHtmxComplete();
  }

  async clearSearch(): Promise<void> {
    const searchInput = this.page.locator('input[type="search"], input[name="search"]');
    await searchInput.clear();
    await this.page.waitForTimeout(500);
    await this.waitForHtmxComplete();
  }

  async applyFilter(filterName: string, value: string): Promise<void> {
    const filterSelect = this.page.locator(`select[name="${filterName}"], [data-filter="${filterName}"]`);
    await filterSelect.selectOption(value);
    await this.waitForHtmxComplete();
  }

  // =========================================================================
  // ASSERTIONS
  // =========================================================================

  async expectPageTitle(title: string | RegExp): Promise<void> {
    await expect(this.pageTitle).toHaveText(title);
  }

  async expectUrl(url: string | RegExp): Promise<void> {
    await expect(this.page).toHaveURL(url);
  }

  async expectNoErrors(): Promise<void> {
    // Check for error alerts
    const errorAlert = this.page.locator('.alert-error, .error-message, [role="alert"][data-type="error"]');
    await expect(errorAlert).toHaveCount(0);
  }
}
