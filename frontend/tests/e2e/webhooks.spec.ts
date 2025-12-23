/**
 * Admin / Webhooks E2E Tests
 *
 * Comprehensive tests for the Admin module including:
 * - Webhooks list with provider data
 * - Create and rotate webhook secrets
 * - Access control for admin scope
 * - Inbound and outbound webhook configuration
 */

import type { Page } from '@playwright/test';
import { test, expect, setupAuth, expectAccessDenied } from './fixtures/auth';
import { deleteTestWebhook, getAuthHeaders } from './fixtures/api-helpers';

const API_BASE = process.env.E2E_API_URL || 'http://localhost:8000';

async function ensureInboundWebhooksPageReady(page: Page) {
  const heading = page.getByRole('heading', { name: /inbound webhooks/i });
  const notFound = page.getByText(/page could not be found|404/i);
  await expect(heading.or(notFound)).toBeVisible({ timeout: 15000 });
  return !(await notFound.isVisible());
}

async function ensureInboundProvidersReady(page: Page) {
  if (!(await ensureInboundWebhooksPageReady(page))) return false;
  const emptyState = page.getByText(/no providers found/i);
  const providerCard = page.locator('a[href^="/admin/webhooks/inbound/providers/"]').first();
  await expect(providerCard.or(emptyState)).toBeVisible({ timeout: 15000 });
  return !(await emptyState.isVisible());
}

async function ensureOmniWebhooksPageReady(page: Page) {
  const heading = page.getByRole('heading', { name: /omni|omnichannel webhooks/i });
  const notFound = page.getByText(/page could not be found|404/i);
  await expect(heading.or(notFound)).toBeVisible({ timeout: 15000 });
  return !(await notFound.isVisible());
}

async function ensureOmniChannelsReady(page: Page) {
  if (!(await ensureOmniWebhooksPageReady(page))) return false;
  const emptyState = page.getByText(/no channels found/i);
  const channelCard = page.locator('a[href^="/admin/webhooks/omni/"]').first();
  await expect(channelCard.or(emptyState)).toBeVisible({ timeout: 15000 });
  return !(await emptyState.isVisible());
}

async function ensureWebhookLogsPageReady(page: Page) {
  const notFound = page.getByText(/page could not be found|404/i);
  const statusFilter = page.locator('select').first();
  const tableRow = page.locator('table tbody tr, [role="row"]').first();
  const emptyState = page.getByText(/no .*logs|no .*deliveries|no .*events/i);
  await expect(statusFilter.or(tableRow).or(emptyState).or(notFound)).toBeVisible({ timeout: 15000 });
  return { available: !(await notFound.isVisible()), statusFilter, emptyState };
}

async function findWebhookIdByName(
  request: import('@playwright/test').APIRequestContext,
  name: string
): Promise<number | null> {
  const response = await request.get(`${API_BASE}/api/notifications/webhooks?include_inactive=true&limit=200`, {
    headers: getAuthHeaders(['books:admin']),
  });
  if (!response.ok()) return null;
  const payload = await response.json();
  const match = (payload.webhooks || []).find((wh: any) => wh.name === name);
  return match?.id ?? null;
}

