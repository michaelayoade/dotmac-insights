/**
 * Projects Page Object
 *
 * Page object for projects and Gantt chart views.
 */

import { type Page, type Locator, expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class ProjectsPage extends BasePage {
  // Projects-specific selectors
  readonly ganttChart: Locator;
  readonly ganttTasks: Locator;
  readonly ganttTimeline: Locator;
  readonly projectList: Locator;
  readonly statusFilter: Locator;
  readonly managerFilter: Locator;
  readonly viewToggle: Locator;
  readonly createProjectButton: Locator;
  readonly taskList: Locator;
  readonly addTaskButton: Locator;
  readonly milestoneList: Locator;
  readonly progressBar: Locator;
  readonly zoomControls: Locator;

  constructor(page: Page) {
    super(page);

    this.ganttChart = page.locator('[data-testid="gantt-chart"], .gantt-chart');
    this.ganttTasks = page.locator('[data-testid="gantt-task"], .gantt-task-row');
    this.ganttTimeline = page.locator('[data-testid="gantt-timeline"], .gantt-timeline');
    this.projectList = page.locator('[data-testid="project-list"], table');
    this.statusFilter = page.locator('select').filter({ hasText: /status/i }).first();
    this.managerFilter = page.locator('select').filter({ hasText: /manager/i }).first();
    this.viewToggle = page.locator('[data-testid="view-toggle"]').or(
      page.getByRole('tablist')
    );
    this.createProjectButton = page.getByRole('link', { name: /create project|new project/i });
    this.taskList = page.locator('[data-testid="task-list"], .task-list');
    this.addTaskButton = page.getByRole('button', { name: /add task|new task/i });
    this.milestoneList = page.locator('[data-testid="milestone-list"]');
    this.progressBar = page.locator('[data-testid="progress-bar"], .progress-bar');
    this.zoomControls = page.locator('[data-testid="zoom-controls"]');
  }

  get url(): string {
    return '/projects';
  }

  /**
   * Navigate to a specific project
   */
  async gotoProject(projectId: number): Promise<void> {
    await this.page.goto(`/projects/${projectId}`);
  }

  /**
   * Navigate to Gantt view
   */
  async gotoGantt(): Promise<void> {
    await this.page.goto('/projects/gantt');
  }

  /**
   * Wait for Gantt chart to load
   */
  async waitForGantt(timeout = 10000): Promise<void> {
    await this.ganttChart.waitFor({ state: 'visible', timeout });
  }

  /**
   * Switch to list view
   */
  async switchToListView(): Promise<void> {
    await this.page.getByRole('tab', { name: /list/i }).or(
      this.page.getByRole('button', { name: /list/i })
    ).click();
  }

  /**
   * Switch to Gantt view
   */
  async switchToGanttView(): Promise<void> {
    await this.page.getByRole('tab', { name: /gantt/i }).or(
      this.page.getByRole('button', { name: /gantt/i })
    ).click();
  }

  /**
   * Switch to board view
   */
  async switchToBoardView(): Promise<void> {
    await this.page.getByRole('tab', { name: /board|kanban/i }).or(
      this.page.getByRole('button', { name: /board|kanban/i })
    ).click();
  }

  /**
   * Filter by status
   */
  async filterByStatus(status: string): Promise<void> {
    await this.statusFilter.selectOption({ label: status });
    await this.page.waitForTimeout(500);
  }

  /**
   * Filter by manager
   */
  async filterByManager(manager: string): Promise<void> {
    await this.managerFilter.selectOption({ label: manager });
    await this.page.waitForTimeout(500);
  }

  /**
   * Click a project in the list
   */
  async clickProject(projectName: string): Promise<void> {
    await this.page.getByText(projectName).first().click();
  }

  /**
   * Open create project form
   */
  async openCreateProject(): Promise<void> {
    await this.createProjectButton.click();
  }

  /**
   * Create a new project
   */
  async createProject(data: {
    name: string;
    description?: string;
    startDate?: string;
    endDate?: string;
    manager?: string;
    status?: string;
  }): Promise<void> {
    await this.openCreateProject();

    await this.fillField('name', data.name);

    if (data.description) {
      await this.fillField('description', data.description);
    }
    if (data.startDate) {
      await this.fillField('start date', data.startDate);
    }
    if (data.endDate) {
      await this.fillField('end date', data.endDate);
    }
    if (data.manager) {
      await this.selectDropdown('manager', data.manager);
    }
    if (data.status) {
      await this.selectDropdown('status', data.status);
    }

    await this.submitForm();
  }

  /**
   * Get number of tasks in Gantt chart
   */
  async getGanttTaskCount(): Promise<number> {
    return await this.ganttTasks.count();
  }

  /**
   * Click a task in the Gantt chart
   */
  async clickGanttTask(taskName: string): Promise<void> {
    await this.ganttChart.getByText(taskName).first().click();
  }

  /**
   * Add a task to the current project
   */
  async addTask(data: {
    name: string;
    description?: string;
    assignee?: string;
    startDate?: string;
    dueDate?: string;
    priority?: string;
  }): Promise<void> {
    await this.addTaskButton.click();

    await this.fillField('name', data.name);

    if (data.description) {
      await this.fillField('description', data.description);
    }
    if (data.assignee) {
      await this.selectDropdown('assignee', data.assignee);
    }
    if (data.startDate) {
      await this.fillField('start date', data.startDate);
    }
    if (data.dueDate) {
      await this.fillField('due date', data.dueDate);
    }
    if (data.priority) {
      await this.selectDropdown('priority', data.priority);
    }

    await this.submitForm();
  }

  /**
   * Zoom in on Gantt chart
   */
  async zoomIn(): Promise<void> {
    await this.zoomControls.getByRole('button', { name: /zoom in|\+/i }).click();
  }

  /**
   * Zoom out on Gantt chart
   */
  async zoomOut(): Promise<void> {
    await this.zoomControls.getByRole('button', { name: /zoom out|-/i }).click();
  }

  /**
   * Get project progress percentage
   */
  async getProgress(): Promise<string> {
    return await this.progressBar.getAttribute('data-progress') ||
           await this.progressBar.textContent() || '0';
  }

  /**
   * Verify project status
   */
  async expectStatus(status: string): Promise<void> {
    await expect(this.page.getByText(new RegExp(status, 'i'))).toBeVisible();
  }

  /**
   * Verify task exists in task list
   */
  async expectTaskInList(taskName: string): Promise<void> {
    await expect(this.taskList.getByText(taskName)).toBeVisible();
  }
}

export default ProjectsPage;
