import { Page, Locator, expect } from '@playwright/test';
import { BasePage } from './base.page';

/**
 * Page object for Accounting module.
 *
 * Handles:
 * - Invoices CRUD and payments
 * - AR/AP Payments and allocations
 * - Journal entries
 * - Financial reports (Balance Sheet, Income Statement, etc.)
 * - Aging reports
 */
export class AccountingPage extends BasePage {
  // URL patterns
  readonly dashboardUrl = '/accounting';
  readonly invoicesUrl = '/accounting/invoices';
  readonly arPaymentsUrl = '/accounting/ar-payments';
  readonly apPaymentsUrl = '/accounting/ap-payments';
  readonly journalEntriesUrl = '/accounting/journal-entries';
  readonly suppliersUrl = '/accounting/suppliers';
  readonly reportsUrl = '/accounting/reports';

  // Dashboard elements
  readonly dashboardStats: Locator;
  readonly revenueCard: Locator;
  readonly expenseCard: Locator;
  readonly receivablesCard: Locator;
  readonly payablesCard: Locator;

  // Invoices list elements
  readonly invoicesTable: Locator;
  readonly invoiceSearch: Locator;
  readonly invoiceStatusFilter: Locator;
  readonly newInvoiceButton: Locator;
  readonly statTotal: Locator;
  readonly statOutstanding: Locator;
  readonly statOverdue: Locator;
  readonly statPaid: Locator;

  // Invoice form elements
  readonly invoiceForm: Locator;
  readonly customerSelect: Locator;
  readonly invoiceDateInput: Locator;
  readonly dueDateInput: Locator;
  readonly lineItemsSection: Locator;
  readonly addLineButton: Locator;
  readonly invoiceSubtotal: Locator;
  readonly invoiceTotal: Locator;

  // Invoice detail elements
  readonly invoiceHeader: Locator;
  readonly invoiceStatus: Locator;
  readonly invoiceAmount: Locator;
  readonly invoiceBalance: Locator;
  readonly receivePaymentButton: Locator;
  readonly sendInvoiceButton: Locator;

  // Payments elements
  readonly paymentsTable: Locator;
  readonly paymentSearch: Locator;
  readonly paymentStatusFilter: Locator;
  readonly paymentMethodFilter: Locator;
  readonly newPaymentButton: Locator;

  // Payment form elements
  readonly paymentForm: Locator;
  readonly paymentAmountInput: Locator;
  readonly paymentMethodSelect: Locator;
  readonly paymentDateInput: Locator;
  readonly paymentReferenceInput: Locator;

  // Journal entries elements
  readonly journalEntriesTable: Locator;
  readonly journalSearch: Locator;
  readonly newJournalEntryButton: Locator;

  // Report elements
  readonly reportContainer: Locator;
  readonly reportPeriodSelect: Locator;
  readonly reportExportButton: Locator;

