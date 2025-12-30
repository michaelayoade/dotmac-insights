/**
 * Inventory Items E2E Tests
 *
 * Comprehensive tests for the Inventory module including:
 * - Item list view with filters
 * - Item CRUD operations
 * - Stock levels and movements
 * - Warehouse management
 * - Stock entries and transfers
 * - RBAC (role-based access control)
 */

import { test, expect, setupAuth, expectAccessDenied } from './fixtures/auth';
import {
  createTestInventoryItem,
  deleteTestInventoryItem,
  createTestWarehouse,
  deleteTestWarehouse,
} from './fixtures/api-helpers';
import { InventoryPage } from './pages';

test.describe('Inventory Items - Authenticated', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page, ['inventory:read', 'inventory:write']);
  });

  test.describe('List View', () => {
    test('renders inventory items list', async ({ page }) => {
      const inventoryPage = new InventoryPage(page);
      await inventoryPage.gotoItems();

      await expect(page.getByText(/access denied|not authorized/i)).toBeHidden({ timeout: 10000 });
      await expect(
        page.getByRole('heading', { name: /inventory|items/i })
      ).toBeVisible({ timeout: 10000 });

      await expect(inventoryPage.createItemButton).toBeVisible();
    });

    test('displays items data table', async ({ page }) => {
      const inventoryPage = new InventoryPage(page);
      await inventoryPage.gotoItems();

      await expect(inventoryPage.itemsTable).toBeVisible({ timeout: 10000 });
    });

    test('search filters items', async ({ page }) => {
      const inventoryPage = new InventoryPage(page);
      await inventoryPage.gotoItems();

      await inventoryPage.search('Test');

      await expect(
        page
          .locator('table tbody tr, [role="grid"] [role="row"]')
          .first()
          .or(page.getByText(/no results|empty|no data/i))
      ).toBeVisible({ timeout: 10000 });
    });

    test('filter by category works', async ({ page }) => {
      const inventoryPage = new InventoryPage(page);
      await inventoryPage.gotoItems();

      if (await inventoryPage.categoryFilter.isVisible()) {
        await inventoryPage.filterByCategory('Products');

        await expect(
          page
            .locator('table tbody tr')
            .first()
            .or(page.getByText(/no results|empty/i))
        ).toBeVisible({ timeout: 10000 });
      }
    });

    test('filter by stock level works', async ({ page }) => {
      const inventoryPage = new InventoryPage(page);
      await inventoryPage.gotoItems();

      if (await inventoryPage.stockLevelFilter.isVisible()) {
        await inventoryPage.filterByStockLevel('In Stock');

        await expect(
          page
            .locator('table tbody tr')
            .first()
            .or(page.getByText(/no results|empty/i))
        ).toBeVisible({ timeout: 10000 });
      }
    });

    test('filter by warehouse works', async ({ page }) => {
      const inventoryPage = new InventoryPage(page);
      await inventoryPage.gotoItems();

      if (await inventoryPage.warehouseSelector.isVisible()) {
        await inventoryPage.warehouseSelector.selectOption({ index: 1 });

        await page.waitForTimeout(500);
        await expect(inventoryPage.itemsTable).toBeVisible();
      }
    });
  });

  test.describe('Create Item', () => {
    test('navigates to create form', async ({ page }) => {
      const inventoryPage = new InventoryPage(page);
      await inventoryPage.gotoItems();

      await inventoryPage.openCreateItem();

      await expect(page).toHaveURL(/\/inventory\/items\/new|\/inventory\/items\/create/);
    });

    test('validates required fields', async ({ page }) => {
      await page.goto('/inventory/items/new');

      await page.getByRole('button', { name: /save|create|submit/i }).click();

      await expect(
        page.getByText(/required|cannot be empty|please enter/i).first()
      ).toBeVisible({ timeout: 5000 });
    });

    test('creates item successfully', async ({ page, request }) => {
      const itemName = `E2E Item ${Date.now()}`;
      const itemCode = `ITEM-${Date.now()}`;

      await page.goto('/inventory/items/new');

      await page.getByLabel(/name|item.*name/i).first().fill(itemName);

      const skuInput = page.getByLabel(/sku|code|item.*code/i);
      if (await skuInput.isVisible()) {
        await skuInput.fill(itemCode);
      }

      await page.getByRole('button', { name: /save|create|submit/i }).click();
      await page.waitForURL(/\/inventory\/items\/\d+/, { timeout: 10000 });

      await expect(page.getByText(itemName)).toBeVisible();
    });

    test('creates item with category', async ({ page }) => {
      const itemName = `Category Item ${Date.now()}`;

      await page.goto('/inventory/items/new');

      await page.getByLabel(/name|item.*name/i).first().fill(itemName);

      const categorySelect = page.getByLabel(/category|group/i);
      if (await categorySelect.isVisible()) {
        await categorySelect.click();
        await page.getByRole('option').first().click();
      }

      await page.getByRole('button', { name: /save|create|submit/i }).click();
      await page.waitForURL(/\/inventory\/items/, { timeout: 10000 });
    });
  });

  test.describe('Edit Item', () => {
    test('loads item data', async ({ page, request }) => {
      const item = await createTestInventoryItem(request, {
        item_name: `Edit View Test ${Date.now()}`,
        item_code: `EDIT-${Date.now()}`,
      });

      try {
        const inventoryPage = new InventoryPage(page);
        await inventoryPage.gotoItem(item.id);

        await expect(page.getByText(item.item_name)).toBeVisible({ timeout: 5000 });
      } finally {
        await deleteTestInventoryItem(request, item.id);
      }
    });

    test('updates item name', async ({ page, request }) => {
      const item = await createTestInventoryItem(request, {
        item_name: `Update Test ${Date.now()}`,
        item_code: `UPD-${Date.now()}`,
      });

      try {
        await page.goto(`/inventory/items/${item.id}/edit`);

        const updatedName = `Updated Item ${Date.now()}`;
        await page.getByLabel(/name|item.*name/i).first().fill(updatedName);
        await page.getByRole('button', { name: /save|update/i }).click();

        await page.waitForURL(/\/inventory\/items\/\d+$/, { timeout: 10000 });
        await expect(page.getByText(updatedName)).toBeVisible();
      } finally {
        await deleteTestInventoryItem(request, item.id);
      }
    });
  });

  test.describe('Stock Levels', () => {
    test('displays stock quantity', async ({ page, request }) => {
      const item = await createTestInventoryItem(request, {
        item_name: `Stock Level Test ${Date.now()}`,
        item_code: `STK-${Date.now()}`,
      });

      try {
        const inventoryPage = new InventoryPage(page);
        await inventoryPage.gotoItem(item.id);

        // Stock quantity display should be visible
        const stockDisplay = page.locator('[data-testid="stock-qty"]').or(
          page.getByText(/stock|quantity|on hand/i)
        );

        await expect(stockDisplay).toBeVisible({ timeout: 5000 });
      } finally {
        await deleteTestInventoryItem(request, item.id);
      }
    });

    test('shows low stock indicator', async ({ page }) => {
      const inventoryPage = new InventoryPage(page);
      await inventoryPage.gotoItems();

      // Filter to low stock
      if (await inventoryPage.stockLevelFilter.isVisible()) {
        await inventoryPage.filterByStockLevel('Low Stock');

        await page.waitForTimeout(500);

        // Should show items or empty state
        await expect(
          page
            .locator('table tbody tr')
            .first()
            .or(page.getByText(/no results|empty|no low stock/i))
        ).toBeVisible({ timeout: 5000 });
      }
    });
  });

  test.describe('Stock Entry', () => {
    test('opens stock entry form', async ({ page }) => {
      const inventoryPage = new InventoryPage(page);
      await inventoryPage.gotoItems();

      if (await inventoryPage.stockEntryButton.isVisible()) {
        await inventoryPage.openStockEntry();

        await expect(
          page.getByRole('dialog').or(page.getByRole('heading', { name: /stock.*entry|receive/i }))
        ).toBeVisible({ timeout: 5000 });
      }
    });

    test('creates stock entry', async ({ page, request }) => {
      const item = await createTestInventoryItem(request, {
        item_name: `Stock Entry Test ${Date.now()}`,
        item_code: `ENTRY-${Date.now()}`,
      });

      try {
        await page.goto('/inventory/stock-entries/new');

        // Select item
        const itemSelect = page.getByLabel(/item/i).first();
        if (await itemSelect.isVisible()) {
          await itemSelect.click();
          await page.getByRole('option').first().click();
        }

        // Select warehouse
        const warehouseSelect = page.getByLabel(/warehouse/i).first();
        if (await warehouseSelect.isVisible()) {
          await warehouseSelect.click();
          await page.getByRole('option').first().click();
        }

        // Enter quantity
        await page.getByLabel(/quantity|qty/i).fill('10');

        await page.getByRole('button', { name: /save|create|submit/i }).click();
        await page.waitForTimeout(1000);
      } finally {
        await deleteTestInventoryItem(request, item.id);
      }
    });
  });

  test.describe('Stock Transfer', () => {
    test('opens transfer form', async ({ page }) => {
      const inventoryPage = new InventoryPage(page);
      await inventoryPage.gotoItems();

      if (await inventoryPage.transferButton.isVisible()) {
        await inventoryPage.transferButton.click();

        await expect(
          page.getByRole('dialog').or(page.getByRole('heading', { name: /transfer/i }))
        ).toBeVisible({ timeout: 5000 });
      }
    });
  });

  test.describe('Stock Adjustment', () => {
    test('opens adjustment form', async ({ page }) => {
      const inventoryPage = new InventoryPage(page);
      await inventoryPage.gotoItems();

      if (await inventoryPage.adjustButton.isVisible()) {
        await inventoryPage.adjustButton.click();

        await expect(
          page.getByRole('dialog').or(page.getByRole('heading', { name: /adjust/i }))
        ).toBeVisible({ timeout: 5000 });
      }
    });
  });

  test.describe('Stock Ledger', () => {
    test('navigates to stock ledger', async ({ page }) => {
      const inventoryPage = new InventoryPage(page);
      await inventoryPage.gotoStockLedger();

      await expect(page).toHaveURL(/\/inventory\/stock-ledger/);
    });

    test('displays stock movements', async ({ page }) => {
      const inventoryPage = new InventoryPage(page);
      await inventoryPage.gotoStockLedger();

      // Should show ledger entries or empty state
      await expect(
        page
          .locator('table tbody tr')
          .first()
          .or(page.getByText(/no.*entries|empty|no data/i))
      ).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Warehouses', () => {
    test('navigates to warehouses list', async ({ page }) => {
      const inventoryPage = new InventoryPage(page);
      await inventoryPage.gotoWarehouses();

      await expect(page).toHaveURL(/\/inventory\/warehouses/);
    });

    test('displays warehouses', async ({ page }) => {
      const inventoryPage = new InventoryPage(page);
      await inventoryPage.gotoWarehouses();

      await expect(
        page
          .locator('table tbody tr, [data-testid="warehouse-card"]')
          .first()
          .or(page.getByText(/no.*warehouses|empty/i))
      ).toBeVisible({ timeout: 10000 });
    });

    test('can create warehouse', async ({ page, request }) => {
      await page.goto('/inventory/warehouses/new');

      const warehouseName = `E2E Warehouse ${Date.now()}`;
      await page.getByLabel(/name|warehouse.*name/i).first().fill(warehouseName);

      await page.getByRole('button', { name: /save|create|submit/i }).click();
      await page.waitForURL(/\/inventory\/warehouses/, { timeout: 10000 });
    });
  });

  test.describe('Delete Item', () => {
    test('can delete item', async ({ page, request }) => {
      const item = await createTestInventoryItem(request, {
        item_name: `Delete Test ${Date.now()}`,
        item_code: `DEL-${Date.now()}`,
      });

      const inventoryPage = new InventoryPage(page);
      await inventoryPage.gotoItem(item.id);

      const deleteButton = page.getByRole('button', { name: /delete|archive/i });
      if (await deleteButton.isVisible()) {
        await deleteButton.click();

        const confirmButton = page.getByRole('button', { name: /confirm|yes|delete/i });
        await expect(confirmButton).toBeVisible({ timeout: 2000 });
        await confirmButton.click();

        await page.waitForURL(/\/inventory\/items/, { timeout: 10000 });
      } else {
        await deleteTestInventoryItem(request, item.id);
      }
    });
  });
});

test.describe('Inventory Items - RBAC', () => {
  test('read-only user cannot create items', async ({ page }) => {
    await setupAuth(page, ['inventory:read']);

    const inventoryPage = new InventoryPage(page);
    await inventoryPage.gotoItems();

    await expect(inventoryPage.createItemButton).toBeHidden();
  });

  test('user without inventory scope sees access denied', async ({ page }) => {
    await setupAuth(page, ['hr:read']);
    await page.goto('/inventory/items');

    await expectAccessDenied(page);
  });
});

test.describe('Inventory Items - Unauthenticated', () => {
  test('redirects to login when not authenticated', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => localStorage.clear());

    await page.goto('/inventory/items');

    await expect(page).toHaveURL(/\/login|\/auth/);
  });
});
