import { defineConfig, devices } from '@playwright/test';

const defaultE2ESecret = 'e2e-secret';
if (!process.env.E2E_JWT_SECRET) {
  process.env.E2E_JWT_SECRET = defaultE2ESecret;
}
if (!process.env.E2E_AUTH_ENABLED) {
  process.env.E2E_AUTH_ENABLED = 'true';
}
const e2eWorkers = process.env.E2E_WORKERS ? Number(process.env.E2E_WORKERS) : 1;
const fullyParallel = process.env.E2E_FULLY_PARALLEL === 'true';

/**
 * Playwright configuration for DotMac Insights HTMX E2E tests.
 *
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  // Test directory
  testDir: './tests/e2e-browser',

  // Global setup for authentication
  globalSetup: './tests/e2e-browser/global-setup.ts',

  // Run tests in parallel
  fullyParallel,

  // Fail the build on CI if test.only is left in the source code
  forbidOnly: !!process.env.CI,

  // Retry on CI only
  retries: process.env.CI ? 2 : 0,

  // Limit parallel workers on CI
  workers: process.env.CI ? 1 : e2eWorkers,

  // Reporter configuration
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list'],
    ...(process.env.CI ? [['github'] as const] : []),
  ],

  // Shared settings for all projects
  use: {
    // Base URL for the application
    baseURL: process.env.BASE_URL || 'http://localhost:8000',

    // Collect trace on first retry
    trace: 'on-first-retry',

    // Screenshot on failure
    screenshot: 'only-on-failure',

    // Video on failure
    video: 'on-first-retry',

    // Default timeout for actions
    actionTimeout: 10000,

    // Default navigation timeout
    navigationTimeout: 30000,
  },

  // Test timeout
  timeout: 60000,

  // Expect timeout
  expect: {
    timeout: 10000,
  },

  // Configure projects for different browsers
  projects: [
    // Desktop browsers with superuser auth
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        storageState: './tests/e2e-browser/.auth/superuser.json',
      },
    },
    {
      name: 'firefox',
      use: {
        ...devices['Desktop Firefox'],
        storageState: './tests/e2e-browser/.auth/superuser.json',
      },
    },
    {
      name: 'webkit',
      use: {
        ...devices['Desktop Safari'],
        storageState: './tests/e2e-browser/.auth/superuser.json',
      },
    },

    // Mobile viewports
    {
      name: 'mobile-chrome',
      use: {
        ...devices['Pixel 5'],
        storageState: './tests/e2e-browser/.auth/superuser.json',
      },
    },
    {
      name: 'mobile-safari',
      use: {
        ...devices['iPhone 12'],
        storageState: './tests/e2e-browser/.auth/superuser.json',
      },
    },
  ],

  // Run local dev server before starting the tests
  webServer: process.env.CI ? undefined : {
    command: 'poetry run uvicorn app.main:app --host 0.0.0.0 --port 8000',
    url: 'http://localhost:8000/health',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },

  // Output directory for test artifacts
  outputDir: 'test-results/',
});
