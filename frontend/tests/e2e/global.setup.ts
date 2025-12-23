import { request } from '@playwright/test';
import { createTestToken, type Scope } from './fixtures/auth';
import { MODULES } from '../../lib/config/modules';

const apiURL = process.env.E2E_API_URL || 'http://localhost:8000';

async function waitForApiReady(maxWaitMs: number): Promise<void> {
  const start = Date.now();
  const context = await request.newContext();

  try {
    while (Date.now() - start < maxWaitMs) {
      try {
        const response = await context.get(`${apiURL}/health`);
        if (response.ok()) {
          return;
        }
      } catch {
        // API not ready yet
      }
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  } finally {
    await context.dispose();
  }

  throw new Error(`API not ready at ${apiURL} after ${maxWaitMs}ms`);
}

async function validateAdminScopes(): Promise<void> {
  const requiredScopes = new Set<Scope>();
  for (const moduleDef of MODULES) {
    for (const scope of moduleDef.requiredScopes || []) {
      requiredScopes.add(scope);
    }
  }

  const token = createTestToken(['*']);
  const context = await request.newContext({
    extraHTTPHeaders: {
      Authorization: `Bearer ${token}`,
      Accept: 'application/json',
    },
  });

  try {
    const response = await context.get(`${apiURL}/api/admin/me`);
    if (!response.ok()) {
      throw new Error(`Admin scope check failed: ${response.status()} ${response.statusText()}`);
    }
    const data = await response.json();
    const permissions: string[] = Array.isArray(data.permissions) ? data.permissions : [];
    if (permissions.includes('*')) {
      return;
    }
    const missing = [...requiredScopes].filter((scope) => !permissions.includes(scope));
    if (missing.length > 0) {
      throw new Error(`Admin scope check failed: missing ${missing.join(', ')}`);
    }
  } finally {
    await context.dispose();
  }
}

export default async function globalSetup(): Promise<void> {
  const maxWaitMs = process.env.CI ? 60000 : 30000;
  await waitForApiReady(maxWaitMs);
  await validateAdminScopes();
}