  constructor(page: Page) {
    super(page);

    // Dashboard
    this.dashboardStats = page.locator('.dashboard-stats, [data-testid="dashboard-stats"]');
    this.revenueCard = page.locator('[data-testid="revenue-card"], .stat-revenue');
    this.expenseCard = page.locator('[data-testid="expense-card"], .stat-expense');
    this.receivablesCard = page.locator('[data-testid="receivables-card"], .stat-receivables');
    this.payablesCard = page.locator('[data-testid="payables-card"], .stat-payables');

    // Invoices list
    this.invoicesTable = page.locator('#invoices-table, #invoices-table-container table, [data-testid="invoices-table"] table');
    this.invoiceSearch = page.locator('[data-testid="invoice-search"]');
    this.invoiceStatusFilter = page.locator('[data-testid="status-filter"]');
    this.newInvoiceButton = page.locator('[data-testid="new-invoice-button"]');
    this.statTotal = page.locator('[data-testid="stat-total"]');
    this.statOutstanding = page.locator('[data-testid="stat-outstanding"]');
    this.statOverdue = page.locator('[data-testid="stat-overdue"]');
    this.statPaid = page.locator('[data-testid="stat-paid"]');

    // Invoice form
    this.invoiceForm = page.locator('[data-testid="invoice-form"]');
    this.customerSelect = page.locator('select[name="customer_id"], [data-testid="customer-select"]');
    this.invoiceDateInput = page.locator('input[name="invoice_date"]');
    this.dueDateInput = page.locator('input[name="due_date"]');
    this.lineItemsSection = page.locator('#line-items, [data-testid="line-items"]');
    this.addLineButton = page.locator('button:has-text("Add Line"), [data-testid="add-line"]');
    this.invoiceSubtotal = page.locator('[data-testid="subtotal"]');
    this.invoiceTotal = page.locator('[data-testid="total"]');

    // Invoice detail
    this.invoiceHeader = page.locator('.invoice-header, [data-testid="invoice-header"]');
    this.invoiceStatus = page.locator('[data-testid="invoice-status"], .invoice-status');
    this.invoiceAmount = page.locator('[data-testid="total-amount"]');
    this.invoiceBalance = page.locator('[data-testid="balance"]');
    this.receivePaymentButton = page.locator('[data-testid="record-payment-button"], [data-testid="receive-payment"], a:has-text("Record Payment"), button:has-text("Receive Payment")');
    this.sendInvoiceButton = page.locator('button:has-text("Send Invoice"), [data-testid="send-invoice"]');

    // Payments
    this.paymentsTable = page.locator('#payments-table table, #payments-table-container table, [data-testid="payments-table"] table');
    this.paymentSearch = page.locator('[data-testid="payment-search"], input[name="q"]');
    this.paymentStatusFilter = page.locator('select[name="status"]');
    this.paymentMethodFilter = page.locator('select[name="method"], select[name="payment_method"]');
    this.newPaymentButton = page.locator(
      '[data-testid="new-payment-button"], [data-testid="new-payment"], a[href*="/ar-payments/new"], a[href*="/ap-payments/new"], a[href*="/payments/new"], a:has-text("Record Payment"), a:has-text("New Payment"), a:has-text("New Receipt")'
    );

    // Payment form
    this.paymentForm = page.locator('form[action*="/payments"], [data-testid="payment-form"]');
    this.paymentAmountInput = page.locator('input[name="amount"]');
    this.paymentMethodSelect = page.locator('select[name="payment_method"]');
    this.paymentDateInput = page.locator('input[name="payment_date"]');
    this.paymentReferenceInput = page.locator('input[name="reference"]');

    // Journal entries
    this.journalEntriesTable = page.locator('#journal-entries-table table, [data-testid="journal-entries-table"]');
    this.journalSearch = page.locator('[data-testid="journal-search"], input[name="q"]');
    this.newJournalEntryButton = page.locator('a[href*="/journal-entries/new"], [data-testid="new-journal-entry"]');

    // Reports
    this.reportContainer = page.locator('.report-container, [data-testid="report-container"]');
    this.reportPeriodSelect = page.locator('select[name="period"], [data-testid="period-select"]');
    this.reportExportButton = page.locator('button:has-text("Export"), [data-testid="export-btn"]');
  }

  // =========================================================================
  // NAVIGATION
  // =========================================================================

  async gotoDashboard(): Promise<void> {
    await this.goto(this.dashboardUrl);
  }

  async gotoInvoices(): Promise<void> {
    await this.goto(this.invoicesUrl);
  }

  async gotoInvoiceCreate(): Promise<void> {
    await this.goto(`${this.invoicesUrl}/new`);
  }

  async gotoInvoice(id: number): Promise<void> {
    await this.goto(`${this.invoicesUrl}/${id}`);
  }

  async gotoARPayments(): Promise<void> {
    await this.goto(this.arPaymentsUrl);
  }

