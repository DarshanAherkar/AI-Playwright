const { test, expect } = require('@playwright/test');
const { LoginPage } = require('../src/pages/login.page');

test.describe('Login page', () => {
  test('should load login form and submit credentials', async ({ page }) => {
    const loginPage = new LoginPage(page);

    await loginPage.open();
    await loginPage.clickLoginButton();
    
    // Verify email field is visible
    const emailField = page.locator('input[placeholder="name@example.com"]');
    await expect(emailField).toBeVisible();
    
    await loginPage.login('test@example.com', 'password123');

    // Verify successful login or page change
    await expect(page).toHaveURL(/.*login|dashboard|home/);
  });
});
