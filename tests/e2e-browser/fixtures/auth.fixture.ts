import { test as base, expect, Page, BrowserContext } from '@playwright/test';
import path from 'path';

/**
 * Authentication fixture for E2E tests.
 *
 * Provides pre-authenticated browser contexts for different user roles.
 */

// Storage state file paths
const STORAGE_DIR = path.join(__dirname, '../../.auth');

export interface AuthFixtures {
  /** Page with superuser authentication */
  superuserPage: Page;
  /** Page with standard user authentication */
  userPage: Page;
  /** Page with read-only user authentication */
  readonlyPage: Page;
  /** Unauthenticated page for login tests */
  anonPage: Page;
}

/**
 * Login helper function.
 */
async function login(page: Page, email: string, password: string): Promise<void> {
  await page.goto('/login');
  await page.fill('input[name="email"], input[name="username"]', email);
  await page.fill('input[name="password"]', password);
  await page.click('button[type="submit"]');

  // Wait for redirect to dashboard or home
  await page.waitForURL(/\/(dashboard|home|$)/, { timeout: 10000 });
}

/**
 * Extended test fixture with authentication helpers.
 */
export const test = base.extend<AuthFixtures>({
  superuserPage: async ({ browser }, use) => {
    // Create a new context with superuser credentials
    const context = await browser.newContext();
    const page = await context.newPage();

    // Login as superuser
    await login(page, process.env.E2E_SUPERUSER_EMAIL || 'admin@dotmac.ng', process.env.E2E_SUPERUSER_PASSWORD || 'admin123');

    await use(page);

    await context.close();
  },

  userPage: async ({ browser }, use) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await login(page, process.env.E2E_USER_EMAIL || 'user@dotmac.ng', process.env.E2E_USER_PASSWORD || 'user123');

    await use(page);

    await context.close();
  },

  readonlyPage: async ({ browser }, use) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await login(page, process.env.E2E_READONLY_EMAIL || 'readonly@dotmac.ng', process.env.E2E_READONLY_PASSWORD || 'readonly123');

    await use(page);

    await context.close();
  },

  anonPage: async ({ browser }, use) => {
    const context = await browser.newContext();
    const page = await context.newPage();

    await use(page);

    await context.close();
  },
});

export { expect };

/**
 * Global setup to save authentication state.
 * Run with: npx playwright test --global-setup=./tests/e2e-browser/fixtures/global-setup.ts
 */
export async function globalAuthSetup(browser: any) {
  const fs = await import('fs');

  // Ensure storage directory exists
  if (!fs.existsSync(STORAGE_DIR)) {
    fs.mkdirSync(STORAGE_DIR, { recursive: true });
  }

  // Setup superuser
  const superuserContext = await browser.newContext();
  const superuserPage = await superuserContext.newPage();
  await login(
    superuserPage,
    process.env.E2E_SUPERUSER_EMAIL || 'admin@dotmac.ng',
    process.env.E2E_SUPERUSER_PASSWORD || 'admin123'
  );
  await superuserContext.storageState({ path: path.join(STORAGE_DIR, 'superuser.json') });
  await superuserContext.close();

  // Setup regular user
  const userContext = await browser.newContext();
  const userPage = await userContext.newPage();
  await login(
    userPage,
    process.env.E2E_USER_EMAIL || 'user@dotmac.ng',
    process.env.E2E_USER_PASSWORD || 'user123'
  );
  await userContext.storageState({ path: path.join(STORAGE_DIR, 'user.json') });
  await userContext.close();
}
