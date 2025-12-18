import { test, expect } from '@playwright/test';

test.describe('Webhooks smoke', () => {
  test('Inbound providers list renders', async ({ page }) => {
    await page.goto('/admin/webhooks/inbound');
    await expect(page.getByRole('heading', { name: /Inbound Webhooks/i })).toBeVisible();
    await expect(page.getByText(/Inbound webhooks coming into the platform/i)).toBeVisible();
  });

  test('Omni webhooks page loads', async ({ page }) => {
    await page.goto('/admin/webhooks/omni');
    await expect(page.getByRole('heading', { name: /Omni Webhooks/i })).toBeVisible();
  });
});
