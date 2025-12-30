/**
 * Accounting Page Object
 *
 * Page object for accounting/GL views.
 */

import { type Page, type Locator, expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class AccountingPage extends BasePage {
  // Accounting-specific selectors
  readonly chartOfAccounts: Locator;
  readonly accountRows: Locator;
  readonly journalEntries: Locator;
  readonly journalRows: Locator;
  readonly periodFilter: Locator;
  readonly accountFilter: Locator;
  readonly createJournalButton: Locator;
  readonly postButton: Locator;
  readonly reverseButton: Locator;
  readonly lineItemsTable: Locator;
  readonly addLineButton: Locator;
  readonly totalDebits: Locator;
  readonly totalCredits: Locator;
  readonly balanceIndicator: Locator;
  readonly trialBalance: Locator;
  readonly balanceSheet: Locator;
  readonly incomeStatement: Locator;

  constructor(page: Page) {
    super(page);

    this.chartOfAccounts = page.locator('[data-testid="chart-of-accounts"]');
    this.accountRows = page.locator('[data-testid="account-row"]');
    this.journalEntries = page.locator('[data-testid="journal-entries"], table');
    this.journalRows = page.locator('table tbody tr');
    this.periodFilter = page.locator('select').filter({ hasText: /period/i }).first();
    this.accountFilter = page.locator('select').filter({ hasText: /account/i }).first();
    this.createJournalButton = page.getByRole('link', { name: /create.*journal|new.*entry/i });
    this.postButton = page.getByRole('button', { name: /post|finalize/i });
    this.reverseButton = page.getByRole('button', { name: /reverse/i });
    this.lineItemsTable = page.locator('[data-testid="journal-lines"], table.journal-lines');
    this.addLineButton = page.getByRole('button', { name: /add.*line|add.*row/i });
    this.totalDebits = page.locator('[data-testid="total-debits"]');
    this.totalCredits = page.locator('[data-testid="total-credits"]');
    this.balanceIndicator = page.locator('[data-testid="balance-indicator"]');
    this.trialBalance = page.locator('[data-testid="trial-balance"]');
    this.balanceSheet = page.locator('[data-testid="balance-sheet"]');
    this.incomeStatement = page.locator('[data-testid="income-statement"]');
  }

  get url(): string {
    return '/accounting';
  }

  /**
   * Navigate to chart of accounts
   */
  async gotoChartOfAccounts(): Promise<void> {
    await this.page.goto('/accounting/chart-of-accounts');
  }

  /**
   * Navigate to journal entries
   */
  async gotoJournalEntries(): Promise<void> {
    await this.page.goto('/accounting/journal-entries');
  }

  /**
   * Navigate to a specific journal entry
   */
  async gotoJournalEntry(entryId: number): Promise<void> {
    await this.page.goto(`/accounting/journal-entries/${entryId}`);
  }

  /**
   * Navigate to trial balance
   */
  async gotoTrialBalance(): Promise<void> {
    await this.page.goto('/accounting/reports/trial-balance');
  }

  /**
   * Navigate to balance sheet
   */
  async gotoBalanceSheet(): Promise<void> {
    await this.page.goto('/accounting/reports/balance-sheet');
  }

  /**
   * Navigate to income statement
   */
  async gotoIncomeStatement(): Promise<void> {
    await this.page.goto('/accounting/reports/income-statement');
  }

  /**
   * Filter by period
   */
  async filterByPeriod(period: string): Promise<void> {
    await this.periodFilter.selectOption({ label: period });
    await this.page.waitForTimeout(500);
  }

  /**
   * Filter by account
   */
  async filterByAccount(accountName: string): Promise<void> {
    await this.accountFilter.selectOption({ label: accountName });
    await this.page.waitForTimeout(500);
  }

  /**
   * Click a journal entry row
   */
  async clickJournalEntry(entryNumber: string): Promise<void> {
    await this.page.getByText(entryNumber).first().click();
  }

  /**
   * Open create journal entry form
   */
  async openCreateJournalEntry(): Promise<void> {
    await this.createJournalButton.click();
  }

  /**
   * Create a journal entry
   */
  async createJournalEntry(data: {
    date: string;
    reference?: string;
    memo?: string;
    lines: Array<{
      account: string;
      debit?: string;
      credit?: string;
      description?: string;
    }>;
  }): Promise<void> {
    await this.openCreateJournalEntry();

    await this.fillField('date', data.date);

    if (data.reference) {
      await this.fillField('reference', data.reference);
    }
    if (data.memo) {
      await this.fillField('memo', data.memo);
    }

    // Add journal lines
    for (let i = 0; i < data.lines.length; i++) {
      if (i > 0) {
        await this.addLineButton.click();
      }
      await this.fillJournalLine(i, data.lines[i]);
    }

    await this.submitForm();
  }

  /**
   * Fill a journal entry line
   */
  async fillJournalLine(index: number, line: {
    account: string;
    debit?: string;
    credit?: string;
    description?: string;
  }): Promise<void> {
    const row = this.lineItemsTable.locator('tbody tr').nth(index);

    // Select account
    const accountSelect = row.locator('select, [data-testid*="account"]').first();
    await accountSelect.click();
    await this.page.getByRole('option', { name: new RegExp(line.account, 'i') }).click();

    if (line.debit) {
      await row.locator('input[name*="debit"], [data-testid*="debit"]').fill(line.debit);
    }
    if (line.credit) {
      await row.locator('input[name*="credit"], [data-testid*="credit"]').fill(line.credit);
    }
    if (line.description) {
      await row.locator('input[name*="description"], [data-testid*="description"]').fill(line.description);
    }
  }

  /**
   * Post a journal entry
   */
  async postJournalEntry(): Promise<void> {
    await this.postButton.click();
    await this.confirmModal();
  }

  /**
   * Reverse a journal entry
   */
  async reverseJournalEntry(): Promise<void> {
    await this.reverseButton.click();
    await this.confirmModal();
  }

  /**
   * Get total debits
   */
  async getTotalDebits(): Promise<string> {
    return await this.totalDebits.textContent() || '0';
  }

  /**
   * Get total credits
   */
  async getTotalCredits(): Promise<string> {
    return await this.totalCredits.textContent() || '0';
  }

  /**
   * Check if journal entry is balanced
   */
  async isBalanced(): Promise<boolean> {
    const debits = await this.getTotalDebits();
    const credits = await this.getTotalCredits();
    return debits === credits;
  }

  /**
   * Verify journal entry status
   */
  async expectStatus(status: string): Promise<void> {
    await expect(this.page.getByText(new RegExp(status, 'i'))).toBeVisible();
  }

  /**
   * Verify account balance in trial balance
   */
  async expectAccountBalance(accountName: string, balance: string): Promise<void> {
    const row = this.page.locator('tr').filter({ hasText: accountName });
    await expect(row).toContainText(balance);
  }

  /**
   * Verify entry is posted
   */
  async expectPosted(): Promise<void> {
    await expect(this.page.getByText(/posted/i)).toBeVisible();
  }

  /**
   * Verify entry is balanced (visual indicator)
   */
  async expectBalanced(): Promise<void> {
    await expect(this.balanceIndicator.getByText(/balanced/i)).toBeVisible();
  }
}

export default AccountingPage;
