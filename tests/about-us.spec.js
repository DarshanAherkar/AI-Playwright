const { test, expect } = require('@playwright/test');
const { AboutUsPage } = require('../src/pages/about-us.page');
const { LoginPage } = require('../src/pages/login.page');

test.describe('About Us Page', () => {
  let aboutUsPage;
  let loginPage;

  test.beforeEach(async ({ page }) => {
    aboutUsPage = new AboutUsPage(page);
    loginPage = new LoginPage(page);
  });

  test('should navigate to about us page', async ({ page }) => {
    await aboutUsPage.open();
    await aboutUsPage.navigateToAbout();
    await aboutUsPage.assertAboutPageLoaded();
  });

  test('should display company description on about page', async ({ page }) => {
    await aboutUsPage.open();
    await aboutUsPage.navigateToAbout();
    await aboutUsPage.verifyCompanyDescription();
  });

  test('should verify about page heading is visible', async ({ page }) => {
    await aboutUsPage.open();
    await aboutUsPage.navigateToAbout();
    const heading = page.locator('h1');
    await expect(heading).toBeVisible();
  });
});
