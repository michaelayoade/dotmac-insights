/**
 * Contacts E2E Tests
 *
 * Comprehensive tests for the Unified Contacts module including:
 * - List view with pagination, filters, and search
 * - CRUD operations (create, read, update, delete/archive)
 * - Data validation and error states
 * - RBAC (role-based access control)
 */

import { test, expect, setupAuth, expectAccessDenied, type Scope } from './fixtures/auth';
import { createTestContact, deleteTestContact } from './fixtures/api-helpers';

test.describe('Contacts - Authenticated', () => {
  test.beforeEach(async ({ page }) => {
    // Set up authentication with full customer scopes
    await setupAuth(page, ['customers:read', 'customers:write']);
  });

  test.describe('List View', () => {
    test('renders contacts list with data table', async ({ page }) => {
      await page.goto('/contacts');

      // Verify page structure
      await expect(page.getByRole('heading', { name: /Unified Contacts/i })).toBeVisible();
      await expect(page.getByRole('link', { name: /Add Contact/i })).toBeVisible();

      // Verify data table is present
      await expect(page.locator('table, [role="grid"]').first()).toBeVisible();

      // Verify filter controls exist
      await expect(page.getByPlaceholder(/search/i)).toBeVisible();
    });

    test('displays pagination controls when data exists', async ({ page }) => {
      await page.goto('/contacts');

      // Wait for table to load
      await page.waitForSelector('table tbody tr, [role="grid"] [role="row"]', {
        timeout: 10000,
      });

      await expect(page.locator('table tbody tr, [role="grid"] [role="row"]').first()).toBeVisible();
      await expect(
        page
          .locator('[aria-label*="page"], button:has-text("Next"), button:has-text("Previous")')
          .first()
      ).toBeVisible();
    });

    test('search filters contacts by name', async ({ page }) => {
      await page.goto('/contacts');

      const searchInput = page.getByPlaceholder(/search/i);
      await searchInput.fill('Test');

      // Wait for search debounce and API response
      await page.waitForTimeout(500);

      // Table should update (either showing results or empty state)
      await expect(page.locator('table, [role="grid"]').first()).toBeVisible();
    });

    test('filter by contact type works', async ({ page }) => {
      await page.goto('/contacts');

      // Find and use the contact type filter
      const typeFilter = page.locator('select').filter({ hasText: /type|all/i }).first();
      await expect(typeFilter).toBeVisible();
      await typeFilter.selectOption({ index: 1 });
      await page.waitForTimeout(500);

      // Verify table is still visible after filter
      await expect(page.locator('table, [role="grid"]').first()).toBeVisible();
    });
  });

  test.describe('Create Contact', () => {
    test('navigates to create form from list', async ({ page }) => {
      await page.goto('/contacts');

      await page.getByRole('link', { name: /Add Contact/i }).click();

      await expect(page).toHaveURL(/\/contacts\/new|\/contacts\/create/);
      await expect(page.getByRole('heading', { name: /new|create|add/i })).toBeVisible();
    });

    test('validates required fields', async ({ page }) => {
      await page.goto('/contacts/new');

      // Try to submit empty form
      const submitButton = page.getByRole('button', { name: /save|create|submit/i });
      await submitButton.click();

      // Should show validation errors
      await expect(
        page.getByText(/required|cannot be empty|please enter/i).first()
      ).toBeVisible({ timeout: 5000 });
    });

    test('creates contact successfully and shows in list', async ({ page, request }) => {
      const testName = `E2E Test Contact ${Date.now()}`;
      const testEmail = `e2e-${Date.now()}@test.com`;

      await page.goto('/contacts/new');

      // Fill form
      await page.getByLabel(/name/i).fill(testName);
      await page.getByLabel(/email/i).fill(testEmail);

      // Submit
      const submitButton = page.getByRole('button', { name: /save|create|submit/i });
      await submitButton.click();

      // Should redirect to list or detail page
      await page.waitForURL(/\/contacts(?:\/\d+)?$/, { timeout: 10000 });

      // Verify contact appears in list
      await page.goto('/contacts');
      await page.getByPlaceholder(/search/i).fill(testName);
      await page.waitForTimeout(500);

      await expect(page.getByText(testName)).toBeVisible({ timeout: 5000 });
    });

  });

  test.describe('Edit Contact', () => {
    test('loads contact data in edit form', async ({ page, request }) => {
      // Create a test contact first
      const contact = await createTestContact(request, {
        name: `Edit Test ${Date.now()}`,
        email: `edit-${Date.now()}@test.com`,
      });

      await page.goto(`/contacts/${contact.id}`);

      // Click edit button
      const editButton = page.getByRole('link', { name: /edit/i }).or(
        page.getByRole('button', { name: /edit/i })
      );
      await editButton.click();

      // Verify form is populated
      await expect(page.getByLabel(/name/i)).toHaveValue(contact.name);

      // Cleanup
      await deleteTestContact(request, contact.id);
    });

    test('updates contact and persists changes', async ({ page, request }) => {
      const contact = await createTestContact(request, {
        name: `Update Test ${Date.now()}`,
        email: `update-${Date.now()}@test.com`,
      });

      await page.goto(`/contacts/${contact.id}/edit`);

      const updatedName = `Updated ${Date.now()}`;
      await page.getByLabel(/name/i).fill(updatedName);
      await page.getByRole('button', { name: /save|update|submit/i }).click();

      // Should redirect and show updated data
      await page.waitForURL(/\/contacts\/\d+$/, { timeout: 10000 });
      await expect(page.getByText(updatedName)).toBeVisible();

      // Cleanup
      await deleteTestContact(request, contact.id);
    });
  });

  test.describe('Delete/Archive Contact', () => {
    test('archive removes contact from active list', async ({ page, request }) => {
      const contact = await createTestContact(request, {
        name: `Archive Test ${Date.now()}`,
        email: `archive-${Date.now()}@test.com`,
      });

      await page.goto(`/contacts/${contact.id}`);

      // Find and click archive/delete button
      const archiveButton = page.getByRole('button', { name: /archive|delete|remove/i });
      await archiveButton.click();

      // Confirm if modal appears
      const confirmButton = page.getByRole('button', { name: /confirm|yes|archive|delete/i });
      await expect(confirmButton).toBeVisible({ timeout: 2000 });
      await confirmButton.click();

      // Should redirect to list
      await page.waitForURL('/contacts', { timeout: 10000 });

      // Contact should not appear in active list
      await page.getByPlaceholder(/search/i).fill(contact.name);
      await page.waitForTimeout(500);

      await expect(page.getByText(contact.name)).not.toBeVisible();
    });
  });
});

  test.describe('Contacts - RBAC', () => {
    test('read-only user cannot see create button', async ({ page }) => {
      await setupAuth(page, ['customers:read']);
      await page.goto('/contacts');

      // Create button should be hidden or disabled
      const createButton = page.getByRole('link', { name: /Add Contact/i });
      await expect(createButton).toBeHidden();
    });

  test('user without customers scope sees access denied', async ({ page }) => {
    await setupAuth(page, ['hr:read']); // No customer scopes
    await page.goto('/contacts');

    await expectAccessDenied(page);
  });
});

  test.describe('Contacts - Unauthenticated', () => {
    test('redirects to login when not authenticated', async ({ page }) => {
      // Clear any existing auth
      await page.goto('/');
      await page.evaluate(() => localStorage.clear());

      await page.goto('/contacts');

      await expect(page).toHaveURL(/\/login|\/auth/);
    });
  });
