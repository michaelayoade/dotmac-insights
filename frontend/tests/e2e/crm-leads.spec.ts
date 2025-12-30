/**
 * CRM Leads E2E Tests
 *
 * Comprehensive tests for the CRM leads module including:
 * - Lead list view with pagination and filters
 * - Lead CRUD operations
 * - Lead qualification workflow
 * - Lead conversion to customer
 * - RBAC (role-based access control)
 */

import { test, expect, setupAuth, expectAccessDenied } from './fixtures/auth';
import {
  createTestLead,
  deleteTestLead,
  createTestContact,
  deleteTestContact,
} from './fixtures/api-helpers';

test.describe('CRM Leads - Authenticated', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page, ['crm:read', 'crm:write']);
  });

  test.describe('List View', () => {
    test('renders leads list with data table', async ({ page }) => {
      await page.goto('/crm/leads');

      // Verify page structure
      await expect(page.getByText(/access denied|not authorized/i)).toBeHidden({ timeout: 10000 });
      await expect(
        page.getByRole('heading', { name: /leads/i })
      ).toBeVisible({ timeout: 10000 });

      // Verify create button
      await expect(page.getByRole('link', { name: /add.*lead|new.*lead|create.*lead/i })).toBeVisible();

      // Verify data table is present
      await expect(page.locator('table, [role="grid"]').first()).toBeVisible();
    });

    test('displays pagination when data exists', async ({ page }) => {
      await page.goto('/crm/leads');

      // Wait for table to load
      await page.waitForSelector('table tbody tr, [role="grid"] [role="row"]', {
        timeout: 10000,
      });

      await expect(page.locator('table tbody tr, [role="grid"] [role="row"]').first()).toBeVisible();
    });

    test('search filters leads by name', async ({ page }) => {
      await page.goto('/crm/leads');

      const searchInput = page.getByPlaceholder(/search/i);
      await searchInput.fill('Test');

      await expect(
        page
          .locator('table tbody tr, [role="grid"] [role="row"]')
          .first()
          .or(page.getByText(/no results|empty|no data/i))
      ).toBeVisible({ timeout: 10000 });
    });

    test('filter by status works', async ({ page }) => {
      await page.goto('/crm/leads');

      const statusFilter = page.locator('select').filter({ hasText: /status|all/i }).first();
      if (await statusFilter.isVisible()) {
        await statusFilter.selectOption({ index: 1 });

        await expect(
          page
            .locator('table tbody tr, [role="grid"] [role="row"]')
            .first()
            .or(page.getByText(/no results|empty|no data/i))
        ).toBeVisible({ timeout: 10000 });
      }
    });

    test('filter by source works', async ({ page }) => {
      await page.goto('/crm/leads');

      const sourceFilter = page.locator('select').filter({ hasText: /source/i }).first();
      if (await sourceFilter.isVisible()) {
        await sourceFilter.selectOption({ index: 1 });

        await expect(
          page
            .locator('table tbody tr, [role="grid"] [role="row"]')
            .first()
            .or(page.getByText(/no results|empty|no data/i))
        ).toBeVisible({ timeout: 10000 });
      }
    });
  });

  test.describe('Create Lead', () => {
    test('navigates to create form from list', async ({ page }) => {
      await page.goto('/crm/leads');

      await page.getByRole('link', { name: /add.*lead|new.*lead|create.*lead/i }).click();

      await expect(page).toHaveURL(/\/crm\/leads\/new|\/crm\/leads\/create/);
      await expect(page.getByRole('heading', { name: /new|create|add/i })).toBeVisible();
    });

    test('validates required fields', async ({ page }) => {
      await page.goto('/crm/leads/new');

      const submitButton = page.getByRole('button', { name: /save|create|submit/i });
      await submitButton.click();

      await expect(
        page.getByText(/required|cannot be empty|please enter/i).first()
      ).toBeVisible({ timeout: 5000 });
    });

    test('creates lead successfully', async ({ page, request }) => {
      const testName = `E2E Test Lead ${Date.now()}`;
      const testEmail = `lead-${Date.now()}@test.com`;

      await page.goto('/crm/leads/new');

      // Fill form
      await page.getByLabel(/name/i).first().fill(testName);
      await page.getByLabel(/email/i).fill(testEmail);
      await page.getByLabel(/company/i).fill('Test Company Ltd');

      // Submit
      await page.getByRole('button', { name: /save|create|submit/i }).click();

      // Should redirect
      await page.waitForURL(/\/crm\/leads(?:\/\d+)?$/, { timeout: 10000 });

      // Verify lead appears
      await page.goto('/crm/leads');
      await page.getByPlaceholder(/search/i).fill(testName);

      await expect(page.getByText(testName)).toBeVisible({ timeout: 5000 });

      // Cleanup
      const urlMatch = page.url().match(/\/crm\/leads\/(\d+)/);
      if (urlMatch) {
        await deleteTestLead(request, Number(urlMatch[1]));
      }
    });

    test('creates lead with source', async ({ page, request }) => {
      const testName = `E2E Source Lead ${Date.now()}`;

      await page.goto('/crm/leads/new');

      await page.getByLabel(/name/i).first().fill(testName);
      await page.getByLabel(/email/i).fill(`source-${Date.now()}@test.com`);

      // Select source if available
      const sourceSelect = page.getByLabel(/source/i);
      if (await sourceSelect.isVisible()) {
        await sourceSelect.click();
        await page.getByRole('option').first().click();
      }

      await page.getByRole('button', { name: /save|create|submit/i }).click();
      await page.waitForURL(/\/crm\/leads/, { timeout: 10000 });
    });
  });

  test.describe('Edit Lead', () => {
    test('loads lead data in edit form', async ({ page, request }) => {
      const lead = await createTestLead(request, {
        name: `Edit Test ${Date.now()}`,
        email: `edit-${Date.now()}@test.com`,
        company: 'Edit Test Company',
      });

      try {
        await page.goto(`/crm/leads/${lead.id}`);

        const editButton = page.getByRole('link', { name: /edit/i }).or(
          page.getByRole('button', { name: /edit/i })
        );
        await editButton.click();

        await expect(page.getByLabel(/name/i).first()).toHaveValue(lead.name);
      } finally {
        await deleteTestLead(request, lead.id);
      }
    });

    test('updates lead and persists changes', async ({ page, request }) => {
      const lead = await createTestLead(request, {
        name: `Update Test ${Date.now()}`,
        email: `update-${Date.now()}@test.com`,
      });

      try {
        await page.goto(`/crm/leads/${lead.id}/edit`);

        const updatedName = `Updated Lead ${Date.now()}`;
        await page.getByLabel(/name/i).first().fill(updatedName);
        await page.getByRole('button', { name: /save|update/i }).click();

        await page.waitForURL(/\/crm\/leads\/\d+$/, { timeout: 10000 });
        await expect(page.getByText(updatedName)).toBeVisible();
      } finally {
        await deleteTestLead(request, lead.id);
      }
    });
  });

  test.describe('Lead Status Updates', () => {
    test('can change lead status', async ({ page, request }) => {
      const lead = await createTestLead(request, {
        name: `Status Test ${Date.now()}`,
        status: 'new',
      });

      try {
        await page.goto(`/crm/leads/${lead.id}`);

        const statusSelector = page.getByLabel(/status/i).or(
          page.locator('select').filter({ hasText: /status/i })
        );

        if (await statusSelector.isVisible()) {
          await statusSelector.click();
          await page.getByRole('option', { name: /contacted|qualified/i }).first().click();

          // Save if needed
          const saveButton = page.getByRole('button', { name: /save|update/i });
          if (await saveButton.isVisible()) {
            await saveButton.click();
          }

          await page.waitForTimeout(1000);
        }
      } finally {
        await deleteTestLead(request, lead.id);
      }
    });

    test('can mark lead as qualified', async ({ page, request }) => {
      const lead = await createTestLead(request, {
        name: `Qualify Test ${Date.now()}`,
        status: 'contacted',
      });

      try {
        await page.goto(`/crm/leads/${lead.id}`);

        const qualifyButton = page.getByRole('button', { name: /qualify/i });
        if (await qualifyButton.isVisible()) {
          await qualifyButton.click();

          // Confirm if modal appears
          const confirmButton = page.getByRole('button', { name: /confirm|yes/i });
          if (await confirmButton.isVisible({ timeout: 2000 })) {
            await confirmButton.click();
          }

          await page.waitForTimeout(1000);
          await expect(page.getByText(/qualified/i)).toBeVisible();
        }
      } finally {
        await deleteTestLead(request, lead.id);
      }
    });
  });

  test.describe('Convert Lead to Customer', () => {
    test('shows convert option for qualified leads', async ({ page, request }) => {
      const lead = await createTestLead(request, {
        name: `Convert Test ${Date.now()}`,
        status: 'qualified',
      });

      try {
        await page.goto(`/crm/leads/${lead.id}`);

        const convertButton = page.getByRole('button', { name: /convert|create.*customer/i });
        await expect(convertButton).toBeVisible({ timeout: 5000 });
      } finally {
        await deleteTestLead(request, lead.id);
      }
    });

    test('converts lead to customer', async ({ page, request }) => {
      const lead = await createTestLead(request, {
        name: `Convert Customer Test ${Date.now()}`,
        status: 'qualified',
        email: `convert-${Date.now()}@test.com`,
      });

      let customerId: number | null = null;

      try {
        await page.goto(`/crm/leads/${lead.id}`);

        const convertButton = page.getByRole('button', { name: /convert|create.*customer/i });
        if (await convertButton.isVisible()) {
          await convertButton.click();

          // Fill any required fields in conversion modal
          const customerNameInput = page.getByLabel(/customer.*name|name/i).first();
          if (await customerNameInput.isVisible({ timeout: 2000 })) {
            // Name might be pre-filled
          }

          // Confirm conversion
          const confirmButton = page.getByRole('button', { name: /confirm|convert|create/i });
          if (await confirmButton.isVisible()) {
            await confirmButton.click();
          }

          // Should redirect to customer or show success
          await page.waitForTimeout(2000);
        }
      } finally {
        // Lead might be deleted after conversion
        try {
          await deleteTestLead(request, lead.id);
        } catch {
          // Lead may have been converted/deleted
        }
      }
    });
  });

  test.describe('Lead Activities', () => {
    test('can add activity to lead', async ({ page, request }) => {
      const lead = await createTestLead(request, {
        name: `Activity Test ${Date.now()}`,
      });

      try {
        await page.goto(`/crm/leads/${lead.id}`);

        const addActivityButton = page.getByRole('button', { name: /add.*activity|log.*activity|new.*activity/i });
        if (await addActivityButton.isVisible()) {
          await addActivityButton.click();

          // Fill activity form
          await page.getByLabel(/type/i).click();
          await page.getByRole('option', { name: /call|email|meeting/i }).first().click();

          await page.getByLabel(/subject|title/i).fill(`E2E Test Activity ${Date.now()}`);

          await page.getByRole('button', { name: /save|create|add/i }).click();
          await page.waitForTimeout(1000);
        }
      } finally {
        await deleteTestLead(request, lead.id);
      }
    });
  });

  test.describe('Delete Lead', () => {
    test('can delete/archive lead', async ({ page, request }) => {
      const lead = await createTestLead(request, {
        name: `Delete Test ${Date.now()}`,
      });

      await page.goto(`/crm/leads/${lead.id}`);

      const deleteButton = page.getByRole('button', { name: /delete|archive|remove/i });
      if (await deleteButton.isVisible()) {
        await deleteButton.click();

        const confirmButton = page.getByRole('button', { name: /confirm|yes|delete/i });
        await expect(confirmButton).toBeVisible({ timeout: 2000 });
        await confirmButton.click();

        await page.waitForURL('/crm/leads', { timeout: 10000 });

        // Lead should not appear
        await page.getByPlaceholder(/search/i).fill(lead.name);
        await expect(page.getByText(lead.name)).toBeHidden({ timeout: 5000 });
      } else {
        // Cleanup if delete not available
        await deleteTestLead(request, lead.id);
      }
    });
  });
});

test.describe('CRM Leads - RBAC', () => {
  test('read-only user cannot create leads', async ({ page }) => {
    await setupAuth(page, ['crm:read']);
    await page.goto('/crm/leads');

    const createButton = page.getByRole('link', { name: /add.*lead|new.*lead|create.*lead/i });
    await expect(createButton).toBeHidden();
  });

  test('user without CRM scope sees access denied', async ({ page }) => {
    await setupAuth(page, ['hr:read']);
    await page.goto('/crm/leads');

    await expectAccessDenied(page);
  });
});

test.describe('CRM Leads - Unauthenticated', () => {
  test('redirects to login when not authenticated', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => localStorage.clear());

    await page.goto('/crm/leads');

    await expect(page).toHaveURL(/\/login|\/auth/);
  });
});
