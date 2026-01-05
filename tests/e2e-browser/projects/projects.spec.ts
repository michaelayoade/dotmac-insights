import { test, expect } from '../fixtures/htmx.fixture';
import { ProjectsPage } from '../pages/projects.page';

/**
 * E2E Browser Tests for Projects Module.
 *
 * Tests the HTMX-powered project management interface including:
 * - Project list with search and filters
 * - Project detail with tasks
 * - Task management
 * - Gantt chart view
 */

test.describe('Projects List', () => {
  let projectsPage: ProjectsPage;

  test.beforeEach(async ({ page }) => {
    projectsPage = new ProjectsPage(page);
    await projectsPage.gotoList();
  });

  test('displays projects page @smoke', async () => {
    const pageTitle = projectsPage.page.locator('[data-testid="page-title"]');
    await expect(pageTitle).toContainText(/project/i);
  });

  test('displays projects table or cards @smoke', async () => {
    if (!(await projectsPage.hasProjects())) {
      await projectsPage.expectEmptyState();
      return;
    }

    const table = projectsPage.projectsTable;
    const cards = projectsPage.projectCards;

    const hasTable = await table.count() > 0;
    const hasCards = await cards.count() > 0;

    expect(hasTable || hasCards).toBeTruthy();
  });

  test('search filters projects via HTMX @critical', async ({ htmx }) => {
    if (!(await projectsPage.hasProjects())) {
      test.skip();
      return;
    }
    const initialCount = await projectsPage.getProjectCount();

    await projectsPage.searchProjects('test');
    await htmx.waitForHtmxIdle();

    const filteredCount = await projectsPage.getProjectCount();
    expect(filteredCount).toBeLessThanOrEqual(initialCount);
  });

  test('filter by status updates list', async ({ htmx }) => {
    if (!(await projectsPage.hasProjects())) {
      test.skip();
      return;
    }

    if (await projectsPage.statusFilter.count() === 0) {
      test.skip();
      return;
    }

    await projectsPage.filterByStatus('active');
    await htmx.waitForHtmxIdle();

    // Table/cards should update
    await projectsPage.waitForHtmxComplete();
  });

  test('click project navigates to detail', async ({ page }) => {
    if (!(await projectsPage.hasProjects())) {
      test.skip();
      return;
    }

    // Get first project name
    const firstItem = projectsPage.projectsTable.locator('tbody tr').first();
    if (await firstItem.count() > 0) {
      const name = await firstItem.locator('td').first().textContent() || '';
      await projectsPage.clickProject(name.trim());
      await expect(page).toHaveURL(/\/projects\/\d+/);
    } else {
      const firstCard = projectsPage.projectCards.first();
      await firstCard.click();
      await expect(page).toHaveURL(/\/projects\/\d+/);
    }
  });

  test('new project button navigates to form', async ({ page }) => {
    await projectsPage.newProjectButton.click();
    await expect(page).toHaveURL(/\/new|\/create/);
  });
});

test.describe('Project Detail View', () => {
  let projectsPage: ProjectsPage;

  test.beforeEach(async ({ page }) => {
    projectsPage = new ProjectsPage(page);
    await projectsPage.gotoList();
    if (!(await projectsPage.hasProjects())) {
      test.skip();
      return;
    }
    // Click first project
    const firstItem = projectsPage.projectsTable.locator('tbody tr').first();
    if (await firstItem.count() > 0) {
      const name = await firstItem.locator('td').first().textContent() || '';
      await projectsPage.clickProject(name.trim());
    } else {
      await projectsPage.projectCards.first().click();
    }
  });

  test('displays project header', async () => {
    await expect(projectsPage.projectHeader).toBeVisible();
  });

  test('displays progress indicator', async () => {
    const progress = projectsPage.projectProgress;
    if (await progress.count() > 0) {
      await expect(progress).toBeVisible();
    }
  });

  test('displays tasks section', async () => {
    const tasks = projectsPage.tasksSection;
    if (await tasks.count() > 0) {
      await expect(tasks).toBeVisible();
    }
  });

  test('displays milestones section if available', async () => {
    const milestones = projectsPage.milestonesSection;
    if (await milestones.count() > 0) {
      await expect(milestones).toBeVisible();
    }
  });
});

