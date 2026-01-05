import { Page, Locator } from '@playwright/test';
import { BasePage } from './base.page';

export class MarketingPage extends BasePage {
  readonly tabsNav: Locator;

  constructor(page: Page) {
    super(page);
    this.tabsNav = page.locator('nav[aria-label="Secondary navigation"], nav[aria-label="Secondary Navigation"]');
  }

  async gotoDashboard() {
    await this.goto('/marketing');
  }

  async gotoCampaigns() {
    await this.goto('/marketing/campaigns');
  }

  async gotoJourneys() {
    await this.goto('/marketing/journeys');
  }

  async gotoJourneyTemplates() {
    await this.goto('/marketing/journeys/templates');
  }

  async gotoSocialCalendar() {
    await this.goto('/marketing/social/calendar');
  }

  async gotoSocialPosts() {
    await this.goto('/marketing/social/posts');
  }

  async gotoSocialAccounts() {
    await this.goto('/marketing/social/accounts');
  }

  async gotoEmailCampaigns() {
    await this.goto('/marketing/email/campaigns');
  }

  async gotoEmailTemplates() {
    await this.goto('/marketing/email/templates');
  }

  async gotoEmailAnalytics() {
    await this.goto('/marketing/email/analytics');
  }

  async gotoAudiences() {
    await this.goto('/marketing/audiences');
  }

  async gotoIntegrations() {
    await this.goto('/marketing/integrations');
  }

  async gotoConsent() {
    await this.goto('/marketing/consent');
  }

  async gotoUnsubscribe() {
    await this.goto('/marketing/consent/unsubscribe');
  }
}
