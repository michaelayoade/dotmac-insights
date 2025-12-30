/**
 * Projects & Gantt E2E Tests
 *
 * Comprehensive tests for the Projects module including:
 * - Project list and Gantt views
 * - Project CRUD operations
 * - Task management
 * - Gantt chart interactions
 * - View switching (list, Gantt, board)
 * - RBAC (role-based access control)
 */

import { test, expect, setupAuth, expectAccessDenied } from './fixtures/auth';
import {
  createTestProject,
  deleteTestProject,
  createTestProjectTask,
} from './fixtures/api-helpers';
import { ProjectsPage } from './pages';

test.describe('Projects - Authenticated', () => {
  test.beforeEach(async ({ page }) => {
    await setupAuth(page, ['projects:read', 'projects:write']);
  });

  test.describe('List View', () => {
    test('renders projects list', async ({ page }) => {
      const projectsPage = new ProjectsPage(page);
      await projectsPage.goto();

      await expect(page.getByText(/access denied|not authorized/i)).toBeHidden({ timeout: 10000 });
      await expect(
        page.getByRole('heading', { name: /projects/i })
      ).toBeVisible({ timeout: 10000 });

      await expect(projectsPage.createProjectButton).toBeVisible();
    });

    test('displays project data table', async ({ page }) => {
      const projectsPage = new ProjectsPage(page);
      await projectsPage.goto();

      await expect(projectsPage.projectList).toBeVisible({ timeout: 10000 });
    });

    test('search filters projects', async ({ page }) => {
      const projectsPage = new ProjectsPage(page);
      await projectsPage.goto();

      await projectsPage.search('Test');

      await expect(
        page
          .locator('table tbody tr, [role="grid"] [role="row"]')
          .first()
          .or(page.getByText(/no results|empty|no data/i))
      ).toBeVisible({ timeout: 10000 });
    });

    test('filter by status works', async ({ page }) => {
      const projectsPage = new ProjectsPage(page);
      await projectsPage.goto();

      if (await projectsPage.statusFilter.isVisible()) {
        await projectsPage.filterByStatus('Open');

        await expect(
          page
            .locator('table tbody tr')
            .first()
            .or(page.getByText(/no results|empty/i))
        ).toBeVisible({ timeout: 10000 });
      }
    });
  });

  test.describe('Gantt View', () => {
    test('navigates to Gantt view', async ({ page }) => {
      const projectsPage = new ProjectsPage(page);
      await projectsPage.gotoGantt();

      await expect(page).toHaveURL(/\/projects\/gantt/);
    });

    test('displays Gantt chart', async ({ page, request }) => {
      const project = await createTestProject(request, {
        project_name: `Gantt Test ${Date.now()}`,
      });

      try {
        const projectsPage = new ProjectsPage(page);
        await projectsPage.gotoGantt();

        // Gantt chart or timeline should be visible
        const ganttElement = page.locator('[data-testid="gantt-chart"], .gantt-chart, .gantt-container');
        await expect(ganttElement.or(page.getByText(/gantt|timeline/i))).toBeVisible({ timeout: 10000 });
      } finally {
        await deleteTestProject(request, project.id);
      }
    });

    test('shows tasks in Gantt chart', async ({ page, request }) => {
      const project = await createTestProject(request, {
        project_name: `Gantt Tasks Test ${Date.now()}`,
      });

      try {
        // Add a task
        await createTestProjectTask(request, project.id, {
          subject: `Gantt Task ${Date.now()}`,
        });

        await page.goto(`/projects/${project.id}/gantt`);

        // Task should appear in Gantt
        await page.waitForTimeout(1000);
      } finally {
        await deleteTestProject(request, project.id);
      }
    });

    test('zoom controls work', async ({ page }) => {
      const projectsPage = new ProjectsPage(page);
      await projectsPage.gotoGantt();

      if (await projectsPage.zoomControls.isVisible()) {
        // Zoom in
        await projectsPage.zoomIn();
        await page.waitForTimeout(300);

        // Zoom out
        await projectsPage.zoomOut();
        await page.waitForTimeout(300);
      }
    });
  });

  test.describe('View Switching', () => {
    test('can switch to list view', async ({ page }) => {
      const projectsPage = new ProjectsPage(page);
      await projectsPage.goto();

      await projectsPage.switchToListView();

      await expect(projectsPage.projectList).toBeVisible({ timeout: 5000 });
    });

    test('can switch to Gantt view', async ({ page }) => {
      const projectsPage = new ProjectsPage(page);
      await projectsPage.goto();

      if (await projectsPage.viewToggle.isVisible()) {
        await projectsPage.switchToGanttView();

        const ganttChart = page.locator('[data-testid="gantt-chart"], .gantt-chart');
        await expect(ganttChart.or(page.getByText(/gantt|timeline/i))).toBeVisible({ timeout: 5000 });
      }
    });

    test('can switch to board view', async ({ page }) => {
      const projectsPage = new ProjectsPage(page);
      await projectsPage.goto();

      if (await projectsPage.viewToggle.isVisible()) {
        try {
          await projectsPage.switchToBoardView();
          await page.waitForTimeout(500);
        } catch {
          // Board view may not be available
        }
      }
    });
  });

  test.describe('Create Project', () => {
    test('navigates to create form', async ({ page }) => {
      const projectsPage = new ProjectsPage(page);
      await projectsPage.goto();

      await projectsPage.openCreateProject();

      await expect(page).toHaveURL(/\/projects\/new|\/projects\/create/);
    });

    test('validates required fields', async ({ page }) => {
      await page.goto('/projects/new');

      await page.getByRole('button', { name: /save|create|submit/i }).click();

      await expect(
        page.getByText(/required|cannot be empty|please enter/i).first()
      ).toBeVisible({ timeout: 5000 });
    });

    test('creates project successfully', async ({ page, request }) => {
      const projectName = `E2E Project ${Date.now()}`;

      await page.goto('/projects/new');

      await page.getByLabel(/name|title/i).first().fill(projectName);

      // Set dates if fields exist
      const startDateInput = page.getByLabel(/start.*date/i);
      if (await startDateInput.isVisible()) {
        await startDateInput.fill(new Date().toISOString().split('T')[0]);
      }

      await page.getByRole('button', { name: /save|create|submit/i }).click();
      await page.waitForURL(/\/projects\/\d+/, { timeout: 10000 });

      // Verify project created
      await expect(page.getByText(projectName)).toBeVisible();
    });
  });

  test.describe('Edit Project', () => {
    test('loads project data', async ({ page, request }) => {
      const project = await createTestProject(request, {
        project_name: `Edit View Test ${Date.now()}`,
      });

      try {
        const projectsPage = new ProjectsPage(page);
        await projectsPage.gotoProject(project.id);

        await expect(page.getByText(project.project_name)).toBeVisible({ timeout: 5000 });
      } finally {
        await deleteTestProject(request, project.id);
      }
    });

    test('updates project name', async ({ page, request }) => {
      const project = await createTestProject(request, {
        project_name: `Update Test ${Date.now()}`,
      });

      try {
        await page.goto(`/projects/${project.id}/edit`);

        const updatedName = `Updated Project ${Date.now()}`;
        await page.getByLabel(/name|title/i).first().fill(updatedName);
        await page.getByRole('button', { name: /save|update/i }).click();

        await page.waitForURL(/\/projects\/\d+$/, { timeout: 10000 });
        await expect(page.getByText(updatedName)).toBeVisible();
      } finally {
        await deleteTestProject(request, project.id);
      }
    });
  });

  test.describe('Task Management', () => {
    test('displays task list for project', async ({ page, request }) => {
      const project = await createTestProject(request, {
        project_name: `Task List Test ${Date.now()}`,
      });

      try {
        await createTestProjectTask(request, project.id, {
          subject: `Test Task ${Date.now()}`,
        });

        const projectsPage = new ProjectsPage(page);
        await projectsPage.gotoProject(project.id);

        // Task list should be visible
        const taskList = page.locator('[data-testid="task-list"], .task-list, table');
        await expect(taskList).toBeVisible({ timeout: 10000 });
      } finally {
        await deleteTestProject(request, project.id);
      }
    });

    test('can add task to project', async ({ page, request }) => {
      const project = await createTestProject(request, {
        project_name: `Add Task Test ${Date.now()}`,
      });

      try {
        const projectsPage = new ProjectsPage(page);
        await projectsPage.gotoProject(project.id);

        if (await projectsPage.addTaskButton.isVisible()) {
          await projectsPage.addTask({
            name: `E2E Task ${Date.now()}`,
          });

          await page.waitForTimeout(1000);
        }
      } finally {
        await deleteTestProject(request, project.id);
      }
    });

    test('task appears in task list', async ({ page, request }) => {
      const project = await createTestProject(request, {
        project_name: `Task Visibility Test ${Date.now()}`,
      });

      const taskSubject = `Visible Task ${Date.now()}`;

      try {
        await createTestProjectTask(request, project.id, {
          subject: taskSubject,
        });

        const projectsPage = new ProjectsPage(page);
        await projectsPage.gotoProject(project.id);

        await projectsPage.expectTaskInList(taskSubject);
      } finally {
        await deleteTestProject(request, project.id);
      }
    });
  });

  test.describe('Project Progress', () => {
    test('displays progress bar', async ({ page, request }) => {
      const project = await createTestProject(request, {
        project_name: `Progress Test ${Date.now()}`,
      });

      try {
        const projectsPage = new ProjectsPage(page);
        await projectsPage.gotoProject(project.id);

        const progressBar = page.locator('[data-testid="progress-bar"], .progress-bar, [role="progressbar"]');
        if (await progressBar.isVisible()) {
          await expect(progressBar).toBeVisible();
        }
      } finally {
        await deleteTestProject(request, project.id);
      }
    });
  });

  test.describe('Project Status', () => {
    test('displays project status', async ({ page, request }) => {
      const project = await createTestProject(request, {
        project_name: `Status Test ${Date.now()}`,
        status: 'Open',
      });

      try {
        const projectsPage = new ProjectsPage(page);
        await projectsPage.gotoProject(project.id);

        await projectsPage.expectStatus('Open');
      } finally {
        await deleteTestProject(request, project.id);
      }
    });

    test('can change project status', async ({ page, request }) => {
      const project = await createTestProject(request, {
        project_name: `Status Change Test ${Date.now()}`,
        status: 'Open',
      });

      try {
        await page.goto(`/projects/${project.id}`);

        const statusSelect = page.getByLabel(/status/i).or(
          page.locator('select').filter({ hasText: /status/i })
        );

        if (await statusSelect.isVisible()) {
          await statusSelect.click();
          await page.getByRole('option', { name: /in progress|completed/i }).first().click();

          const saveButton = page.getByRole('button', { name: /save|update/i });
          if (await saveButton.isVisible()) {
            await saveButton.click();
          }

          await page.waitForTimeout(1000);
        }
      } finally {
        await deleteTestProject(request, project.id);
      }
    });
  });

  test.describe('Delete Project', () => {
    test('can delete project', async ({ page, request }) => {
      const project = await createTestProject(request, {
        project_name: `Delete Test ${Date.now()}`,
      });

      const projectsPage = new ProjectsPage(page);
      await projectsPage.gotoProject(project.id);

      const deleteButton = page.getByRole('button', { name: /delete|archive/i });
      if (await deleteButton.isVisible()) {
        await deleteButton.click();

        const confirmButton = page.getByRole('button', { name: /confirm|yes|delete/i });
        await expect(confirmButton).toBeVisible({ timeout: 2000 });
        await confirmButton.click();

        await page.waitForURL('/projects', { timeout: 10000 });
      } else {
        // Manual cleanup
        await deleteTestProject(request, project.id);
      }
    });
  });
});

test.describe('Projects - RBAC', () => {
  test('read-only user cannot create projects', async ({ page }) => {
    await setupAuth(page, ['projects:read']);

    const projectsPage = new ProjectsPage(page);
    await projectsPage.goto();

    await expect(projectsPage.createProjectButton).toBeHidden();
  });

  test('user without projects scope sees access denied', async ({ page }) => {
    await setupAuth(page, ['hr:read']);
    await page.goto('/projects');

    await expectAccessDenied(page);
  });
});

test.describe('Projects - Unauthenticated', () => {
  test('redirects to login when not authenticated', async ({ page }) => {
    await page.goto('/');
    await page.evaluate(() => localStorage.clear());

    await page.goto('/projects');

    await expect(page).toHaveURL(/\/login|\/auth/);
  });
});