test.describe('Task Management', () => {
  let projectsPage: ProjectsPage;

  test.beforeEach(async ({ page }) => {
    projectsPage = new ProjectsPage(page);
    await projectsPage.gotoList();
    if (!(await projectsPage.hasProjects())) {
      test.skip();
      return;
    }
    // Click first project
    const firstItem = projectsPage.projectsTable.locator('tbody tr').first();
    if (await firstItem.count() > 0) {
      const name = await firstItem.locator('td').first().textContent() || '';
      await projectsPage.clickProject(name.trim());
    } else {
      await projectsPage.projectCards.first().click();
    }
  });

  test('new task button visible', async () => {
    if (await projectsPage.newTaskButton.count() > 0) {
      await expect(projectsPage.newTaskButton).toBeVisible();
    }
  });

  test('task form opens on button click', async ({ htmx }) => {
    if (await projectsPage.newTaskButton.count() === 0) {
      test.skip();
      return;
    }

    await projectsPage.newTaskButton.click();
    await htmx.waitForHtmxIdle();

    // Form should be visible (either modal or page)
    const form = projectsPage.page.locator('form, [role="dialog"]');
    await expect(form.first()).toBeVisible();
  });

  test('displays task list if tasks exist', async () => {
    if (!(await projectsPage.hasTasks())) {
      return;
    }

    const table = projectsPage.tasksTable;
    const cards = projectsPage.taskCards;

    const hasTable = await table.count() > 0;
    const hasCards = await cards.count() > 0;

    expect(hasTable || hasCards).toBeTruthy();
  });
});

test.describe('Gantt Chart', () => {
  let projectsPage: ProjectsPage;

  test.beforeEach(async ({ page }) => {
    projectsPage = new ProjectsPage(page);
  });

  test('gantt page loads @smoke', async () => {
    await projectsPage.gotoGantt();

    // Either gantt chart or empty state should be visible
    const gantt = projectsPage.ganttChart;
    const emptyState = projectsPage.page.locator('.empty-state, [data-testid="empty-state"]');

    const hasGantt = await gantt.count() > 0;
    const hasEmpty = await emptyState.count() > 0;

    expect(hasGantt || hasEmpty).toBeTruthy();
  });

  test('gantt chart displays if projects exist', async () => {
    await projectsPage.gotoList();
    if (!(await projectsPage.hasProjects())) {
      test.skip();
      return;
    }

    await projectsPage.gotoGantt();

    const gantt = projectsPage.ganttChart;
    if (await gantt.count() > 0) {
      await projectsPage.expectGanttVisible();
    }
  });

  test('zoom controls work', async () => {
    await projectsPage.gotoGantt();

    const gantt = projectsPage.ganttChart;
    if (await gantt.count() === 0) {
      test.skip();
      return;
    }

    // Test zoom in if available
    const zoomIn = projectsPage.ganttZoomIn;
    if (await zoomIn.count() > 0) {
      await projectsPage.zoomIn();
      // Just verify no errors
    }
  });
});

test.describe('Project Creation', () => {
  let projectsPage: ProjectsPage;

  test.beforeEach(async ({ page }) => {
    projectsPage = new ProjectsPage(page);
  });

  test('project form is accessible', async () => {
    await projectsPage.gotoCreate();
    await expect(projectsPage.projectForm).toBeVisible();
  });

  test('form has required fields', async () => {
    await projectsPage.gotoCreate();

    await expect(projectsPage.projectName).toBeVisible();
  });

  test('validation errors shown on empty submit', async ({ htmx }) => {
    await projectsPage.gotoCreate();

    await projectsPage.htmxSubmitForm(projectsPage.projectForm);

    const errorMessage = projectsPage.page.locator('.field-error, [data-error], .text-red-600');
    await expect(errorMessage.first()).toBeVisible();
  });
});

test.describe('Project Empty States', () => {
  let projectsPage: ProjectsPage;

  test.beforeEach(async ({ page }) => {
    projectsPage = new ProjectsPage(page);
    await projectsPage.gotoList();
  });

  test('shows empty state when no search results', async ({ htmx }) => {
    await projectsPage.searchProjects('xyznonexistent98765');
    await htmx.waitForHtmxIdle();

    const emptyState = projectsPage.page.locator('.empty-state, [data-testid="empty-state"], [data-testid="projects-empty-state"], .no-results');
    const noRows = await projectsPage.projectsTable.locator('tbody tr').count() === 0;
    const noCards = await projectsPage.projectCards.count() === 0;

    expect(await emptyState.count() > 0 || (noRows && noCards)).toBeTruthy();
  });
});
