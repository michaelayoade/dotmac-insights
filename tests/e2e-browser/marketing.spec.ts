import { test, expect } from './fixtures/htmx.fixture';
import { MarketingPage } from './pages/marketing.page';

/**
 * Marketing module UI coverage.
 */

test.describe('Marketing Module @smoke', () => {
  let marketingPage: MarketingPage;

  test.beforeEach(async ({ page }) => {
    marketingPage = new MarketingPage(page);
  });

  test('dashboard loads', async () => {
    await marketingPage.gotoDashboard();
    await expect(marketingPage.page.getByTestId('page-title')).toHaveText(/Marketing Dashboard/i);
    await expect(marketingPage.tabsNav).toBeVisible();
  });

  test('campaigns page loads', async () => {
    await marketingPage.gotoCampaigns();
    await expect(marketingPage.page.getByTestId('page-title')).toHaveText(/Campaigns/i);
  });

  test('journeys pages load', async () => {
    await marketingPage.gotoJourneys();
    await expect(marketingPage.page.getByTestId('page-title')).toHaveText(/Customer Journeys/i);

    await marketingPage.gotoJourneyTemplates();
    await expect(marketingPage.page.getByTestId('page-title')).toHaveText(/Journey Templates/i);
  });

  test('social pages load', async () => {
    await marketingPage.gotoSocialCalendar();
    await expect(marketingPage.page.getByTestId('page-title')).toHaveText(/Social Calendar/i);

    await marketingPage.gotoSocialPosts();
    await expect(marketingPage.page.getByTestId('page-title')).toHaveText(/Social Posts/i);

    await marketingPage.gotoSocialAccounts();
    await expect(marketingPage.page.getByTestId('page-title')).toHaveText(/Social Accounts/i);
  });

  test('email pages load', async () => {
    await marketingPage.gotoEmailCampaigns();
    await expect(marketingPage.page.getByTestId('page-title')).toHaveText(/Email Campaigns/i);

    await marketingPage.gotoEmailTemplates();
    await expect(marketingPage.page.getByTestId('page-title')).toHaveText(/Email Templates/i);

    await marketingPage.gotoEmailAnalytics();
    await expect(marketingPage.page.getByTestId('page-title')).toHaveText(/Email Analytics/i);
  });

  test('audiences, integrations, consent pages load', async () => {
    await marketingPage.gotoAudiences();
    await expect(marketingPage.page.getByTestId('page-title')).toHaveText(/Audiences/i);

    await marketingPage.gotoIntegrations();
    await expect(marketingPage.page.getByTestId('page-title')).toHaveText(/Integrations/i);

    await marketingPage.gotoConsent();
    await expect(marketingPage.page.getByTestId('page-title')).toHaveText(/Consent/i);
  });

  test('unsubscribe page loads', async () => {
    await marketingPage.gotoUnsubscribe();
    await expect(marketingPage.page.getByTestId('page-title')).toHaveText(/Unsubscribe/i);
  });
});
