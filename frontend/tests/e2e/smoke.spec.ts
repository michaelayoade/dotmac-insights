import { test, expect, setupAuth } from './fixtures/auth';
import { SMOKE_PAGES } from './fixtures/smoke-pages';

/**
 * Smoke tests verify that pages load without server errors.
 * We check:
 * 1. Page responds with status < 500
 * 2. Loading indicators disappear (page finishes loading)
 * 3. Main content area is visible
 * 4. No uncaught JavaScript exceptions
 */

// Increase timeout for smoke tests due to slow API responses
test.setTimeout(180_000); // 3 minutes per test

const LOADING_SELECTORS = '.animate-spin, [aria-busy="true"], [role="progressbar"]';

for (const [moduleName, pages] of Object.entries(SMOKE_PAGES)) {
  test.describe(`Smoke Tests - ${moduleName}`, () => {
    for (const pageConfig of pages) {
      test(`${pageConfig.name} (${pageConfig.path})`, async ({ page }) => {
        if (pageConfig.skipReason) {
          test.skip(true, pageConfig.skipReason);
          return;
        }

        if (pageConfig.path.includes('[')) {
          test.skip(true, 'Dynamic route requires real data');
          return;
        }

        await setupAuth(page, pageConfig.scopes);

        // Track uncaught exceptions only (not console errors)
        const pageErrors: string[] = [];
        page.on('pageerror', (err) => {
          pageErrors.push(err.message);
        });

        // Navigate and check response status
        const response = await page.goto(pageConfig.path, { waitUntil: 'domcontentloaded' });
        expect(response?.status() ?? 0).toBeLessThan(500);

        // Wait for loading indicators to disappear (page finished loading)
        const loadingIndicator = page.locator(LOADING_SELECTORS).first();
        await expect(loadingIndicator).toBeHidden({ timeout: 120_000 });

        // Verify main content is visible
        const mainContent = page.locator('main, [role="main"], h1, h2, [data-testid="page-content"]').first();
        await expect(mainContent).toBeVisible({ timeout: 30_000 });

        // Only fail on uncaught exceptions (not console.error)
        const criticalErrors = pageErrors.filter(
          (error) => !error.includes('ResizeObserver') && !error.includes('hydration')
        );
        expect(criticalErrors).toHaveLength(0);
      });
    }
  });
}
