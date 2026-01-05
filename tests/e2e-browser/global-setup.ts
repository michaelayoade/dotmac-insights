import { chromium, FullConfig } from '@playwright/test';
import path from 'path';
import fs from 'fs';
import jwt from 'jsonwebtoken';

/**
 * Global setup for Playwright tests.
 *
 * Runs once before all tests to:
 * - Verify application is running
 * - Generate JWT tokens for test users
 * - Save authenticated state (storage + cookies)
 *
 * Environment variables:
 * - E2E_JWT_SECRET: Required - the HS256 secret for signing test JWTs
 * - E2E_AUTH_ENABLED: Should be "true" on the server
 */

const AUTH_DIR = path.join(__dirname, '.auth');
const AUTH_COOKIE_NAME = 'dotmac_access_token';

interface TestUser {
  email: string;
  name: string;
  scopes: string[];
  stateFile: string;
}

const TEST_USERS: Record<string, TestUser> = {
  superuser: {
    email: process.env.E2E_SUPERUSER_EMAIL || 'admin@dotmac.ng',
    name: 'E2E Admin',
    scopes: ['*'],  // Superuser has all permissions
    stateFile: 'superuser.json',
  },
  user: {
    email: process.env.E2E_USER_EMAIL || 'user@dotmac.ng',
    name: 'E2E User',
    scopes: [
      'customers:read', 'customers:write',
      'invoices:read', 'invoices:write',
      'payments:read', 'payments:write',
      'tickets:read', 'tickets:write',
      'projects:read', 'projects:write',
      'employees:read',
      'subscriptions:read', 'subscriptions:write',
    ],
    stateFile: 'user.json',
  },
  readonly: {
    email: process.env.E2E_READONLY_EMAIL || 'readonly@dotmac.ng',
    name: 'E2E Readonly',
    scopes: [
      'customers:read',
      'invoices:read',
      'payments:read',
      'tickets:read',
      'projects:read',
      'employees:read',
      'subscriptions:read',
    ],
    stateFile: 'readonly.json',
  },
};

/**
 * Generate a JWT token for E2E testing.
 *
 * The token uses HS256 algorithm and includes:
 * - sub: User identifier
 * - email: User email
 * - name: User display name
 * - scopes: Permission scopes array
 * - exp: Expiration (24 hours from now)
 * - iat: Issued at timestamp
 */
function generateTestToken(user: TestUser, secret: string): string {
  const now = Math.floor(Date.now() / 1000);
  const payload = {
    sub: `e2e-${user.email.replace('@', '-at-')}`,
    email: user.email,
    name: user.name,
    scopes: user.scopes,
    iat: now,
    exp: now + 86400, // 24 hours
  };

  return jwt.sign(payload, secret, { algorithm: 'HS256' });
}

/**
 * Create storage state with authentication cookie.
 */
function createStorageState(token: string, baseURL: string): object {
  // Parse the URL to get cookie domain
  const url = new URL(baseURL);
  const domain = url.hostname;

  return {
    cookies: [
      {
        name: AUTH_COOKIE_NAME,
        value: token,
        domain: domain,
        path: '/',
        expires: Math.floor(Date.now() / 1000) + 86400,
        httpOnly: true,
        secure: url.protocol === 'https:',
        sameSite: 'Lax',
      },
    ],
    origins: [],
  };
}

async function globalSetup(config: FullConfig) {
  const baseURL = config.projects[0].use.baseURL || 'http://localhost:8000';
  const authRequired = (process.env.E2E_AUTH_ENABLED || 'true') === 'true';

  // Get E2E JWT secret from environment
  const jwtSecret = process.env.E2E_JWT_SECRET;
  if (!jwtSecret) {
    if (authRequired) {
      throw new Error('E2E_JWT_SECRET not set while E2E_AUTH_ENABLED=true.');
    }
    console.warn('E2E_JWT_SECRET not set. Tests will run without authentication.');
  }

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

  // If no JWT secret, create empty auth states (anonymous access)
  if (!jwtSecret) {
    for (const [role, user] of Object.entries(TEST_USERS)) {
      const stateFile = path.join(AUTH_DIR, user.stateFile);
      const emptyState = { cookies: [], origins: [] };
      fs.writeFileSync(stateFile, JSON.stringify(emptyState, null, 2));
      console.log(`Created empty auth state for ${role} (no E2E_JWT_SECRET)`);
    }
    await browser.close();
    return;
  }

  // Generate tokens and create storage states for each test user
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

    console.log(`Generating auth token for ${role}...`);

    // Generate JWT token
    const token = generateTestToken(user, jwtSecret);

    // Create storage state with cookie
    const storageState = createStorageState(token, baseURL);

    // Verify the token works by making a test request
    const context = await browser.newContext();
    const page = await context.newPage();

    try {
      // Set the auth cookie
      await context.addCookies([{
        name: AUTH_COOKIE_NAME,
        value: token,
        url: baseURL,
        httpOnly: true,
        sameSite: 'Lax',
      }]);

      // Try to access a protected page
      await page.goto(`${baseURL}/`, { timeout: 15000 });

      // Check if we're redirected to login (auth failed) or stayed on the page (auth succeeded)
      const currentUrl = page.url();
      if (currentUrl.includes('/login')) {
        if (authRequired) {
          throw new Error(`Auth token rejected for ${role} while E2E_AUTH_ENABLED=true.`);
        }
        console.warn(`Auth token not accepted for ${role} - server may not have E2E_AUTH_ENABLED=true`);
      } else {
        console.log(`Auth token verified for ${role}`);
      }
    } catch (error) {
      console.warn(`Could not verify auth for ${role}:`, error);
    }

    await context.close();

    // Save storage state
    fs.writeFileSync(stateFile, JSON.stringify(storageState, null, 2));
    console.log(`Saved auth state for ${role}`);
  }

  await browser.close();
}

export default globalSetup;
