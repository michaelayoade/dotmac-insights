/**
 * CRM Pipeline Page Object
 *
 * Page object for CRM pipeline/opportunities views.
 */

import { type Page, type Locator, expect } from '@playwright/test';
import { BasePage } from './BasePage';

export class CRMPipelinePage extends BasePage {
  // Pipeline-specific selectors
  readonly kanbanBoard: Locator;
  readonly kanbanColumns: Locator;
  readonly opportunityCards: Locator;
  readonly stageFilter: Locator;
  readonly valueFilter: Locator;
  readonly ownerFilter: Locator;
  readonly pipelineMetrics: Locator;
  readonly addOpportunityButton: Locator;

  constructor(page: Page) {
    super(page);

    this.kanbanBoard = page.locator('[data-testid="pipeline-board"], [data-testid="kanban-board"]');
    this.kanbanColumns = page.locator('[data-testid="pipeline-column"], [data-testid="kanban-column"]');
    this.opportunityCards = page.locator('[data-testid="opportunity-card"], [data-testid="kanban-card"]');
    this.stageFilter = page.locator('select').filter({ hasText: /stage/i }).first();
    this.valueFilter = page.locator('select').filter({ hasText: /value/i }).first();
    this.ownerFilter = page.locator('select').filter({ hasText: /owner/i }).first();
    this.pipelineMetrics = page.locator('[data-testid="pipeline-metrics"]');
    this.addOpportunityButton = page.getByRole('button', { name: /add opportunity|new opportunity/i });
  }

  get url(): string {
    return '/crm/pipeline';
  }

  /**
   * Wait for the pipeline board to load
   */
  async waitForPipeline(timeout = 10000): Promise<void> {
    await this.waitForPageLoad(timeout);
    await this.kanbanBoard.waitFor({ state: 'visible', timeout });
  }

  /**
   * Get the number of pipeline stages/columns
   */
  async getStageCount(): Promise<number> {
    return await this.kanbanColumns.count();
  }

  /**
   * Get opportunities count in a specific stage
   */
  async getOpportunitiesInStage(stageName: string): Promise<number> {
    const column = this.page.locator(`[data-testid="pipeline-column"]:has-text("${stageName}")`);
    const cards = column.locator('[data-testid="opportunity-card"]');
    return await cards.count();
  }

  /**
   * Click an opportunity card by name
   */
  async clickOpportunity(name: string): Promise<void> {
    await this.page.getByText(name).first().click();
  }

  /**
   * Drag opportunity from one stage to another
   */
  async dragOpportunityToStage(opportunityName: string, targetStage: string): Promise<void> {
    const card = this.page.locator(`[data-testid="opportunity-card"]:has-text("${opportunityName}")`);
    const targetColumn = this.page.locator(`[data-testid="pipeline-column"]:has-text("${targetStage}")`);

    await card.dragTo(targetColumn);
  }

  /**
   * Filter pipeline by stage
   */
  async filterByStage(stageName: string): Promise<void> {
    await this.stageFilter.selectOption({ label: stageName });
    await this.page.waitForTimeout(500);
  }

  /**
   * Filter by owner
   */
  async filterByOwner(ownerName: string): Promise<void> {
    await this.ownerFilter.selectOption({ label: ownerName });
    await this.page.waitForTimeout(500);
  }

  /**
   * Get total pipeline value from metrics
   */
  async getTotalPipelineValue(): Promise<string> {
    const valueElement = this.pipelineMetrics.locator('[data-testid="total-value"]').or(
      this.page.getByText(/total.*value/i)
    );
    return await valueElement.textContent() || '';
  }

  /**
   * Open create opportunity form
   */
  async openCreateOpportunity(): Promise<void> {
    await this.addOpportunityButton.click();
  }

  /**
   * Create a new opportunity
   */
  async createOpportunity(data: {
    name: string;
    value: string;
    stage?: string;
    probability?: string;
    closeDate?: string;
    contact?: string;
  }): Promise<void> {
    await this.openCreateOpportunity();

    await this.fillField('name', data.name);
    await this.fillField('value', data.value);

    if (data.stage) {
      await this.selectDropdown('stage', data.stage);
    }
    if (data.probability) {
      await this.fillField('probability', data.probability);
    }
    if (data.closeDate) {
      await this.fillField('close date', data.closeDate);
    }
    if (data.contact) {
      await this.selectDropdown('contact', data.contact);
    }

    await this.submitForm();
  }

  /**
   * Verify opportunity appears in stage
   */
  async expectOpportunityInStage(opportunityName: string, stageName: string): Promise<void> {
    const column = this.page.locator(`[data-testid="pipeline-column"]:has-text("${stageName}")`);
    await expect(column.getByText(opportunityName)).toBeVisible();
  }
}

export default CRMPipelinePage;