  async gotoAPPayments(): Promise<void> {
    await this.goto(this.apPaymentsUrl);
  }

  async gotoJournalEntries(): Promise<void> {
    await this.goto(this.journalEntriesUrl);
  }

  async gotoReport(reportType: 'balance-sheet' | 'income-statement' | 'trial-balance' | 'cash-flow'): Promise<void> {
    await this.goto(`${this.reportsUrl}/${reportType}`);
  }

  async gotoAging(type: 'ar' | 'ap'): Promise<void> {
    await this.goto(`/accounting/aging/${type}`);
  }

  // =========================================================================
  // INVOICES
  // =========================================================================

  async searchInvoices(query: string): Promise<void> {
    await this.invoiceSearch.fill(query);
    await this.page.waitForTimeout(400);
    await this.waitForHtmxComplete();
  }

  async filterInvoicesByStatus(status: string): Promise<void> {
    await this.invoiceStatusFilter.selectOption(status);
    await this.waitForHtmxComplete();
  }

  async getInvoiceCount(): Promise<number> {
    return await this.getTableRowCount(this.invoicesTable);
  }

  async hasInvoices(): Promise<boolean> {
    return (await this.invoicesTable.locator('tbody tr').count()) > 0;
  }

  async ensureHasInvoices(): Promise<boolean> {
    if (await this.hasInvoices()) {
      return true;
    }
    const emptyState = this.page.locator('[data-testid="empty-state"], .empty-state');
    if (await emptyState.count() > 0) {
      return false;
    }
    await this.page.waitForTimeout(300);
    return await this.hasInvoices();
  }

  async clickInvoice(invoiceNumber: string): Promise<void> {
    const link = this.invoicesTable.locator('a', { hasText: invoiceNumber }).first();
    await Promise.all([
      this.page.waitForURL(/\/accounting\/invoices\/\d+/, { timeout: 10000 }),
      link.click(),
    ]);
    await this.waitForPageLoad();
  }

  async createInvoice(data: {
    customerId: string;
    invoiceDate?: string;
    dueDate?: string;
    lines: Array<{ description: string; quantity: number; unitPrice: number }>;
  }): Promise<void> {
    await this.gotoInvoiceCreate();
    await this.customerSelect.selectOption(data.customerId);

    if (data.invoiceDate) {
      await this.invoiceDateInput.fill(data.invoiceDate);
    }
    if (data.dueDate) {
      await this.dueDateInput.fill(data.dueDate);
    }

    for (let i = 0; i < data.lines.length; i++) {
      if (i > 0) {
        await this.htmxClick(this.addLineButton);
      }
      const lineRow = this.lineItemsSection.locator('tr, .line-item').nth(i);
      await lineRow.locator('input[name*="description"], textarea').fill(data.lines[i].description);
      await lineRow.locator('input[name*="quantity"]').fill(data.lines[i].quantity.toString());
      await lineRow.locator('input[name*="unit_price"], input[name*="price"]').fill(data.lines[i].unitPrice.toString());
    }

    await this.htmxSubmitForm(this.invoiceForm);
  }

  async getInvoiceRowData(index: number): Promise<{
    number: string;
    customer: string;
    amount: string;
    status: string;
  }> {
    const row = this.invoicesTable.locator('tbody tr').nth(index);
    const numberLink = row.locator('[data-testid^="invoice-number-"]').first();
    return {
      number: (await numberLink.textContent()) || (await row.locator('td').nth(0).textContent()) || '',
      customer: await row.locator('td').nth(1).textContent() || '',
      amount: await row.locator('td').nth(2).textContent() || '',
      status: await row.locator('.badge, [data-status]').textContent() || '',
    };
  }

  // =========================================================================
  // PAYMENTS
  // =========================================================================

  async searchPayments(query: string): Promise<void> {
    await this.paymentSearch.fill(query);
    await this.page.waitForTimeout(400);
    await this.waitForHtmxComplete();
  }

