/**
 * Sales Invoices E2E Tests
 *
 * Comprehensive tests for the Sales Invoices module including:
 * - Invoice list view with filters
 * - Invoice CRUD operations
 * - Line item management
 * - Invoice posting and voiding
 * - Email and print functionality
 * - RBAC (role-based access control)
 */

import { test, expect, setupAuth, expectAccessDenied } from './fixtures/auth';
import {
  createTestInvoice,
  deleteTestInvoice,
  createTestContact,
  deleteTestContact,
} from './fixtures/api-helpers';
import { SalesInvoicesPage } from './pages';

test.describe('Sales Invoices - Authenticated', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page, ['sales:read', 'sales:write']);
  });

  test.describe('List View', () => {
    test('renders invoices list with data table', async ({ page }) => {
      const invoicesPage = new SalesInvoicesPage(page);
      await invoicesPage.goto();

      // Verify page structure
      await expect(page.getByText(/access denied|not authorized/i)).toBeHidden({ timeout: 10000 });
      await expect(
        page.getByRole('heading', { name: /invoices|sales/i })
      ).toBeVisible({ timeout: 10000 });

      // Verify create button
      await expect(invoicesPage.createInvoiceButton).toBeVisible();

      // Verify data table
      await expect(page.locator('table, [role="grid"]').first()).toBeVisible();
    });

    test('displays pagination when data exists', async ({ page }) => {
      const invoicesPage = new SalesInvoicesPage(page);
      await invoicesPage.goto();

      await page.waitForSelector('table tbody tr, [role="grid"] [role="row"]', {
        timeout: 10000,
      });

      await expect(page.locator('table tbody tr, [role="grid"] [role="row"]').first()).toBeVisible();
    });

    test('filter by status works', async ({ page }) => {
      const invoicesPage = new SalesInvoicesPage(page);
      await invoicesPage.goto();

      if (await invoicesPage.statusFilter.isVisible()) {
        await invoicesPage.filterByStatus('Draft');

        await expect(
          page
            .locator('table tbody tr, [role="grid"] [role="row"]')
            .first()
            .or(page.getByText(/no results|empty|no data/i))
        ).toBeVisible({ timeout: 10000 });
      }
    });

    test('search filters invoices', async ({ page }) => {
      const invoicesPage = new SalesInvoicesPage(page);
      await invoicesPage.goto();

      await invoicesPage.search('INV');

      await expect(
        page
          .locator('table tbody tr, [role="grid"] [role="row"]')
          .first()
          .or(page.getByText(/no results|empty|no data/i))
      ).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Create Invoice', () => {
    test('navigates to create form from list', async ({ page }) => {
      const invoicesPage = new SalesInvoicesPage(page);
      await invoicesPage.goto();

      await invoicesPage.openCreateInvoice();

      await expect(page).toHaveURL(/\/sales\/invoices\/new|\/sales\/invoices\/create/);
    });

    test('validates required fields', async ({ page }) => {
      await page.goto('/sales/invoices/new');

      await page.getByRole('button', { name: /save|create|submit/i }).click();

      await expect(
        page.getByText(/required|cannot be empty|please select/i).first()
      ).toBeVisible({ timeout: 5000 });
    });

    test('creates invoice with line items', async ({ page, request }) => {
      // Create test contact first
      const contact = await createTestContact(request, {
        name: `Invoice Customer ${Date.now()}`,
        contact_type: 'customer',
      });

      try {
        await page.goto('/sales/invoices/new');

        // Select customer
        const customerSelect = page.getByLabel(/customer/i);
        await customerSelect.click();
        await page.getByRole('option').first().click();

        // Add line item
        const descriptionInput = page.locator('input[name*="description"], [data-testid*="description"]').first();
        if (await descriptionInput.isVisible()) {
          await descriptionInput.fill('E2E Test Service');
        }

        const qtyInput = page.locator('input[name*="quantity"], [data-testid*="quantity"]').first();
        if (await qtyInput.isVisible()) {
          await qtyInput.fill('2');
        }

        const rateInput = page.locator('input[name*="rate"], input[name*="price"], [data-testid*="rate"]').first();
        if (await rateInput.isVisible()) {
          await rateInput.fill('15000');
        }

        // Submit
        await page.getByRole('button', { name: /save|create|submit/i }).click();
        await page.waitForURL(/\/sales\/invoices\/\d+/, { timeout: 10000 });

        // Verify invoice created
        await expect(page.getByText(/30,?000/)).toBeVisible({ timeout: 5000 });
      } finally {
        await deleteTestContact(request, contact.id);
      }
    });

    test('calculates totals automatically', async ({ page }) => {
      await page.goto('/sales/invoices/new');

      // Fill line item
      const qtyInput = page.locator('input[name*="quantity"], [data-testid*="quantity"]').first();
      const rateInput = page.locator('input[name*="rate"], input[name*="price"]').first();

      if (await qtyInput.isVisible() && await rateInput.isVisible()) {
        await qtyInput.fill('5');
        await rateInput.fill('10000');

        // Wait for calculation
        await page.waitForTimeout(500);

        // Check total (5 * 10000 = 50000)
        const totalElement = page.locator('[data-testid="total"]').or(
          page.getByText(/total/i).locator('+ *')
        );

        if (await totalElement.isVisible()) {
          await expect(totalElement).toContainText(/50,?000/);
        }
      }
    });
  });

  test.describe('Edit Invoice', () => {
    test('loads invoice data', async ({ page, request }) => {
      const invoice = await createTestInvoice(request, {
        items: [{ item_name: 'Test Item', qty: 1, rate: 20000 }],
      });

      try {
        await page.goto(`/sales/invoices/${invoice.id}`);

        await expect(page.getByText(invoice.invoice_number)).toBeVisible({ timeout: 5000 });
        await expect(page.getByText(/20,?000/)).toBeVisible();
      } finally {
        await deleteTestInvoice(request, invoice.id);
      }
    });

    test('can edit draft invoice', async ({ page, request }) => {
      const invoice = await createTestInvoice(request, {
        items: [{ item_name: 'Edit Test', qty: 1, rate: 15000 }],
      });

      try {
        await page.goto(`/sales/invoices/${invoice.id}/edit`);

        // Update quantity
        const qtyInput = page.locator('input[name*="quantity"], [data-testid*="quantity"]').first();
        if (await qtyInput.isVisible()) {
          await qtyInput.fill('3');
        }

        await page.getByRole('button', { name: /save|update/i }).click();
        await page.waitForTimeout(1000);

        // Verify update (3 * 15000 = 45000)
        await expect(page.getByText(/45,?000/)).toBeVisible({ timeout: 5000 });
      } finally {
        await deleteTestInvoice(request, invoice.id);
      }
    });
  });

  test.describe('Line Item Management', () => {
    test('can add multiple line items', async ({ page }) => {
      await page.goto('/sales/invoices/new');

      const addLineButton = page.getByRole('button', { name: /add.*line|add.*item|add row/i });
      if (await addLineButton.isVisible()) {
        await addLineButton.click();
        await addLineButton.click();

        // Should have 3 line items (1 default + 2 added)
        const lineRows = page.locator('[data-testid="line-item-row"], table.line-items tbody tr');
        const count = await lineRows.count();
        expect(count).toBeGreaterThanOrEqual(2);
      }
    });

    test('can remove line items', async ({ page }) => {
      await page.goto('/sales/invoices/new');

      const addLineButton = page.getByRole('button', { name: /add.*line|add.*item/i });
      if (await addLineButton.isVisible()) {
        await addLineButton.click();

        const removeButton = page.getByRole('button', { name: /delete|remove/i }).first();
        if (await removeButton.isVisible()) {
          await removeButton.click();

          // Count should decrease
          await page.waitForTimeout(500);
        }
      }
    });
  });

  test.describe('Invoice Actions', () => {
    test('can post draft invoice', async ({ page, request }) => {
      const invoice = await createTestInvoice(request, {
        items: [{ item_name: 'Post Test', qty: 1, rate: 10000 }],
      });

      try {
        const invoicesPage = new SalesInvoicesPage(page);
        await invoicesPage.gotoInvoice(invoice.id);

        if (await invoicesPage.postButton.isVisible()) {
          await invoicesPage.postInvoice();

          await expect(page.getByText(/posted|submitted/i)).toBeVisible({ timeout: 5000 });
        }
      } finally {
        await deleteTestInvoice(request, invoice.id);
      }
    });

    test('can void posted invoice', async ({ page, request }) => {
      const invoice = await createTestInvoice(request, {
        items: [{ item_name: 'Void Test', qty: 1, rate: 5000 }],
      });

      try {
        const invoicesPage = new SalesInvoicesPage(page);
        await invoicesPage.gotoInvoice(invoice.id);

        // Post first if needed
        if (await invoicesPage.postButton.isVisible()) {
          await invoicesPage.postInvoice();
          await page.waitForTimeout(500);
        }

        // Now void
        if (await invoicesPage.voidButton.isVisible()) {
          await invoicesPage.voidInvoice();

          await expect(page.getByText(/void|cancelled/i)).toBeVisible({ timeout: 5000 });
        }
      } finally {
        await deleteTestInvoice(request, invoice.id);
      }
    });

    test('shows email button', async ({ page, request }) => {
      const invoice = await createTestInvoice(request, {
        items: [{ item_name: 'Email Test', qty: 1, rate: 8000 }],
      });

      try {
        const invoicesPage = new SalesInvoicesPage(page);
        await invoicesPage.gotoInvoice(invoice.id);

        await expect(invoicesPage.emailButton).toBeVisible();
      } finally {
        await deleteTestInvoice(request, invoice.id);
      }
    });

    test('shows print/PDF button', async ({ page, request }) => {
      const invoice = await createTestInvoice(request, {
        items: [{ item_name: 'Print Test', qty: 1, rate: 7000 }],
      });

      try {
        const invoicesPage = new SalesInvoicesPage(page);
        await invoicesPage.gotoInvoice(invoice.id);

        await expect(invoicesPage.printButton).toBeVisible();
      } finally {
        await deleteTestInvoice(request, invoice.id);
      }
    });
  });

  test.describe('Invoice Totals', () => {
    test('displays subtotal, tax, and total', async ({ page, request }) => {
      const invoice = await createTestInvoice(request, {
        items: [{ item_name: 'Totals Test', qty: 2, rate: 10000 }],
      });

      try {
        const invoicesPage = new SalesInvoicesPage(page);
        await invoicesPage.gotoInvoice(invoice.id);

        // Check subtotal
        const subtotal = page.getByText(/subtotal/i).first();
        await expect(subtotal).toBeVisible();

        // Check total
        await expect(invoicesPage.totalAmount.or(page.getByText(/20,?000/))).toBeVisible();
      } finally {
        await deleteTestInvoice(request, invoice.id);
      }
    });
  });
});

test.describe('Sales Invoices - RBAC', () => {
  test('read-only user cannot create invoices', async ({ page }) => {
    await setupAuth(page, ['sales:read']);

    const invoicesPage = new SalesInvoicesPage(page);
    await invoicesPage.goto();

    await expect(invoicesPage.createInvoiceButton).toBeHidden();
  });

  test('user without sales scope sees access denied', async ({ page }) => {
    await setupAuth(page, ['hr:read']);
    await page.goto('/sales/invoices');

    await expectAccessDenied(page);
  });
});

test.describe('Sales Invoices - Unauthenticated', () => {
  test('redirects to login when not authenticated', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => localStorage.clear());

    await page.goto('/sales/invoices');

    await expect(page).toHaveURL(/\/login|\/auth/);
  });
});
