import { test, expect } from '@playwright/test';

test.describe('Contacts smoke', () => {
  test('Contacts list renders', async ({ page }) => {
    await page.goto('/contacts');
    await expect(page.getByText(/Unified Contacts/i)).toBeVisible();
    await expect(page.getByRole('link', { name: /Add Contact/i })).toBeVisible();
  });
});
