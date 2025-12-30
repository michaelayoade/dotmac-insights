/**
 * Sales Invoices Page Object
 *
 * Page object for sales invoices views.
 */

import { type Page, type Locator, expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class SalesInvoicesPage extends BasePage {
  // Invoice-specific selectors
  readonly statusFilter: Locator;
  readonly customerFilter: Locator;
  readonly dateRangeFilter: Locator;
  readonly invoiceRows: Locator;
  readonly createInvoiceButton: Locator;
  readonly lineItemsTable: Locator;
  readonly addLineItemButton: Locator;
  readonly subtotalAmount: Locator;
  readonly taxAmount: Locator;
  readonly totalAmount: Locator;
  readonly postButton: Locator;
  readonly voidButton: Locator;
  readonly emailButton: Locator;
  readonly printButton: Locator;

  constructor(page: Page) {
    super(page);

    this.statusFilter = page.locator('select').filter({ hasText: /status/i }).first();
    this.customerFilter = page.locator('select').filter({ hasText: /customer/i }).first();
    this.dateRangeFilter = page.locator('[data-testid="date-range-filter"]');
    this.invoiceRows = page.locator('table tbody tr');
    this.createInvoiceButton = page.getByRole('link', { name: /create invoice|new invoice/i });
    this.lineItemsTable = page.locator('[data-testid="line-items"], table.line-items');
    this.addLineItemButton = page.getByRole('button', { name: /add.*line|add.*item|add row/i });
    this.subtotalAmount = page.locator('[data-testid="subtotal"]').or(page.getByText(/subtotal/i).locator('+ *'));
    this.taxAmount = page.locator('[data-testid="tax-amount"]').or(page.getByText(/^tax$/i).locator('+ *'));
    this.totalAmount = page.locator('[data-testid="total"]').or(page.getByText(/total/i).locator('+ *'));
    this.postButton = page.getByRole('button', { name: /post|finalize/i });
    this.voidButton = page.getByRole('button', { name: /void|cancel/i });
    this.emailButton = page.getByRole('button', { name: /email|send/i });
    this.printButton = page.getByRole('button', { name: /print|pdf/i });
  }

  get url(): string {
    return '/sales/invoices';
  }

  /**
   * Navigate to a specific invoice
   */
  async gotoInvoice(invoiceId: number): Promise<void> {
    await this.page.goto(`/sales/invoices/${invoiceId}`);
  }

  /**
   * Filter by status
   */
  async filterByStatus(status: string): Promise<void> {
    await this.statusFilter.selectOption({ label: status });
    await this.page.waitForTimeout(500);
    await this.waitForTableData().catch(() => {});
  }

  /**
   * Filter by customer
   */
  async filterByCustomer(customerName: string): Promise<void> {
    await this.customerFilter.selectOption({ label: customerName });
    await this.page.waitForTimeout(500);
  }

  /**
   * Click an invoice row by invoice number
   */
  async clickInvoice(invoiceNumber: string): Promise<void> {
    await this.page.getByText(invoiceNumber).first().click();
  }

  /**
   * Open create invoice form
   */
  async openCreateInvoice(): Promise<void> {
    await this.createInvoiceButton.click();
  }

  /**
   * Create a new invoice
   */
  async createInvoice(data: {
    customer: string;
    items: Array<{
      description: string;
      quantity: string;
      unitPrice: string;
    }>;
    dueDate?: string;
  }): Promise<void> {
    await this.openCreateInvoice();

    // Select customer
    await this.selectDropdown('customer', data.customer);

    // Add line items
    for (let i = 0; i < data.items.length; i++) {
      if (i > 0) {
        await this.addLineItemButton.click();
      }

      const item = data.items[i];
      await this.fillLineItem(i, item.description, item.quantity, item.unitPrice);
    }

    if (data.dueDate) {
      await this.fillField('due date', data.dueDate);
    }

    await this.submitForm();
  }

  /**
   * Fill a line item in the invoice
   */
  async fillLineItem(index: number, description: string, quantity: string, unitPrice: string): Promise<void> {
    const row = this.lineItemsTable.locator('tbody tr').nth(index);
    await row.locator('input[name*="description"], [data-testid*="description"]').fill(description);
    await row.locator('input[name*="quantity"], [data-testid*="quantity"]').fill(quantity);
    await row.locator('input[name*="price"], [data-testid*="price"]').fill(unitPrice);
  }

  /**
   * Remove a line item
   */
  async removeLineItem(index: number): Promise<void> {
    const row = this.lineItemsTable.locator('tbody tr').nth(index);
    await row.getByRole('button', { name: /delete|remove/i }).click();
  }

  /**
   * Get invoice total
   */
  async getTotal(): Promise<string> {
    return await this.totalAmount.textContent() || '';
  }

  /**
   * Post/finalize the invoice
   */
  async postInvoice(): Promise<void> {
    await this.postButton.click();
    await this.confirmModal();
  }

  /**
   * Void the invoice
   */
  async voidInvoice(): Promise<void> {
    await this.voidButton.click();
    await this.confirmModal();
  }

  /**
   * Email the invoice
   */
  async emailInvoice(toEmail: string): Promise<void> {
    await this.emailButton.click();
    await this.fillField('email', toEmail);
    await this.clickButton('send');
  }

  /**
   * Verify invoice status
   */
  async expectStatus(status: string): Promise<void> {
    await expect(this.page.getByText(new RegExp(status, 'i'))).toBeVisible();
  }

  /**
   * Verify invoice total
   */
  async expectTotal(amount: string): Promise<void> {
    await expect(this.totalAmount).toContainText(amount);
  }
}

export default SalesInvoicesPage;
