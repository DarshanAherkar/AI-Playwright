const { test, expect } = require('@playwright/test');
const { DashboardPage } = require('../src/pages/dashboard.page');

test.describe('Dashboard page', () => {
  test.skip('dashboard route is not publicly available on the deployed site', async ({ page }) => {
    const dashboardPage = new DashboardPage(page);

    await dashboardPage.open();
    await dashboardPage.assertLoaded();
    await expect(page.locator('h1')).toBeVisible();
  });
});
