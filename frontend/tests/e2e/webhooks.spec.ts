/**
 * Admin / Webhooks E2E Tests
 *
 * Comprehensive tests for the Admin module including:
 * - Webhooks list with provider data
 * - Create and rotate webhook secrets
 * - Access control for admin scope
 * - Inbound and outbound webhook configuration
 */

import { test, expect, setupAuth, expectAccessDenied } from './fixtures/auth';

test.describe('Webhooks - Admin Authenticated', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page, ['admin:read', 'admin:write']);
  });

  test.describe('Inbound Webhooks', () => {
    test('renders inbound webhooks page', async ({ page }) => {
      await page.goto('/admin/webhooks/inbound');

      await expect(page.getByRole('heading', { name: /Inbound Webhooks/i })).toBeVisible();
      await expect(page.getByText(/Inbound webhooks coming into the platform/i)).toBeVisible();
    });

    test('displays provider list', async ({ page }) => {
      await page.goto('/admin/webhooks/inbound');

      await page.waitForLoadState('networkidle');

      // Should show webhook providers (Paystack, Flutterwave, etc.)
      await expect(
        page.getByText(/paystack|flutterwave|mono|provider/i).first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('shows webhook URL for each provider', async ({ page }) => {
      await page.goto('/admin/webhooks/inbound');

      await page.waitForLoadState('networkidle');

      // Should display webhook URLs
      await expect(
        page.getByText(/https?:\/\/|webhook.*url/i).first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('copy URL button works', async ({ page }) => {
      await page.goto('/admin/webhooks/inbound');

      const copyButton = page.getByRole('button', { name: /copy/i }).first();
      await expect(copyButton).toBeVisible();
      await copyButton.click();

      await expect(page.getByText(/copied/i)).toBeVisible({ timeout: 3000 });
    });

    test('shows webhook secret (masked)', async ({ page }) => {
      await page.goto('/admin/webhooks/inbound');

      await page.waitForLoadState('networkidle');

      // Secrets should be masked
      await expect(
        page.getByText(/\*+|secret|hidden/i).first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('rotate secret shows confirmation', async ({ page }) => {
      await page.goto('/admin/webhooks/inbound');

      const rotateButton = page.getByRole('button', { name: /rotate|regenerate/i }).first();
      await expect(rotateButton).toBeVisible();
      await rotateButton.click();

      await expect(page.getByText(/are you sure|confirm|rotate/i)).toBeVisible({ timeout: 3000 });
    });

    test('shows webhook delivery status', async ({ page }) => {
      await page.goto('/admin/webhooks/inbound');

      await page.waitForLoadState('networkidle');

      await expect(page.getByText(/active|enabled|status/i).first()).toBeVisible({
        timeout: 10000,
      });
    });
  });

  test.describe('Omni Webhooks (Outbound)', () => {
    test('renders omni webhooks page', async ({ page }) => {
      await page.goto('/admin/webhooks/omni');

      await expect(page.getByRole('heading', { name: /Omni Webhooks/i })).toBeVisible();
    });

    test('displays outbound webhook list', async ({ page }) => {
      await page.goto('/admin/webhooks/omni');

      await page.waitForLoadState('networkidle');

      await expect(page.locator('table tbody tr, [role="row"]').first()).toBeVisible({
        timeout: 10000,
      });
    });

    test('create webhook button exists', async ({ page }) => {
      await page.goto('/admin/webhooks/omni');

      await expect(
        page.getByRole('button', { name: /add|create|new/i }).or(
          page.getByRole('link', { name: /add|create|new/i })
        )
      ).toBeVisible();
    });

    test('create webhook form validates URL', async ({ page }) => {
      await page.goto('/admin/webhooks/omni');

      const addButton = page.getByRole('button', { name: /add|create|new/i }).first();
      await expect(addButton).toBeVisible();
      await addButton.click();

      const urlInput = page.getByLabel(/url|endpoint/i);
      await urlInput.fill('invalid-url');

      const saveButton = page.getByRole('button', { name: /save|create/i });
      await saveButton.click();

      await expect(page.getByText(/invalid|url|https/i).first()).toBeVisible({ timeout: 5000 });
    });

    test('create webhook successfully', async ({ page }) => {
      await page.goto('/admin/webhooks/omni');

      const addButton = page.getByRole('button', { name: /add|create|new/i }).first();
      await expect(addButton).toBeVisible();
      await addButton.click();

      await page.getByLabel(/name/i).fill(`Test Webhook ${Date.now()}`);
      await page.getByLabel(/url|endpoint/i).fill('https://example.com/webhook');

      const eventCheckbox = page.locator('input[type="checkbox"]').first();
      await expect(eventCheckbox).toBeVisible();
      await eventCheckbox.check();

      await page.getByRole('button', { name: /save|create/i }).click();

      await expect(page.getByText(/created|success/i).first()).toBeVisible({ timeout: 5000 });
    });

    test('edit webhook configuration', async ({ page }) => {
      await page.goto('/admin/webhooks/omni');

      await page.waitForSelector('table tbody tr, [role="row"]', { timeout: 10000 });

      const webhookRow = page.locator('table tbody tr, [role="row"]').first();
      await expect(webhookRow).toBeVisible();
      const editButton = webhookRow.locator('button').filter({ hasText: /edit/i });
      await expect(editButton).toBeVisible();
      await editButton.click();

      await expect(page.getByLabel(/name|url/i)).toBeVisible();
    });

    test('delete webhook shows confirmation', async ({ page }) => {
      await page.goto('/admin/webhooks/omni');

      await page.waitForSelector('table tbody tr', { timeout: 10000 });

      const webhookRow = page.locator('table tbody tr').first();
      await expect(webhookRow).toBeVisible();
      const deleteButton = webhookRow.locator('button').filter({ hasText: /delete|remove/i });
      await expect(deleteButton).toBeVisible();
      await deleteButton.click();

      await expect(page.getByText(/are you sure|confirm|delete/i)).toBeVisible({ timeout: 3000 });
    });

    test('test webhook button sends test event', async ({ page }) => {
      await page.goto('/admin/webhooks/omni');

      await page.waitForSelector('table tbody tr', { timeout: 10000 });

      const testButton = page.getByRole('button', { name: /test|ping/i }).first();
      await expect(testButton).toBeVisible();
      await testButton.click();

      await expect(page.getByText(/sent|success|response/i).first()).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Webhook Logs', () => {
    test('displays delivery logs', async ({ page }) => {
      await page.goto('/admin/webhooks/logs');

      await page.waitForLoadState('networkidle');

      await expect(page.locator('table tbody tr, [role="row"]').first()).toBeVisible({
        timeout: 10000,
      });
    });

    test('filter logs by status', async ({ page }) => {
      await page.goto('/admin/webhooks/logs');

      const statusFilter = page.locator('select').first();
      await expect(statusFilter).toBeVisible();
      await statusFilter.selectOption({ label: /failed/i });
      await page.waitForTimeout(500);
    });

    test('retry failed delivery', async ({ page }) => {
      await page.goto('/admin/webhooks/logs');

      const failedRow = page.locator('tr').filter({ hasText: /failed/i }).first();
      await expect(failedRow).toBeVisible({ timeout: 5000 });
      const retryButton = failedRow.locator('button').filter({ hasText: /retry/i });
      await expect(retryButton).toBeVisible();
      await retryButton.click();

      await expect(page.getByText(/retrying|queued|success/i).first()).toBeVisible({
        timeout: 5000,
      });
    });
  });
});

test.describe('Webhooks - RBAC', () => {
  test('user without admin scope cannot access webhooks', async ({ page }) => {
    await setupAuth(page, ['customers:read', 'hr:read']);
    await page.goto('/admin/webhooks/inbound');

    await expectAccessDenied(page);
  });

  test('user with admin:read can view but not modify', async ({ page }) => {
    await setupAuth(page, ['admin:read']);
    await page.goto('/admin/webhooks/inbound');

    // Should be visible
    await expect(page.getByRole('heading', { name: /webhook/i })).toBeVisible();

    // But rotate/create buttons should be disabled or hidden
    const rotateButton = page.getByRole('button', { name: /rotate/i }).first();
    await expect(rotateButton).toBeVisible();
    await expect(rotateButton).toBeDisabled();
  });

  test('omni webhooks requires admin:write to create', async ({ page }) => {
    await setupAuth(page, ['admin:read']);
    await page.goto('/admin/webhooks/omni');

    const createButton = page.getByRole('button', { name: /add|create/i }).first();
    await expect(createButton).toBeVisible();
    await expect(createButton).toBeDisabled();
  });
});

test.describe('Webhooks - Unauthenticated', () => {
  test('redirects to login', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => localStorage.clear());

    await page.goto('/admin/webhooks/inbound');

    await expect(page).toHaveURL(/\/login|\/auth/);
  });
});