  async filterPaymentsByStatus(status: string): Promise<void> {
    await this.paymentStatusFilter.selectOption(status);
    await this.waitForHtmxComplete();
  }

  async filterPaymentsByMethod(method: string): Promise<void> {
    await this.paymentMethodFilter.selectOption(method);
    await this.waitForHtmxComplete();
  }

  async getPaymentCount(): Promise<number> {
    return await this.getTableRowCount(this.paymentsTable);
  }

  async hasPayments(): Promise<boolean> {
    return (await this.paymentsTable.locator('tbody tr').count()) > 0;
  }

  async recordPayment(data: {
    amount: number;
    method: string;
    date?: string;
    reference?: string;
  }): Promise<void> {
    await this.paymentAmountInput.fill(data.amount.toString());
    await this.paymentMethodSelect.selectOption(data.method);

    if (data.date) {
      await this.paymentDateInput.fill(data.date);
    }
    if (data.reference) {
      await this.paymentReferenceInput.fill(data.reference);
    }

    await this.htmxSubmitForm(this.paymentForm);
  }

  // =========================================================================
  // JOURNAL ENTRIES
  // =========================================================================

  async searchJournalEntries(query: string): Promise<void> {
    await this.journalSearch.fill(query);
    await this.page.waitForTimeout(400);
    await this.waitForHtmxComplete();
  }

  async getJournalEntryCount(): Promise<number> {
    return await this.getTableRowCount(this.journalEntriesTable);
  }

  async hasJournalEntries(): Promise<boolean> {
    return (await this.journalEntriesTable.locator('tbody tr').count()) > 0;
  }

  // =========================================================================
  // REPORTS
  // =========================================================================

  async selectReportPeriod(period: string): Promise<void> {
    await this.reportPeriodSelect.selectOption(period);
    await this.waitForHtmxComplete();
  }

  async exportReport(format: 'pdf' | 'xlsx' | 'csv' = 'pdf'): Promise<void> {
    const exportBtn = this.page.locator(`button:has-text("${format.toUpperCase()}"), [data-export="${format}"]`);
    await exportBtn.click();
  }

  async expectReportLoaded(): Promise<void> {
    await expect(this.reportContainer).toBeVisible();
  }

  // =========================================================================
  // STATS ASSERTIONS
  // =========================================================================

  async expectStatsVisible(): Promise<void> {
    await expect(this.statTotal).toBeVisible();
  }

  async getStatValue(stat: 'total' | 'outstanding' | 'overdue' | 'paid'): Promise<string> {
    const locator = {
      total: this.statTotal,
      outstanding: this.statOutstanding,
      overdue: this.statOverdue,
      paid: this.statPaid,
    }[stat];
    return await locator.textContent() || '';
  }

  async clickStatCard(stat: 'total' | 'outstanding' | 'overdue' | 'paid'): Promise<void> {
    const locator = {
      total: this.statTotal,
      outstanding: this.statOutstanding,
      overdue: this.statOverdue,
      paid: this.statPaid,
    }[stat];
    await this.htmxClick(locator.locator('..'));
  }

  // =========================================================================
  // ASSERTIONS
  // =========================================================================

  async expectInvoiceStatus(status: string): Promise<void> {
    await expect(this.invoiceStatus).toContainText(status, { ignoreCase: true });
  }

  async expectInvoiceInList(invoiceNumber: string): Promise<void> {
    const row = this.invoicesTable.locator(`tbody tr:has-text("${invoiceNumber}")`);
    await expect(row).toBeVisible();
  }

  async expectPaymentInList(reference: string): Promise<void> {
    const row = this.paymentsTable.locator(`tbody tr:has-text("${reference}")`);
    await expect(row).toBeVisible();
  }

  async expectEmptyState(): Promise<void> {
    const emptyState = this.page.locator('.empty-state, [data-testid="empty-state"]');
    await expect(emptyState).toBeVisible();
  }
}
