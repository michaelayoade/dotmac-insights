import { Page, Locator, expect } from '@playwright/test';
import { BasePage } from './base.page';

/**
 * Page object for Projects module.
 *
 * Handles:
 * - Project list with search and filters
 * - Project detail with tasks
 * - Task management
 * - Gantt chart view
 */
export class ProjectsPage extends BasePage {
  // URL patterns
  readonly listUrl = '/projects';
  readonly dashboardUrl = '/projects/dashboard';
  readonly createUrl = '/projects/new';

  // List page elements
  readonly projectsTable: Locator;
  readonly projectCards: Locator;
  readonly projectSearch: Locator;
  readonly statusFilter: Locator;
  readonly newProjectButton: Locator;

  // Stats elements
  readonly statActive: Locator;
  readonly statCompleted: Locator;
  readonly statOverdue: Locator;

  // Project form elements
  readonly projectForm: Locator;
  readonly projectName: Locator;
  readonly projectDescription: Locator;
  readonly projectStartDate: Locator;
  readonly projectEndDate: Locator;
  readonly projectStatus: Locator;

  // Project detail elements
  readonly projectHeader: Locator;
  readonly projectProgress: Locator;
  readonly tasksSection: Locator;
  readonly milestonesSection: Locator;

  // Task elements
  readonly tasksTable: Locator;
  readonly taskCards: Locator;
  readonly newTaskButton: Locator;
  readonly taskForm: Locator;
  readonly taskName: Locator;
  readonly taskDescription: Locator;
  readonly taskAssignee: Locator;
  readonly taskDueDate: Locator;
  readonly taskPriority: Locator;
  readonly taskStatus: Locator;

  // Gantt elements
  readonly ganttChart: Locator;
  readonly ganttZoomIn: Locator;
  readonly ganttZoomOut: Locator;

  constructor(page: Page) {
    super(page);

    // List page
    this.projectsTable = page.locator('#projects-table-container table, [data-testid="projects-table"] table');
    this.projectCards = page.locator('[data-testid="project-card"]');
    this.projectSearch = page.locator('[data-testid="projects-search"]');
    this.statusFilter = page.locator('[data-testid="status-filter-button"]');
    this.newProjectButton = page.locator('[data-testid="new-project-button"]');

    // Stats
    this.statActive = page.locator('[data-testid="stat-active"], .stat-active');
    this.statCompleted = page.locator('[data-testid="stat-completed"], .stat-completed');
    this.statOverdue = page.locator('[data-testid="stat-overdue"], .stat-overdue');

    // Form
    this.projectForm = page.locator('form[action*="/projects"], [data-testid="project-form"]');
    this.projectName = page.locator('input[name="project_name"]');
    this.projectDescription = page.locator('textarea[name="notes"]');
    this.projectStartDate = page.locator('input[name="expected_start_date"]');
    this.projectEndDate = page.locator('input[name="expected_end_date"]');
    this.projectStatus = page.locator('select[name="status"]');

    // Detail
    this.projectHeader = page.locator('.project-header, [data-testid="project-header"], h1');
    this.projectProgress = page.locator('.project-progress, [data-testid="progress"], .progress-bar');
    this.tasksSection = page.locator('#tasks, .tasks-section, [data-testid="tasks"]');
    this.milestonesSection = page.locator('#milestones, .milestones-section, [data-testid="milestones"]');

    // Tasks
    this.tasksTable = page.locator('#tasks-table table, [data-testid="tasks-table"]');
    this.taskCards = page.locator('.task-card, [data-testid="task-card"]');
    this.newTaskButton = page.locator('[data-testid="new-task"], button:has-text("New Task"), a[href*="/tasks/new"]');
    this.taskForm = page.locator('form[action*="/tasks"], [data-testid="task-form"]');
    this.taskName = page.locator('input[name="name"], input[name="title"]');
    this.taskDescription = page.locator('textarea[name="description"]');
    this.taskAssignee = page.locator('select[name="assignee"], select[name="assigned_to"]');
    this.taskDueDate = page.locator('input[name="due_date"]');
    this.taskPriority = page.locator('select[name="priority"]');
    this.taskStatus = page.locator('select[name="status"]');

    // Gantt
    this.ganttChart = page.locator('.gantt-chart, [data-testid="gantt"], #gantt');
    this.ganttZoomIn = page.locator('button[onclick="zoomIn()"]');
    this.ganttZoomOut = page.locator('button[onclick="zoomOut()"]');
  }

  // =========================================================================
  // NAVIGATION
  // =========================================================================

