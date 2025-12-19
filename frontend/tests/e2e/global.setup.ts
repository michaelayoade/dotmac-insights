import { request } from '@playwright/test';

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

export default async function globalSetup(): Promise<void> {
  const maxWaitMs = process.env.CI ? 60000 : 30000;
  await waitForApiReady(maxWaitMs);
}
