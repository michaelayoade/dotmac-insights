/**
 * Playwright auth fixtures for authenticated E2E tests.
 *
 * Sets up localStorage with a test JWT token containing the specified scopes.
 * Uses storage state to persist auth across tests for efficiency.
 */

import { createHmac, createHash } from 'crypto';
import { test as base, expect, type Page } from '@playwright/test';

// All available scopes matching the backend RBAC system
export type Scope =
  | 'customers:read'
  | 'customers:write'
  | 'analytics:read'
  | 'sync:read'
  | 'sync:write'
  | 'explore:read'
  | 'admin:read'
  | 'admin:write'
  | 'hr:read'
  | 'hr:write'
  | 'accounting:read'
  | 'accounting:write'
  | 'payments:read'
  | 'payments:write'
  | 'openbanking:read'
  | 'openbanking:write'
  | 'gateway:read'
  | 'gateway:write';

const ALL_SCOPES: Scope[] = [
  'customers:read',
  'customers:write',
  'analytics:read',
  'sync:read',
  'sync:write',
  'explore:read',
  'admin:read',
  'admin:write',
  'hr:read',
  'hr:write',
  'accounting:read',
  'accounting:write',
  'payments:read',
  'payments:write',
  'openbanking:read',
  'openbanking:write',
  'gateway:read',
  'gateway:write',
];

// Test user configurations for different role scenarios
export const TEST_USERS = {
  admin: {
    email: 'admin@test.dotmac.io',
    scopes: ALL_SCOPES,
  },
  readonly: {
    email: 'readonly@test.dotmac.io',
    scopes: ['customers:read', 'analytics:read', 'explore:read'] as Scope[],
  },
  hr: {
    email: 'hr@test.dotmac.io',
    scopes: ['hr:read', 'hr:write', 'customers:read'] as Scope[],
  },
  noAccess: {
    email: 'noaccess@test.dotmac.io',
    scopes: [] as Scope[],
  },
};

/**
 * Create a mock JWT token for testing.
 * In production, tokens are signed by the backend - this is for E2E testing only.
 */
export function createTestToken(scopes: Scope[], expiresIn = 3600): string {
  const secret = process.env.E2E_JWT_SECRET;
  if (!secret) {
    throw new Error('E2E_JWT_SECRET must be set for E2E JWT signing');
  }

  const header = { alg: 'HS256', typ: 'JWT' };
  const scopeKey = scopes.length ? scopes.slice().sort().join('.') : 'none';
  const subjectHash = createHash('sha256').update(scopeKey).digest('hex').slice(0, 16);
  const payload = {
    sub: `e2e-${subjectHash}`,
    email: 'test@dotmac.io',
    scopes,
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + expiresIn,
  };

  const encode = (obj: object) => Buffer.from(JSON.stringify(obj)).toString('base64url');

  const signature = createHmac('sha256', secret)
    .update(`${encode(header)}.${encode(payload)}`)
    .digest('base64url');

  return `${encode(header)}.${encode(payload)}.${signature}`;
}

/**
 * Create an expired test token for testing session expiration.
 */
export function createExpiredToken(scopes: Scope[]): string {
  return createTestToken(scopes, -3600); // Expired 1 hour ago
}

/**
 * Set up authentication in the browser context.
 * Call this in beforeEach or use the authenticated test fixture.
 */
export async function setupAuth(page: Page, scopes: Scope[] = ALL_SCOPES): Promise<void> {
  const token = createTestToken(scopes);
  const baseURL = process.env.E2E_BASE_URL || 'http://localhost:3000';

  await page.context().addCookies([{
    name: 'dotmac_access_token',
    value: token,
    url: baseURL,
    httpOnly: true,
    sameSite: 'Lax',
    secure: baseURL.startsWith('https://'),
    path: '/',
  }]);

  // Navigate to pick up the auth state
  await page.goto('/');
}

/**
 * Clear authentication from the browser context.
 */
export async function clearAuth(page: Page): Promise<void> {
  await page.context().clearCookies();
}

/**
 * Check if the page shows an access denied state.
 */
export async function expectAccessDenied(page: Page): Promise<void> {
  await expect(
    page.getByText(/access denied|not authorized|permission denied/i).first()
  ).toBeVisible({ timeout: 10000 });
}

/**
 * Check if the page shows a login redirect or auth required state.
 */
export async function expectAuthRequired(page: Page): Promise<void> {
  await expect(page).toHaveURL(/\/login|\/auth/);
}

// Extended test fixture with authentication helpers
interface AuthFixtures {
  authenticatedPage: Page;
  authAsAdmin: () => Promise<void>;
  authAsReadonly: () => Promise<void>;
  authAsHr: () => Promise<void>;
  authWithScopes: (scopes: Scope[]) => Promise<void>;
  clearAuth: () => Promise<void>;
}

/**
 * Extended Playwright test with authentication fixtures.
 * Use this instead of the base test for authenticated tests.
 */
export const test = base.extend<AuthFixtures>({
  // Pre-authenticated page with all scopes
  authenticatedPage: async ({ page }, withFixture) => {
    await setupAuth(page, ALL_SCOPES);
    await withFixture(page);
  },

  // Helper to authenticate as admin
  authAsAdmin: async ({ page }, withFixture) => {
    const fn = async () => {
      await setupAuth(page, TEST_USERS.admin.scopes);
    };
    await withFixture(fn);
  },

  // Helper to authenticate as readonly user
  authAsReadonly: async ({ page }, withFixture) => {
    const fn = async () => {
      await setupAuth(page, TEST_USERS.readonly.scopes);
    };
    await withFixture(fn);
  },

  // Helper to authenticate as HR user
  authAsHr: async ({ page }, withFixture) => {
    const fn = async () => {
      await setupAuth(page, TEST_USERS.hr.scopes);
    };
    await withFixture(fn);
  },

  // Helper to authenticate with specific scopes
  authWithScopes: async ({ page }, withFixture) => {
    const fn = async (scopes: Scope[]) => {
      await setupAuth(page, scopes);
    };
    await withFixture(fn);
  },

  // Helper to clear auth
  clearAuth: async ({ page }, withFixture) => {
    const fn = async () => {
      await clearAuth(page);
    };
    await withFixture(fn);
  },
});

export { expect } from '@playwright/test';
