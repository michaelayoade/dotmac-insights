import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.E2E_BASE_URL || 'http://localhost:3000';
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  // Run tests in parallel
  fullyParallel: true,
  // Fail the build on CI if you accidentally left test.only in the source code
  forbidOnly: !!process.env.CI,
  // Retry on CI only
  retries: process.env.CI ? 2 : 0,
  // Opt out of parallel tests on CI to reduce flakiness
  workers: process.env.CI ? 1 : undefined,
  // Reporter to use
  reporter: process.env.CI
    ? [['html', { open: 'never' }], ['github']]
    : [['html', { open: 'on-failure' }]],
  use: {
    baseURL,
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    // Context options for API calls
    extraHTTPHeaders: {
      Accept: 'application/json',
    },
  },
  // Global setup for API readiness check
  globalSetup: './tests/e2e/global.setup.ts',
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
      },
      dependencies: [],
    },
    // Mobile viewport tests (optional)
    {
      name: 'mobile',
      use: {
        ...devices['iPhone 13'],
      },
      testIgnore: ['**/admin/**', '**/settings/**'], // Skip admin tests on mobile
    },
  ],
  // Web server configuration for local development
  webServer: process.env.CI
    ? undefined
    : {
        command: 'npm run dev',
        url: baseURL,
        reuseExistingServer: true,
        timeout: 120_000,
      },
});
