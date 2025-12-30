/**
 * Inventory Page Object
 *
 * Page object for inventory management views.
 */

import { type Page, type Locator, expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class InventoryPage extends BasePage {
  // Inventory-specific selectors
  readonly itemsTable: Locator;
  readonly warehouseSelector: Locator;
  readonly categoryFilter: Locator;
  readonly stockLevelFilter: Locator;
  readonly createItemButton: Locator;
  readonly stockEntryButton: Locator;
  readonly transferButton: Locator;
  readonly adjustButton: Locator;
  readonly stockLedger: Locator;
  readonly barcodeScanner: Locator;

  constructor(page: Page) {
    super(page);

    this.itemsTable = page.locator('[data-testid="items-table"], table');
    this.warehouseSelector = page.locator('select').filter({ hasText: /warehouse/i }).first();
    this.categoryFilter = page.locator('select').filter({ hasText: /category/i }).first();
    this.stockLevelFilter = page.locator('select').filter({ hasText: /stock.*level/i }).first();
    this.createItemButton = page.getByRole('link', { name: /create item|new item|add item/i });
    this.stockEntryButton = page.getByRole('button', { name: /stock entry|receive stock/i });
    this.transferButton = page.getByRole('button', { name: /transfer/i });
    this.adjustButton = page.getByRole('button', { name: /adjust/i });
    this.stockLedger = page.locator('[data-testid="stock-ledger"]');
    this.barcodeScanner = page.locator('[data-testid="barcode-scanner"]');
  }

  get url(): string {
    return '/inventory';
  }

  /**
   * Navigate to items list
   */
  async gotoItems(): Promise<void> {
    await this.page.goto('/inventory/items');
  }

  /**
   * Navigate to warehouses
   */
  async gotoWarehouses(): Promise<void> {
    await this.page.goto('/inventory/warehouses');
  }

  /**
   * Navigate to a specific item
   */
  async gotoItem(itemId: number): Promise<void> {
    await this.page.goto(`/inventory/items/${itemId}`);
  }

  /**
   * Navigate to stock ledger
   */
  async gotoStockLedger(): Promise<void> {
    await this.page.goto('/inventory/stock-ledger');
  }

  /**
   * Filter by warehouse
   */
  async filterByWarehouse(warehouseName: string): Promise<void> {
    await this.warehouseSelector.selectOption({ label: warehouseName });
    await this.page.waitForTimeout(500);
  }

  /**
   * Filter by category
   */
  async filterByCategory(category: string): Promise<void> {
    await this.categoryFilter.selectOption({ label: category });
    await this.page.waitForTimeout(500);
  }

  /**
   * Filter by stock level
   */
  async filterByStockLevel(level: 'All' | 'In Stock' | 'Low Stock' | 'Out of Stock'): Promise<void> {
    await this.stockLevelFilter.selectOption({ label: level });
    await this.page.waitForTimeout(500);
  }

  /**
   * Click an item in the list
   */
  async clickItem(itemName: string): Promise<void> {
    await this.page.getByText(itemName).first().click();
  }

  /**
   * Open create item form
   */
  async openCreateItem(): Promise<void> {
    await this.createItemButton.click();
  }

  /**
   * Create a new inventory item
   */
  async createItem(data: {
    name: string;
    sku: string;
    category?: string;
    unit?: string;
    reorderLevel?: string;
    description?: string;
  }): Promise<void> {
    await this.openCreateItem();

    await this.fillField('name', data.name);
    await this.fillField('sku', data.sku);

    if (data.category) {
      await this.selectDropdown('category', data.category);
    }
    if (data.unit) {
      await this.selectDropdown('unit', data.unit);
    }
    if (data.reorderLevel) {
      await this.fillField('reorder level', data.reorderLevel);
    }
    if (data.description) {
      await this.fillField('description', data.description);
    }

    await this.submitForm();
  }

  /**
   * Open stock entry form
   */
  async openStockEntry(): Promise<void> {
    await this.stockEntryButton.click();
  }

  /**
   * Create a stock entry (receive stock)
   */
  async createStockEntry(data: {
    item: string;
    warehouse: string;
    quantity: string;
    rate?: string;
    reference?: string;
  }): Promise<void> {
    await this.openStockEntry();

    await this.selectDropdown('item', data.item);
    await this.selectDropdown('warehouse', data.warehouse);
    await this.fillField('quantity', data.quantity);

    if (data.rate) {
      await this.fillField('rate', data.rate);
    }
    if (data.reference) {
      await this.fillField('reference', data.reference);
    }

    await this.submitForm();
  }

  /**
   * Create a stock transfer
   */
  async createStockTransfer(data: {
    item: string;
    fromWarehouse: string;
    toWarehouse: string;
    quantity: string;
  }): Promise<void> {
    await this.transferButton.click();

    await this.selectDropdown('item', data.item);
    await this.selectDropdown('from warehouse', data.fromWarehouse);
    await this.selectDropdown('to warehouse', data.toWarehouse);
    await this.fillField('quantity', data.quantity);

    await this.submitForm();
  }

  /**
   * Create a stock adjustment
   */
  async createStockAdjustment(data: {
    item: string;
    warehouse: string;
    quantity: string;
    reason: string;
  }): Promise<void> {
    await this.adjustButton.click();

    await this.selectDropdown('item', data.item);
    await this.selectDropdown('warehouse', data.warehouse);
    await this.fillField('quantity', data.quantity);
    await this.fillField('reason', data.reason);

    await this.submitForm();
  }

  /**
   * Get current stock quantity for an item
   */
  async getStockQuantity(itemName: string): Promise<string> {
    const row = this.page.locator('tr').filter({ hasText: itemName });
    const qtyCell = row.locator('[data-testid="stock-qty"]').or(
      row.locator('td').nth(2)
    );
    return await qtyCell.textContent() || '0';
  }

  /**
   * Verify item exists in list
   */
  async expectItemInList(itemName: string): Promise<void> {
    await expect(this.page.getByText(itemName)).toBeVisible();
  }

  /**
   * Verify stock level
   */
  async expectStockLevel(itemName: string, quantity: string): Promise<void> {
    const row = this.page.locator('tr').filter({ hasText: itemName });
    await expect(row).toContainText(quantity);
  }

  /**
   * Verify low stock warning
   */
  async expectLowStockWarning(itemName: string): Promise<void> {
    const row = this.page.locator('tr').filter({ hasText: itemName });
    await expect(row.getByText(/low stock|reorder/i)).toBeVisible();
  }
}

export default InventoryPage;
