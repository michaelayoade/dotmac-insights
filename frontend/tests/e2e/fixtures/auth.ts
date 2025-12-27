/**
 * Playwright auth fixtures for authenticated E2E tests.
 *
 * Sets up an httpOnly cookie with a test JWT token containing the specified scopes.
 * Uses browser context cookies to persist auth across tests for efficiency.
 */

import { createHmac, createHash } from 'crypto';
import { test as base, expect, type Page } from '@playwright/test';

// All available scopes matching the backend RBAC system
// Keep in sync with frontend/lib/auth-context.tsx and backend Require() calls
export type Scope =
  // Wildcard
  | '*'
  // Admin scopes
  | 'admin:read'
  | 'admin:write'
  | 'admin:users:read'
  | 'admin:users:write'
  | 'admin:roles:read'
  | 'admin:roles:write'
  | 'admin:tokens:read'
  | 'admin:tokens:write'
  // Analytics & Explorer
  | 'analytics:read'
  | 'explorer:read'
  // Sync scopes
  | 'sync:read'
  | 'sync:write'
  | 'sync:splynx:read'
  | 'sync:splynx:write'
  | 'sync:erpnext:write'
  | 'sync:chatwoot:write'
  // Customer & Contact scopes
  | 'customers:read'
  | 'customers:write'
  | 'contacts:read'
  | 'contacts:write'
  // CRM scopes
  | 'crm:read'
  | 'crm:write'
  | 'crm:admin'
  // HR scopes
  | 'hr:read'
  | 'hr:write'
  | 'hr:admin'
  // Fleet scopes
  | 'fleet:read'
  | 'fleet:write'
  // Support scopes
  | 'support:read'
  | 'support:write'
  | 'support:admin'
  | 'support:automation:read'
  | 'support:automation:write'
  | 'support:csat:read'
  | 'support:csat:write'
  | 'support:kb:read'
  | 'support:kb:write'
  | 'support:sla:read'
  | 'support:sla:write'
  // Tickets scopes
  | 'tickets:read'
  | 'tickets:write'
  // Inbox scopes
  | 'inbox:read'
  | 'inbox:write'
  // Accounting scopes
  | 'accounting:read'
  | 'accounting:write'
  // Assets scopes
  | 'assets:read'
  | 'assets:write'
  // Books/Finance scopes
  | 'books:read'
  | 'books:write'
  | 'books:approve'
  | 'books:admin'
  | 'books:close'
  | 'billing:write'
  // Expenses scopes
  | 'expenses:read'
  | 'expenses:write'
  // Field Service scopes
  | 'field-service:read'
  | 'field-service:write'
  | 'field-service:dispatch'
  | 'field-service:admin'
  | 'field-service:mobile'
  // Purchasing scopes
  | 'purchasing:read'
  | 'purchasing:write'
  // Projects scopes
  | 'projects:read'
  | 'projects:write'
  // Reports scopes
  | 'reports:read'
  | 'reports:write'
  // Payments & Banking scopes
  | 'payments:read'
  | 'payments:write'
  | 'openbanking:read'
  | 'openbanking:write'
  | 'gateway:read'
  | 'gateway:write'
  // Inventory scopes
  | 'inventory:read'
  | 'inventory:write'
  | 'inventory:approve'
  // Sales scopes
  | 'sales:read'
  | 'sales:write'
  // Settings scopes
  | 'settings:read'
  | 'settings:write'
  | 'settings:audit_view'
  | 'settings:test'
  // Performance Management scopes
  | 'performance:read'
  | 'performance:write'
  | 'performance:admin'
  | 'performance:review'
  | 'performance:self'
  | 'performance:team';

// Common scope sets for E2E testing - use '*' for admin tests
const ALL_SCOPES: Scope[] = ['*'];

// Test user configurations for different role scenarios
export const TEST_USERS = {
  admin: {
    email: 'admin@test.dotmac.io',
    scopes: ['*'] as Scope[],
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
 *
 * Uses Playwright route interception to mock the /api/admin/me endpoint,
 * avoiding cross-origin cookie issues between frontend and backend.
 */
export async function setupAuth(page: Page, scopes: Scope[] = ALL_SCOPES): Promise<void> {
  const allowOrigin = process.env.E2E_BASE_URL || 'http://localhost:3000';
  const apiBase = process.env.E2E_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  const token = createTestToken(scopes);
  const corsHeaders = {
    'access-control-allow-origin': allowOrigin,
    'access-control-allow-credentials': 'true',
    'access-control-allow-headers': 'content-type, authorization',
    'access-control-allow-methods': 'GET, POST, OPTIONS',
  };

  // Extract domain from apiBase URL for cookie
  const apiUrl = new URL(apiBase);
  await page.context().addCookies([{
    name: 'dotmac_access_token',
    value: token,
    domain: apiUrl.hostname,
    path: '/',
    httpOnly: true,
    sameSite: 'Lax' as const,
    secure: apiBase.startsWith('https'),
  }]);

  // Mock the /api/admin/me endpoint to return the test user's permissions
  // This avoids cross-origin cookie issues between frontend and backend
  // Set route on browser context so it persists across all navigations
  // Use regex for reliable matching across any origin
  await page.context().route(/.*\/api\/admin\/me.*/, async (route) => {
    console.log(`[E2E Auth] Intercepted ${route.request().method()} ${route.request().url()}`);

    if (route.request().method() === 'OPTIONS') {
      await route.fulfill({
        status: 204,
        headers: corsHeaders,
      });
      return;
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      headers: corsHeaders,
      body: JSON.stringify({
        id: 'e2e-test-user',
        email: 'test@dotmac.io',
        permissions: scopes,
      }),
    });
  });

  // Navigate to pick up the auth state
  await page.goto('/');
}

/**
 * Clear authentication from the browser context.
 */
export async function clearAuth(page: Page): Promise<void> {
  const allowOrigin = process.env.E2E_BASE_URL || 'http://localhost:3000';
  const corsHeaders = {
    'access-control-allow-origin': allowOrigin,
    'access-control-allow-credentials': 'true',
    'access-control-allow-headers': 'content-type, authorization',
    'access-control-allow-methods': 'GET, POST, OPTIONS',
  };

  await page.context().clearCookies();
  // Remove the mock route to simulate unauthenticated state
  await page.context().unroute('**/admin/me**');
  // Re-add route that returns 401
  await page.context().route('**/admin/me**', async (route) => {
    if (route.request().method() === 'OPTIONS') {
      await route.fulfill({
        status: 204,
        headers: corsHeaders,
      });
      return;
    }

    await route.fulfill({
      status: 401,
      contentType: 'application/json',
      headers: corsHeaders,
      body: JSON.stringify({ detail: 'Not authenticated' }),
    });
  });
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
