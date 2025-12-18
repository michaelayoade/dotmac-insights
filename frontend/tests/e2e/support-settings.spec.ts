import { test, expect } from '@playwright/test';

test.describe('Support settings smoke', () => {
  test('Loads settings and CSAT section', async ({ page }) => {
    await page.goto('/support/settings');
    await expect(page.getByRole('heading', { name: /Support Settings/i })).toBeVisible();
    await expect(page.getByText(/CSAT Survey Settings/i)).toBeVisible();
    await expect(page.getByText(/Survey Trigger/i)).toBeVisible();
  });
});
