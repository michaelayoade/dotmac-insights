/**
 * BasePage - Page Object Model Base Class
 *
 * Provides common selectors and actions for all page objects.
 * All module-specific page objects should extend this class.
 */

import { type Page, type Locator, expect } from '@playwright/test';

export abstract class BasePage {
  readonly page: Page;

  // Common selectors
  readonly loadingIndicator: Locator;
  readonly mainContent: Locator;
  readonly dataTable: Locator;
  readonly emptyState: Locator;
  readonly searchInput: Locator;
  readonly pageTitle: Locator;
  readonly createButton: Locator;
  readonly pagination: Locator;
  readonly toast: Locator;
  readonly modal: Locator;
  readonly confirmButton: Locator;
  readonly cancelButton: Locator;

  constructor(page: Page) {
    this.page = page;

    // Common element locators
    this.loadingIndicator = page.locator('[data-testid="loading"], .loading, .animate-pulse').first();
    this.mainContent = page.locator('main, [role="main"]').first();
    this.dataTable = page.locator('table, [role="grid"]').first();
    this.emptyState = page.getByText(/no results|empty|no data|no items/i);
    this.searchInput = page.getByPlaceholder(/search/i);
    this.pageTitle = page.locator('h1, [role="heading"]').first();
    this.createButton = page.getByRole('link', { name: /add|create|new/i }).or(
      page.getByRole('button', { name: /add|create|new/i })
    );
    this.pagination = page.locator('[aria-label*="page"], [data-testid="pagination"]').first();
    this.toast = page.locator('[role="alert"], [data-testid="toast"]').first();
    this.modal = page.locator('[role="dialog"], [data-testid="modal"]').first();
    this.confirmButton = page.getByRole('button', { name: /confirm|yes|ok|delete|archive/i });
    this.cancelButton = page.getByRole('button', { name: /cancel|no|close/i });
  }

  // Abstract methods that subclasses must implement
  abstract get url(): string;

  /**
   * Navigate to this page
   */
  async goto(): Promise<void> {
    await this.page.goto(this.url);
  }

  /**
   * Wait for the page to fully load
   */
  async waitForPageLoad(timeout = 10000): Promise<void> {
    // Wait for any loading indicators to disappear
    await this.loadingIndicator.waitFor({ state: 'hidden', timeout }).catch(() => {
      // Ignore if no loading indicator
    });

    // Wait for main content to be visible
    await this.mainContent.waitFor({ state: 'visible', timeout });
  }

  /**
   * Wait for data table to load with data
   */
  async waitForTableData(timeout = 10000): Promise<void> {
    await this.page.waitForSelector('table tbody tr, [role="grid"] [role="row"]', {
      timeout,
    });
  }

  /**
   * Check if data table has any rows
   */
  async hasTableData(): Promise<boolean> {
    const rows = await this.page.locator('table tbody tr, [role="grid"] [role="row"]').count();
    return rows > 0;
  }

  /**
   * Get the number of rows in the data table
   */
  async getTableRowCount(): Promise<number> {
    return await this.page.locator('table tbody tr, [role="grid"] [role="row"]').count();
  }

  /**
   * Search for items using the search input
   */
  async search(query: string): Promise<void> {
    await this.searchInput.fill(query);
    // Wait for results to update
    await this.page.waitForTimeout(500);
    await this.waitForTableData().catch(() => {
      // Empty results are ok
    });
  }

  /**
   * Clear the search input
   */
  async clearSearch(): Promise<void> {
    await this.searchInput.clear();
    await this.page.waitForTimeout(500);
  }

  /**
   * Click the create/add button
   */
  async clickCreate(): Promise<void> {
    await this.createButton.click();
  }

  /**
   * Navigate to next page in pagination
   */
  async nextPage(): Promise<void> {
    const nextButton = this.page.getByRole('button', { name: /next/i }).or(
      this.page.locator('[aria-label*="next"]')
    );
    await nextButton.click();
    await this.waitForTableData();
  }

  /**
   * Navigate to previous page in pagination
   */
  async prevPage(): Promise<void> {
    const prevButton = this.page.getByRole('button', { name: /previous|prev/i }).or(
      this.page.locator('[aria-label*="previous"]')
    );
    await prevButton.click();
    await this.waitForTableData();
  }

  /**
   * Select a filter option
   */
  async selectFilter(filterLabel: string, optionValue: string): Promise<void> {
    const filter = this.page.locator('select').filter({ hasText: new RegExp(filterLabel, 'i') }).first();
    await filter.selectOption({ label: optionValue });
    await this.page.waitForTimeout(500);
  }

  /**
   * Click a table row by index
   */
  async clickTableRow(index: number): Promise<void> {
    const rows = this.page.locator('table tbody tr, [role="grid"] [role="row"]');
    await rows.nth(index).click();
  }

  /**
   * Get text from a table cell
   */
  async getTableCellText(rowIndex: number, colIndex: number): Promise<string> {
    const cell = this.page.locator(`table tbody tr:nth-child(${rowIndex + 1}) td:nth-child(${colIndex + 1})`);
    return await cell.textContent() || '';
  }

  /**
   * Wait for and verify a toast notification
   */
  async expectToast(messagePattern: RegExp): Promise<void> {
    await expect(this.toast).toContainText(messagePattern, { timeout: 5000 });
  }

  /**
   * Wait for modal to appear
   */
  async waitForModal(): Promise<void> {
    await this.modal.waitFor({ state: 'visible' });
  }

  /**
   * Confirm in a modal dialog
   */
  async confirmModal(): Promise<void> {
    await this.waitForModal();
    await this.confirmButton.click();
    await this.modal.waitFor({ state: 'hidden' });
  }

  /**
   * Cancel in a modal dialog
   */
  async cancelModal(): Promise<void> {
    await this.waitForModal();
    await this.cancelButton.click();
    await this.modal.waitFor({ state: 'hidden' });
  }

  /**
   * Fill a form field by label
   */
  async fillField(label: string, value: string): Promise<void> {
    await this.page.getByLabel(new RegExp(label, 'i')).fill(value);
  }

  /**
   * Select a dropdown option by label
   */
  async selectDropdown(label: string, optionLabel: string): Promise<void> {
    const dropdown = this.page.getByLabel(new RegExp(label, 'i'));
    await dropdown.click();
    await this.page.getByRole('option', { name: new RegExp(optionLabel, 'i') }).click();
  }

  /**
   * Click a button by name
   */
  async clickButton(name: string): Promise<void> {
    await this.page.getByRole('button', { name: new RegExp(name, 'i') }).click();
  }

  /**
   * Submit a form
   */
  async submitForm(): Promise<void> {
    const submitButton = this.page.getByRole('button', { name: /save|create|submit|update/i });
    await submitButton.click();
  }

  /**
   * Check for validation error message
   */
  async expectValidationError(message: string): Promise<void> {
    await expect(this.page.getByText(new RegExp(message, 'i'))).toBeVisible();
  }

  /**
   * Check for access denied message
   */
  async expectAccessDenied(): Promise<void> {
    await expect(this.page.getByText(/access denied|not authorized|permission denied/i)).toBeVisible();
  }

  /**
   * Check current URL matches expected pattern
   */
  async expectUrl(pattern: RegExp): Promise<void> {
    await expect(this.page).toHaveURL(pattern);
  }

  /**
   * Take a screenshot for debugging
   */
  async screenshot(name: string): Promise<void> {
    await this.page.screenshot({ path: `screenshots/${name}.png` });
  }
}

export default BasePage;
