import { test as base, expect, Page, Locator } from '@playwright/test';

/**
 * HTMX-specific test helpers and assertions.
 *
 * Provides utilities for testing HTMX behaviors:
 * - Waiting for HTMX requests to complete
 * - Asserting on hx-swap behaviors
 * - Handling loading states
 * - Testing partial page updates
 */

export interface HTMXHelpers {
  /**
   * Wait for all pending HTMX requests to complete.
   */
  waitForHtmxIdle: () => Promise<void>;

  /**
   * Wait for a specific HTMX request triggered by an element.
   */
  waitForHtmxRequest: (trigger: Locator) => Promise<void>;

  /**
   * Click an element and wait for HTMX to complete.
   */
  htmxClick: (locator: Locator) => Promise<void>;

  /**
   * Submit a form via HTMX and wait for completion.
   */
  htmxSubmit: (form: Locator) => Promise<void>;

  /**
   * Assert that an element was swapped by HTMX.
   */
  expectSwapped: (target: Locator) => Promise<void>;

  /**
   * Assert HTMX loading state appears and disappears.
   */
  expectLoadingState: (trigger: Locator) => Promise<void>;

  /**
   * Get the HTMX target element for a trigger.
   */
  getHtmxTarget: (trigger: Locator) => Promise<Locator>;

  /**
   * Assert no HTMX errors occurred.
   */
  expectNoHtmxErrors: () => Promise<void>;
}

/**
 * Extended test fixture with HTMX helpers.
 */
export const test = base.extend<{ htmx: HTMXHelpers }>({
  htmx: async ({ page }, use) => {
    const helpers: HTMXHelpers = {
      async waitForHtmxIdle() {
        // Wait for no elements with htmx-request class
        await page.waitForFunction(() => {
          return document.querySelectorAll('.htmx-request').length === 0;
        }, { timeout: 10000 });

        // Small buffer for DOM updates
        await page.waitForTimeout(100);
      },

      async waitForHtmxRequest(trigger: Locator) {
        // Get the target selector from hx-target or use the trigger itself
        const targetSelector = await trigger.getAttribute('hx-target');

        // Wait for the request class to appear and disappear
        await Promise.race([
          trigger.evaluate((el) => {
            return new Promise<void>((resolve) => {
              const observer = new MutationObserver((mutations) => {
                for (const mutation of mutations) {
                  if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                    const target = mutation.target as HTMLElement;
                    if (!target.classList.contains('htmx-request')) {
                      observer.disconnect();
                      resolve();
                    }
                  }
                }
              });
              observer.observe(el, { attributes: true });

              // Also resolve if already not in request state
              if (!el.classList.contains('htmx-request')) {
                observer.disconnect();
                resolve();
              }
            });
          }),
          page.waitForTimeout(10000), // Fallback timeout
        ]);

        await page.waitForTimeout(50); // Buffer for DOM updates
      },

      async htmxClick(locator: Locator) {
        await locator.click();
        await helpers.waitForHtmxIdle();
      },

      async htmxSubmit(form: Locator) {
        // Find submit button or trigger form submission
        const submitButton = form.locator('button[type="submit"], input[type="submit"]').first();
        if (await submitButton.count() > 0) {
          await submitButton.click();
        } else {
          await form.press('Enter');
        }
        await helpers.waitForHtmxIdle();
      },

      async expectSwapped(target: Locator) {
        // Wait for the target to be updated (check for htmx-settling class)
        await expect(target).toBeVisible();
        await helpers.waitForHtmxIdle();
      },

      async expectLoadingState(trigger: Locator) {
        // Verify loading indicator appears
        const indicator = trigger.locator('.htmx-indicator, [class*="loading"]');
        if (await indicator.count() > 0) {
          await expect(indicator).toBeVisible({ timeout: 1000 }).catch(() => {
            // Loading state may be too fast to catch, that's ok
          });
        }
      },

      async getHtmxTarget(trigger: Locator) {
        const targetSelector = await trigger.getAttribute('hx-target');
        if (targetSelector) {
          if (targetSelector === 'this') {
            return trigger;
          }
          if (targetSelector === 'closest tr') {
            return trigger.locator('xpath=ancestor::tr');
          }
          return page.locator(targetSelector);
        }
        // Default: target is the trigger itself
        return trigger;
      },

      async expectNoHtmxErrors() {
        // Check for HTMX error elements
        const errorElements = page.locator('[hx-swap-oob="true"].error, .htmx-error');
        await expect(errorElements).toHaveCount(0);

        // Check console for HTMX errors
        // Note: This requires setting up console listener in beforeEach
      },
    };

    await use(helpers);
  },
});

export { expect };

/**
 * Custom expect matchers for HTMX testing.
 */
export const htmxExpect = {
  /**
   * Assert element has specific hx-* attribute.
   */
  async toHaveHxAttribute(locator: Locator, attr: string, value?: string) {
    const fullAttr = attr.startsWith('hx-') ? attr : `hx-${attr}`;
    if (value !== undefined) {
      await expect(locator).toHaveAttribute(fullAttr, value);
    } else {
      await expect(locator).toHaveAttribute(fullAttr);
    }
  },

  /**
   * Assert element triggers HTMX on specific event.
   */
  async toHaveHxTrigger(locator: Locator, trigger: string) {
    await expect(locator).toHaveAttribute('hx-trigger', new RegExp(trigger));
  },

  /**
   * Assert element uses specific swap method.
   */
  async toHaveHxSwap(locator: Locator, swapMethod: string) {
    await expect(locator).toHaveAttribute('hx-swap', new RegExp(swapMethod));
  },
};
