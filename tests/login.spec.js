const { test, expect } = require('@playwright/test');
const { LoginPage } = require('../src/pages/login.page');

test.describe('Login page', () => {
  test('should load login form and submit credentials', async ({ page }) => {
    const loginPage = new LoginPage(page);

    await loginPage.open();
    await expect(page.locator('#loginForm')).toBeVisible();
    await loginPage.login('test@example.com', 'password123');

    await expect(page).toHaveURL('https://darshanaherkar.github.io/AI-Testing/');
  });
});
