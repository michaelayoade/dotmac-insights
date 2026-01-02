import { chromium, FullConfig } from '@playwright/test';
import path from 'path';
import fs from 'fs';

/**
 * Global setup for Playwright tests.
 *
 * Runs once before all tests to:
 * - Authenticate users and save state
 * - Seed any required test data
 * - Verify application is running
 */

const AUTH_DIR = path.join(__dirname, '.auth');

interface TestUser {
  email: string;
  password: string;
  stateFile: string;
}

const TEST_USERS: Record<string, TestUser> = {
  superuser: {
    email: process.env.E2E_SUPERUSER_EMAIL || 'admin@dotmac.ng',
    password: process.env.E2E_SUPERUSER_PASSWORD || 'admin123',
    stateFile: 'superuser.json',
  },
  user: {
    email: process.env.E2E_USER_EMAIL || 'user@dotmac.ng',
    password: process.env.E2E_USER_PASSWORD || 'user123',
    stateFile: 'user.json',
  },
  readonly: {
    email: process.env.E2E_READONLY_EMAIL || 'readonly@dotmac.ng',
    password: process.env.E2E_READONLY_PASSWORD || 'readonly123',
    stateFile: 'readonly.json',
  },
};

async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0].use.baseURL || 'http://localhost:8000';

  // Ensure auth directory exists
  if (!fs.existsSync(AUTH_DIR)) {
    fs.mkdirSync(AUTH_DIR, { recursive: true });
  }

  // Check if app is running
  console.log(`Checking if app is running at ${baseURL}...`);
  const browser = await chromium.launch();

  try {
    const page = await browser.newPage();
    await page.goto(`${baseURL}/health`, { timeout: 30000 });
    console.log('Application is ready');
    await page.close();
  } catch (error) {
    console.error('Application not ready. Make sure the server is running.');
    await browser.close();
    throw error;
  }

  // Authenticate each test user and save state
  for (const [role, user] of Object.entries(TEST_USERS)) {
    const stateFile = path.join(AUTH_DIR, user.stateFile);

    // Skip if state already exists and is recent (less than 1 hour old)
    if (fs.existsSync(stateFile)) {
      const stats = fs.statSync(stateFile);
      const ageMinutes = (Date.now() - stats.mtimeMs) / (1000 * 60);
      if (ageMinutes < 60) {
        console.log(`Using cached auth state for ${role} (${Math.round(ageMinutes)} min old)`);
        continue;
      }
    }

    console.log(`Authenticating ${role}...`);
    const context = await browser.newContext();
    const page = await context.newPage();

    try {
      await page.goto(`${baseURL}/login`);

      // Fill login form
      await page.fill('input[name="email"], input[name="username"]', user.email);
      await page.fill('input[name="password"]', user.password);
      await page.click('button[type="submit"]');

      // Wait for successful login
      await page.waitForURL(/\/(dashboard|home|crm|$)/, { timeout: 15000 });

      // Save authenticated state
      await context.storageState({ path: stateFile });
      console.log(`Saved auth state for ${role}`);
    } catch (error) {
      console.error(`Failed to authenticate ${role}:`, error);
      // Don't fail setup - test might use anonPage
    }

    await context.close();
  }

  await browser.close();
}

export default globalSetup;
