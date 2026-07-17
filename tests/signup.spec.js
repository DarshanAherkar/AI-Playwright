const { test, expect } = require('@playwright/test');
const { SignUpPage } = require('../src/pages/signup.page');

test.describe('Sign up page', () => {
  test('should open signup tab and submit account details', async ({ page }) => {
    const signUpPage = new SignUpPage(page);

    await signUpPage.open();
    await signUpPage.signUp('Test User', 'test@example.com', 'password123');

    await expect(page.locator('#signupForm')).toBeVisible();
  });
});