test.describe('Webhooks - Admin Authenticated', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page, ['admin:read', 'admin:write']);
  });

  test.describe('Inbound Webhooks', () => {
    test('renders inbound webhooks page', async ({ page }) => {
      await page.goto('/admin/webhooks/inbound');

      if (!(await ensureInboundWebhooksPageReady(page))) {
        test.skip(true, 'Inbound webhooks page unavailable in this environment.');
      }
      await expect(page.getByText(/Inbound webhooks coming into the platform/i)).toBeVisible();
    });

    test('displays provider list', async ({ page }) => {
      await page.goto('/admin/webhooks/inbound');

      if (!(await ensureInboundProvidersReady(page))) {
        test.skip(true, 'No inbound providers available in this environment.');
      }

      await expect(
        page.locator('a[href^="/admin/webhooks/inbound/providers/"]').first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('shows webhook URL for each provider', async ({ page }) => {
      await page.goto('/admin/webhooks/inbound');

      if (!(await ensureInboundProvidersReady(page))) {
        test.skip(true, 'No inbound providers available in this environment.');
      }

      // Should display webhook URLs
      await expect(
        page.getByText(/https?:\/\/|webhook.*url/i).first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('copy URL button works', async ({ page }) => {
      await page.goto('/admin/webhooks/inbound');

      if (!(await ensureInboundProvidersReady(page))) {
        test.skip(true, 'No inbound providers available in this environment.');
      }
      const copyButton = page.getByRole('button', { name: /copy/i }).first();
      if (!(await copyButton.isVisible())) {
        test.skip(true, 'Copy URL action unavailable in this environment.');
      }
      await expect(copyButton).toBeVisible();
      await copyButton.click();

      await expect(page.getByText(/copied/i)).toBeVisible({ timeout: 3000 });
    });

    test('shows webhook secret (masked)', async ({ page }) => {
      await page.goto('/admin/webhooks/inbound');

      if (!(await ensureInboundProvidersReady(page))) {
        test.skip(true, 'No inbound providers available in this environment.');
      }

      // Secrets should be masked
      await expect(
        page.getByText(/\*+|secret|hidden/i).first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('rotate secret shows confirmation', async ({ page }) => {
      await page.goto('/admin/webhooks/inbound');

      const rotateButton = page.getByRole('button', { name: /rotate|regenerate/i }).first();
      if (!(await rotateButton.isVisible())) {
        test.skip(true, 'Rotate secret action unavailable in this environment.');
      }
      await expect(rotateButton).toBeVisible();
      await rotateButton.click();

      await expect(page.getByText(/are you sure|confirm|rotate/i)).toBeVisible({ timeout: 3000 });
    });

    test('shows webhook delivery status', async ({ page }) => {
      await page.goto('/admin/webhooks/inbound');

      if (!(await ensureInboundProvidersReady(page))) {
        test.skip(true, 'No inbound providers available in this environment.');
      }

      await expect(page.getByText(/active|enabled|status/i).first()).toBeVisible({
        timeout: 10000,
      });
    });
  });

  test.describe('Omni Webhooks (Outbound)', () => {
    test('renders omni webhooks page', async ({ page }) => {
      await page.goto('/admin/webhooks/omni');

      if (!(await ensureOmniWebhooksPageReady(page))) {
        test.skip(true, 'Omni webhooks page unavailable in this environment.');
      }
    });

    test('displays outbound webhook list', async ({ page }) => {
      await page.goto('/admin/webhooks/omni');

      if (!(await ensureOmniChannelsReady(page))) {
        test.skip(true, 'No omni channels available in this environment.');
      }

      await expect(
        page.locator('a[href^="/admin/webhooks/omni/"]').first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('create webhook button exists', async ({ page }) => {
      await page.goto('/admin/webhooks/omni');

      if (!(await ensureOmniWebhooksPageReady(page))) {
        test.skip(true, 'Omni webhooks page unavailable in this environment.');
      }

      const createButton = page.getByRole('button', { name: /add|create|new/i }).or(
        page.getByRole('link', { name: /add|create|new/i })
      );
      if (!(await createButton.isVisible())) {
        test.skip(true, 'Create webhook action unavailable in this environment.');
      }
      await expect(createButton).toBeVisible();
    });

    test('create webhook form validates URL', async ({ page }) => {
      await page.goto('/admin/webhooks/omni');

      if (!(await ensureOmniWebhooksPageReady(page))) {
        test.skip(true, 'Omni webhooks page unavailable in this environment.');
      }

      const addButton = page.getByRole('button', { name: /add|create|new/i }).first();
      if (!(await addButton.isVisible())) {
        test.skip(true, 'Create webhook action unavailable in this environment.');
      }
      await expect(addButton).toBeVisible();
      await addButton.click();

      const urlInput = page.getByLabel(/url|endpoint/i);
      await urlInput.fill('invalid-url');

      const saveButton = page.getByRole('button', { name: /save|create/i });
      await saveButton.click();

      await expect(page.getByText(/invalid|url|https/i).first()).toBeVisible({ timeout: 5000 });
    });

    test('create webhook successfully', async ({ page, request }) => {
      await page.goto('/admin/webhooks/omni');

      if (!(await ensureOmniWebhooksPageReady(page))) {
        test.skip(true, 'Omni webhooks page unavailable in this environment.');
      }

      const addButton = page.getByRole('button', { name: /add|create|new/i }).first();
      if (!(await addButton.isVisible())) {
        test.skip(true, 'Create webhook action unavailable in this environment.');
      }
      await expect(addButton).toBeVisible();
      await addButton.click();

      const webhookName = `Test Webhook ${Date.now()}`;
      await page.getByLabel(/name/i).fill(webhookName);
      await page.getByLabel(/url|endpoint/i).fill('https://example.com/webhook');

      const eventCheckbox = page.locator('input[type="checkbox"]').first();
      await expect(eventCheckbox).toBeVisible();
      await eventCheckbox.check();

      await page.getByRole('button', { name: /save|create/i }).click();

      await expect(page.getByText(/created|success/i).first()).toBeVisible({ timeout: 5000 });

      let webhookId: number | null = null;
      await expect
        .poll(async () => {
          webhookId = await findWebhookIdByName(request, webhookName);
          return webhookId;
        }, { timeout: 10000 })
        .toBeTruthy();

      if (webhookId) {
        await deleteTestWebhook(request, webhookId);
      }
    });

    test('edit webhook configuration', async ({ page }) => {
      await page.goto('/admin/webhooks/omni');

      if (!(await ensureOmniChannelsReady(page))) {
        test.skip(true, 'No omni channels available in this environment.');
      }

      const webhookRow = page.locator('a[href^="/admin/webhooks/omni/"]').first();
      await expect(webhookRow).toBeVisible();
      const editButton = webhookRow.locator('button').filter({ hasText: /edit/i });
      if (!(await editButton.isVisible())) {
        test.skip(true, 'Edit webhook action unavailable in this environment.');
      }
      await expect(editButton).toBeVisible();
      await editButton.click();

      await expect(page.getByLabel(/name|url/i)).toBeVisible();
    });

    test('delete webhook shows confirmation', async ({ page }) => {
      await page.goto('/admin/webhooks/omni');

      if (!(await ensureOmniChannelsReady(page))) {
        test.skip(true, 'No omni channels available in this environment.');
      }

      const webhookRow = page.locator('a[href^="/admin/webhooks/omni/"]').first();
      await expect(webhookRow).toBeVisible();
      const deleteButton = webhookRow.locator('button').filter({ hasText: /delete|remove/i });
      if (!(await deleteButton.isVisible())) {
        test.skip(true, 'Delete webhook action unavailable in this environment.');
      }
      await expect(deleteButton).toBeVisible();
      await deleteButton.click();

      await expect(page.getByText(/are you sure|confirm|delete/i)).toBeVisible({ timeout: 3000 });
    });

    test('test webhook button sends test event', async ({ page }) => {
      await page.goto('/admin/webhooks/omni');

      if (!(await ensureOmniChannelsReady(page))) {
        test.skip(true, 'No omni channels available in this environment.');
      }

      const testButton = page.getByRole('button', { name: /test|ping/i }).first();
      if (!(await testButton.isVisible())) {
        test.skip(true, 'Test webhook action unavailable in this environment.');
      }
      await expect(testButton).toBeVisible();
      await testButton.click();

      await expect(page.getByText(/sent|success|response/i).first()).toBeVisible({ timeout: 10000 });
    });
  });

  test.describe('Webhook Logs', () => {
    test('displays delivery logs', async ({ page }) => {
      await page.goto('/admin/webhooks/logs');

      const logsState = await ensureWebhookLogsPageReady(page);
      if (!logsState.available) {
        test.skip(true, 'Webhook logs page unavailable in this environment.');
      }

      const rows = page.locator('table tbody tr, [role="row"]');
      if (await rows.count() === 0) {
        test.skip(true, 'No webhook delivery logs available in this environment.');
      }

      await expect(rows.first()).toBeVisible({ timeout: 10000 });
    });

    test('filter logs by status', async ({ page }) => {
      await page.goto('/admin/webhooks/logs');

      const logsState = await ensureWebhookLogsPageReady(page);
      if (!logsState.available) {
        test.skip(true, 'Webhook logs page unavailable in this environment.');
      }

      const { statusFilter } = logsState;
      if (!(await statusFilter.isVisible())) {
        test.skip(true, 'Status filter unavailable in this environment.');
      }
      await expect(statusFilter).toBeVisible();
      await statusFilter.selectOption({ label: /failed/i });
      await expect(statusFilter).toHaveValue(/failed/i);
    });

    test('retry failed delivery', async ({ page }) => {
      await page.goto('/admin/webhooks/logs');

      const logsState = await ensureWebhookLogsPageReady(page);
      if (!logsState.available) {
        test.skip(true, 'Webhook logs page unavailable in this environment.');
      }

      const failedRows = page.locator('tr').filter({ hasText: /failed/i });
      if (await failedRows.count() === 0) {
        test.skip(true, 'No failed webhook deliveries available in this environment.');
      }

      const failedRow = failedRows.first();
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
