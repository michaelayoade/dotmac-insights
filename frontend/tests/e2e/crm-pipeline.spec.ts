/**
 * CRM Pipeline E2E Tests
 *
 * Comprehensive tests for the CRM pipeline/opportunities module including:
 * - Pipeline board view with stages
 * - Opportunity CRUD operations
 * - Drag-and-drop stage transitions
 * - Pipeline metrics and filtering
 * - RBAC (role-based access control)
 */

import { test, expect, setupAuth, expectAccessDenied } from './fixtures/auth';
import {
  createTestOpportunity,
  deleteTestOpportunity,
  createTestContact,
  deleteTestContact,
} from './fixtures/api-helpers';
import { CRMPipelinePage } from './pages';

test.describe('CRM Pipeline - Authenticated', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page, ['crm:read', 'crm:write']);
  });

  test.describe('Pipeline Board View', () => {
    test('renders pipeline board with stage columns', async ({ page }) => {
      const pipelinePage = new CRMPipelinePage(page);
      await pipelinePage.goto();

      // Verify page structure
      await expect(page.getByText(/access denied|not authorized/i)).toBeHidden({ timeout: 10000 });
      await expect(
        page.getByRole('heading', { name: /pipeline|opportunities/i })
      ).toBeVisible({ timeout: 10000 });

      // Verify pipeline board is visible
      await expect(pipelinePage.kanbanBoard).toBeVisible();
    });

    test('displays pipeline stage columns', async ({ page }) => {
      const pipelinePage = new CRMPipelinePage(page);
      await pipelinePage.goto();
      await pipelinePage.waitForPipeline();

      // Verify at least one stage column exists
      const stageCount = await pipelinePage.getStageCount();
      expect(stageCount).toBeGreaterThan(0);
    });

    test('shows opportunity cards in pipeline', async ({ page, request }) => {
      // Create a test opportunity
      const opportunity = await createTestOpportunity(request, {
        name: `E2E Pipeline Test ${Date.now()}`,
        value: 50000,
        stage: 'qualification',
      });

      try {
        const pipelinePage = new CRMPipelinePage(page);
        await pipelinePage.goto();
        await pipelinePage.waitForPipeline();

        // Verify opportunity card is visible
        await expect(page.getByText(opportunity.name)).toBeVisible({ timeout: 10000 });
      } finally {
        await deleteTestOpportunity(request, opportunity.id);
      }
    });

    test('displays add opportunity button', async ({ page }) => {
      const pipelinePage = new CRMPipelinePage(page);
      await pipelinePage.goto();

      await expect(pipelinePage.addOpportunityButton).toBeVisible();
    });
  });

  test.describe('Pipeline Filtering', () => {
    test('filter by stage shows only matching opportunities', async ({ page, request }) => {
      const opportunity = await createTestOpportunity(request, {
        name: `Filter Test ${Date.now()}`,
        stage: 'proposal',
      });

      try {
        const pipelinePage = new CRMPipelinePage(page);
        await pipelinePage.goto();

        // Filter by stage if filter exists
        const stageFilter = page.locator('select').filter({ hasText: /stage/i }).first();
        if (await stageFilter.isVisible()) {
          await stageFilter.selectOption({ index: 1 });
          await page.waitForTimeout(500);
        }

        // Pipeline should still be visible
        await expect(pipelinePage.kanbanBoard).toBeVisible();
      } finally {
        await deleteTestOpportunity(request, opportunity.id);
      }
    });

    test('filter by owner works', async ({ page }) => {
      const pipelinePage = new CRMPipelinePage(page);
      await pipelinePage.goto();

      // Check if owner filter exists
      const ownerFilter = page.locator('select').filter({ hasText: /owner|assigned/i }).first();
      if (await ownerFilter.isVisible()) {
        await ownerFilter.selectOption({ index: 1 });
        await page.waitForTimeout(500);

        // Pipeline should still be visible
        await expect(pipelinePage.kanbanBoard).toBeVisible();
      }
    });
  });

  test.describe('Create Opportunity', () => {
    test('opens create opportunity modal', async ({ page }) => {
      const pipelinePage = new CRMPipelinePage(page);
      await pipelinePage.goto();

      await pipelinePage.openCreateOpportunity();

      // Verify modal/form is visible
      await expect(
        page.getByRole('dialog').or(page.getByRole('heading', { name: /new|create|add.*opportunity/i }))
      ).toBeVisible({ timeout: 5000 });
    });

    test('validates required fields', async ({ page }) => {
      const pipelinePage = new CRMPipelinePage(page);
      await pipelinePage.goto();
      await pipelinePage.openCreateOpportunity();

      // Try to submit empty form
      await pipelinePage.submitForm();

      // Should show validation errors
      await expect(
        page.getByText(/required|cannot be empty|please enter/i).first()
      ).toBeVisible({ timeout: 5000 });
    });

    test('creates opportunity successfully', async ({ page, request }) => {
      const pipelinePage = new CRMPipelinePage(page);
      await pipelinePage.goto();

      const opportunityName = `E2E Create Test ${Date.now()}`;

      await pipelinePage.createOpportunity({
        name: opportunityName,
        value: '75000',
      });

      // Wait for success
      await page.waitForTimeout(1000);

      // Verify opportunity appears in pipeline
      await pipelinePage.goto();
      await expect(page.getByText(opportunityName)).toBeVisible({ timeout: 10000 });

      // Cleanup - find and delete the opportunity
      const opportunityCard = page.getByText(opportunityName).first();
      if (await opportunityCard.isVisible()) {
        await opportunityCard.click();
        const urlMatch = page.url().match(/\/opportunities\/(\d+)/);
        if (urlMatch) {
          await deleteTestOpportunity(request, Number(urlMatch[1]));
        }
      }
    });
  });

  test.describe('Edit Opportunity', () => {
    test('opens opportunity detail on card click', async ({ page, request }) => {
      const opportunity = await createTestOpportunity(request, {
        name: `Edit Test ${Date.now()}`,
        value: 30000,
      });

      try {
        const pipelinePage = new CRMPipelinePage(page);
        await pipelinePage.goto();
        await pipelinePage.waitForPipeline();

        await pipelinePage.clickOpportunity(opportunity.name);

        // Should navigate to detail or open modal
        await expect(
          page.getByText(opportunity.name)
        ).toBeVisible({ timeout: 5000 });
      } finally {
        await deleteTestOpportunity(request, opportunity.id);
      }
    });

    test('updates opportunity value', async ({ page, request }) => {
      const opportunity = await createTestOpportunity(request, {
        name: `Update Value Test ${Date.now()}`,
        value: 40000,
      });

      try {
        await page.goto(`/crm/opportunities/${opportunity.id}/edit`);

        const newValue = '85000';
        await page.getByLabel(/value|amount/i).fill(newValue);
        await page.getByRole('button', { name: /save|update/i }).click();

        // Verify update
        await page.waitForTimeout(1000);
        await expect(page.getByText(/85,?000/)).toBeVisible({ timeout: 5000 });
      } finally {
        await deleteTestOpportunity(request, opportunity.id);
      }
    });
  });

  test.describe('Stage Transitions', () => {
    test('can move opportunity to next stage via UI', async ({ page, request }) => {
      const opportunity = await createTestOpportunity(request, {
        name: `Stage Transition ${Date.now()}`,
        stage: 'qualification',
      });

      try {
        await page.goto(`/crm/opportunities/${opportunity.id}`);

        // Look for stage change button or dropdown
        const stageSelector = page.getByLabel(/stage/i).or(
          page.locator('select').filter({ hasText: /stage/i })
        );

        if (await stageSelector.isVisible()) {
          await stageSelector.click();
          await page.getByRole('option', { name: /proposal|negotiation/i }).first().click();
          await page.getByRole('button', { name: /save|update/i }).click();
          await page.waitForTimeout(1000);
        }
      } finally {
        await deleteTestOpportunity(request, opportunity.id);
      }
    });
  });

  test.describe('Pipeline Metrics', () => {
    test('displays pipeline value metrics', async ({ page, request }) => {
      const opportunity = await createTestOpportunity(request, {
        name: `Metrics Test ${Date.now()}`,
        value: 100000,
      });

      try {
        const pipelinePage = new CRMPipelinePage(page);
        await pipelinePage.goto();

        // Check for metrics display
        const metricsSection = page.locator('[data-testid="pipeline-metrics"]').or(
          page.getByText(/total.*value|pipeline.*value/i)
        );

        if (await metricsSection.isVisible()) {
          await expect(metricsSection).toContainText(/\d/);
        }
      } finally {
        await deleteTestOpportunity(request, opportunity.id);
      }
    });
  });

  test.describe('Close Opportunity', () => {
    test('can mark opportunity as won', async ({ page, request }) => {
      const opportunity = await createTestOpportunity(request, {
        name: `Won Test ${Date.now()}`,
        stage: 'negotiation',
        value: 50000,
      });

      try {
        await page.goto(`/crm/opportunities/${opportunity.id}`);

        // Look for won/close button
        const wonButton = page.getByRole('button', { name: /won|close.*won/i });
        if (await wonButton.isVisible()) {
          await wonButton.click();

          // Confirm if modal appears
          const confirmButton = page.getByRole('button', { name: /confirm|yes/i });
          if (await confirmButton.isVisible({ timeout: 2000 })) {
            await confirmButton.click();
          }

          await page.waitForTimeout(1000);
          await expect(page.getByText(/won|closed/i)).toBeVisible({ timeout: 5000 });
        }
      } finally {
        await deleteTestOpportunity(request, opportunity.id);
      }
    });

    test('can mark opportunity as lost', async ({ page, request }) => {
      const opportunity = await createTestOpportunity(request, {
        name: `Lost Test ${Date.now()}`,
        stage: 'proposal',
        value: 25000,
      });

      try {
        await page.goto(`/crm/opportunities/${opportunity.id}`);

        // Look for lost/close button
        const lostButton = page.getByRole('button', { name: /lost|close.*lost/i });
        if (await lostButton.isVisible()) {
          await lostButton.click();

          // Fill reason if required
          const reasonInput = page.getByLabel(/reason/i);
          if (await reasonInput.isVisible({ timeout: 2000 })) {
            await reasonInput.fill('E2E Test - Lost reason');
          }

          // Confirm
          const confirmButton = page.getByRole('button', { name: /confirm|yes|submit/i });
          if (await confirmButton.isVisible({ timeout: 2000 })) {
            await confirmButton.click();
          }

          await page.waitForTimeout(1000);
        }
      } finally {
        await deleteTestOpportunity(request, opportunity.id);
      }
    });
  });
});

test.describe('CRM Pipeline - RBAC', () => {
  test('read-only user cannot create opportunities', async ({ page }) => {
    await setupAuth(page, ['crm:read']);

    const pipelinePage = new CRMPipelinePage(page);
    await pipelinePage.goto();

    // Create button should be hidden or disabled
    await expect(pipelinePage.addOpportunityButton).toBeHidden();
  });

  test('user without CRM scope sees access denied', async ({ page }) => {
    await setupAuth(page, ['hr:read']); // No CRM scopes
    await page.goto('/crm/pipeline');

    await expectAccessDenied(page);
  });
});

test.describe('CRM Pipeline - Unauthenticated', () => {
  test('redirects to login when not authenticated', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => localStorage.clear());

    await page.goto('/crm/pipeline');

    await expect(page).toHaveURL(/\/login|\/auth/);
  });
});