  async gotoList(): Promise<void> {
    await this.goto(this.listUrl);
  }

  async gotoDashboard(): Promise<void> {
    await this.goto(this.dashboardUrl);
  }

  async gotoCreate(): Promise<void> {
    await this.goto(this.createUrl);
  }

  async gotoProject(id: number): Promise<void> {
    await this.goto(`${this.listUrl}/${id}`);
  }

  async gotoGantt(): Promise<void> {
    await this.goto(`${this.listUrl}/gantt`);
  }

  // =========================================================================
  // PROJECTS LIST
  // =========================================================================

  async searchProjects(query: string): Promise<void> {
    await this.projectSearch.fill(query);
    await this.page.waitForTimeout(400);
    await this.waitForHtmxComplete();
  }

  async filterByStatus(status: string): Promise<void> {
    await this.statusFilter.click();
    const option = this.page.locator(`[data-testid="status-option-${status.replace(/\\s+/g, '-')}"]`);
    await option.click();
    await this.waitForHtmxComplete();
  }

  async getProjectCount(): Promise<number> {
    const tableCount = await this.getTableRowCount(this.projectsTable);
    if (tableCount > 0) return tableCount;
    return await this.projectCards.count();
  }

  async hasProjects(): Promise<boolean> {
    const tableRows = await this.projectsTable.locator('tbody tr').count();
    const cards = await this.projectCards.count();
    return tableRows > 0 || cards > 0;
  }

  async clickProject(name: string): Promise<void> {
    const row = this.projectsTable.locator(`tbody tr:has-text("${name}")`);
    if (await row.count() > 0) {
      const link = row.locator('a').first();
      await this.htmxClick(link);
    } else {
      const card = this.projectCards.filter({ hasText: name });
      await this.htmxClick(card);
    }
  }

  // =========================================================================
  // TASKS
  // =========================================================================

  async getTaskCount(): Promise<number> {
    const tableCount = await this.getTableRowCount(this.tasksTable);
    if (tableCount > 0) return tableCount;
    return await this.taskCards.count();
  }

  async hasTasks(): Promise<boolean> {
    const tableRows = await this.tasksTable.locator('tbody tr').count();
    const cards = await this.taskCards.count();
    return tableRows > 0 || cards > 0;
  }

  async createTask(data: {
    name: string;
    description?: string;
    assignee?: string;
    dueDate?: string;
    priority?: string;
  }): Promise<void> {
    await this.newTaskButton.click();
    await this.waitForHtmxComplete();

    await this.taskName.fill(data.name);
    if (data.description) {
      await this.taskDescription.fill(data.description);
    }
    if (data.assignee) {
      await this.taskAssignee.selectOption(data.assignee);
    }
    if (data.dueDate) {
      await this.taskDueDate.fill(data.dueDate);
    }
    if (data.priority) {
      await this.taskPriority.selectOption(data.priority);
    }

    await this.htmxSubmitForm(this.taskForm);
  }

  async updateTaskStatus(taskName: string, newStatus: string): Promise<void> {
    const task = this.tasksTable.locator(`tbody tr:has-text("${taskName}")`);
    const statusSelect = task.locator('select[name="status"]');
    if (await statusSelect.count() > 0) {
      await statusSelect.selectOption(newStatus);
      await this.waitForHtmxComplete();
    }
  }

  // =========================================================================
  // GANTT
  // =========================================================================

  async expectGanttVisible(): Promise<void> {
    await expect(this.ganttChart).toBeVisible();
  }

  async zoomIn(): Promise<void> {
    await this.ganttZoomIn.click();
  }

  async zoomOut(): Promise<void> {
    await this.ganttZoomOut.click();
  }

  // =========================================================================
  // ASSERTIONS
  // =========================================================================

  async expectProjectInList(name: string): Promise<void> {
    const row = this.projectsTable.locator(`tbody tr:has-text("${name}")`);
    const card = this.projectCards.filter({ hasText: name });
    const hasRow = await row.count() > 0;
    const hasCard = await card.count() > 0;
    expect(hasRow || hasCard).toBeTruthy();
  }

  async expectTaskInList(name: string): Promise<void> {
    const row = this.tasksTable.locator(`tbody tr:has-text("${name}")`);
    const card = this.taskCards.filter({ hasText: name });
    const hasRow = await row.count() > 0;
    const hasCard = await card.count() > 0;
    expect(hasRow || hasCard).toBeTruthy();
  }

  async expectEmptyState(): Promise<void> {
    const emptyState = this.page.locator('[data-testid="projects-empty-state"]');
    await expect(emptyState).toBeVisible();
  }
}
