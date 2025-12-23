/**
 * Settings & Feature Gating E2E Tests
 *
 * Comprehensive tests for settings pages and feature flag behavior:
 * - Feature flag disabled → UI shows AccessDenied
 * - Feature flag enabled → full UI loads
 * - User preferences and settings persistence
 * - Admin settings access control
 */

import { test, expect, setupAuth, expectAccessDenied } from './fixtures/auth';

test.describe('Settings - Authenticated', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page, ['admin:read', 'admin:write', 'customers:read']);
  });

  test.describe('Admin Settings Overview', () => {
    test('renders admin settings page', async ({ page }) => {
      await page.goto('/admin/settings');

      await expect(
        page.getByRole('heading', { name: /setting/i })
      ).toBeVisible({ timeout: 10000 });
    });

    test('displays settings sections', async ({ page }) => {
      await page.goto('/admin/settings');

      // Should show multiple settings sections
      await expect(
        page.getByText(/general|company|notification|integration/i).first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('can navigate between settings sections', async ({ page }) => {
      await page.goto('/admin/settings');

      // Find nav links or tabs
      const navItems = page.locator('nav a, [role="tab"]');
      const count = await navItems.count();

      expect(count).toBeGreaterThan(1);
      await navItems.nth(1).click();
      await page.waitForLoadState('networkidle');
      await expect(page.locator('body')).toBeVisible();
    });
  });

  test.describe('Company Settings', () => {
    test('displays company information', async ({ page }) => {
      await page.goto('/admin/settings/company');

      await expect(
        page.getByText(/company|organization|business/i).first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('can update company name', async ({ page }) => {
      await page.goto('/admin/settings/company');

      const nameInput = page.getByLabel(/company.*name|name/i);
      await expect(nameInput).toBeVisible();
      const currentValue = await nameInput.inputValue();
      await nameInput.fill(`${currentValue} Updated`);

      const saveButton = page.getByRole('button', { name: /save/i });
      await saveButton.click();

      await expect(page.getByText(/saved|updated|success/i).first()).toBeVisible({ timeout: 5000 });

      // Revert change
      await nameInput.fill(currentValue);
      await saveButton.click();
    });

    test('validates required fields', async ({ page }) => {
      await page.goto('/admin/settings/company');

      const nameInput = page.getByLabel(/company.*name|name/i);
      await expect(nameInput).toBeVisible();
      await nameInput.fill('');

      const saveButton = page.getByRole('button', { name: /save/i });
      await saveButton.click();

      await expect(page.getByText(/required|cannot be empty/i).first()).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('Notification Settings', () => {
    test('displays notification preferences', async ({ page }) => {
      await page.goto('/admin/settings/notifications');

      await expect(
        page.getByText(/notification|email|alert/i).first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('can toggle notification channels', async ({ page }) => {
      await page.goto('/admin/settings/notifications');

      const toggles = page.locator('input[type="checkbox"], [role="switch"]');
      const firstToggle = toggles.first();

      await expect(firstToggle).toBeVisible();
      const wasChecked = await firstToggle.isChecked();
      await firstToggle.click();

      const isNowChecked = await firstToggle.isChecked();
      expect(isNowChecked).not.toBe(wasChecked);

      await firstToggle.click();
    });

    test('saves notification preferences', async ({ page }) => {
      await page.goto('/admin/settings/notifications');

      const saveButton = page.getByRole('button', { name: /save/i });
      await expect(saveButton).toBeVisible();
      await saveButton.click();

      await expect(page.getByText(/saved|updated|success/i).first()).toBeVisible({ timeout: 5000 });
    });
  });

  test.describe('Integration Settings', () => {
    test('displays integration list', async ({ page }) => {
      await page.goto('/admin/settings/integrations');

      await expect(
        page.getByText(/integration|connect|sync/i).first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('shows connected/disconnected status', async ({ page }) => {
      await page.goto('/admin/settings/integrations');

      await page.waitForLoadState('networkidle');

      await expect(
        page.getByText(/connected|disconnected|not.*configured/i).first()
      ).toBeVisible({ timeout: 10000 });
    });

    test('can connect integration', async ({ page }) => {
      await page.goto('/admin/settings/integrations');

      const connectButton = page.getByRole('button', { name: /connect|configure|setup/i }).first();
      await expect(connectButton).toBeVisible();
      await connectButton.click();

      await expect(page.getByText(/connect|authorize|api.*key/i).first()).toBeVisible({
        timeout: 5000,
      });
    });
  });
});

test.describe('Settings - RBAC', () => {
  test('user without admin scope cannot access settings', async ({ page }) => {
    await setupAuth(page, ['customers:read', 'hr:read']);
    await page.goto('/admin/settings');

    await expectAccessDenied(page);
  });

  test('admin:read can view but not save settings', async ({ page }) => {
    await setupAuth(page, ['admin:read']);
    await page.goto('/admin/settings');

    await expect(page.getByRole('heading', { name: /setting/i })).toBeVisible();

    const saveButton = page.getByRole('button', { name: /save/i }).first();
    await expect(saveButton).toBeVisible();
    await expect(saveButton).toBeDisabled();
  });
});

test.describe('User Preferences', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page, ['customers:read']);
  });

  test('user can access their profile settings', async ({ page }) => {
    await page.goto('/settings/profile');

    await expect(
      page.getByText(/profile|account|preference/i).first()
    ).toBeVisible({ timeout: 10000 });
  });

  test('can update display preferences', async ({ page }) => {
    await page.goto('/settings/preferences');

      const themeToggle = page.locator('[role="switch"], input[type="checkbox"]').first();
      await expect(themeToggle).toBeVisible();
      const initialState = await themeToggle.getAttribute('aria-checked');
      if (initialState !== null) {
        await themeToggle.click();
        await expect(themeToggle).not.toHaveAttribute('aria-checked', initialState);
      } else {
        const wasChecked = await themeToggle.isChecked();
        await themeToggle.click();
        await expect(themeToggle).toHaveJSProperty('checked', !wasChecked);
      }
  });

  test('preferences persist across sessions', async ({ page }) => {
    await page.goto('/settings/preferences');

    // Make a change
      const toggle = page.locator('[role="switch"]').first();
      await expect(toggle).toBeVisible();
      const initialState = await toggle.getAttribute('aria-checked');
      await toggle.click();
      if (initialState !== null) {
        await expect(toggle).not.toHaveAttribute('aria-checked', initialState);
      }

      await page.reload();

    const newState = await toggle.getAttribute('aria-checked');
    expect(newState).not.toBe(initialState);
  });
});
