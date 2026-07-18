const { test, expect } = require('@playwright/test');
const { LoginPage } = require('../src/pages/login.page');
const { SignUpPage } = require('../src/pages/signup.page');
const { ContactUsPage } = require('../src/pages/contact-us.page');
const { AboutUsPage } = require('../src/pages/about-us.page');

test.describe('POM smoke suite', () => {
  test('should open pages and create a basic flow', async ({ page }) => {
    const loginPage = new LoginPage(page);
    const signUpPage = new SignUpPage(page);
    const contactUsPage = new ContactUsPage(page);
    const aboutUsPage = new AboutUsPage(page);

    await signUpPage.open();
    await signUpPage.signUp('Test User', 'test@example.com', 'password123');

    await loginPage.open();
    await loginPage.login('test@example.com', 'password123');

    await aboutUsPage.open();
    await aboutUsPage.navigateToAbout();
    await aboutUsPage.assertAboutPageLoaded();

    await contactUsPage.open();
    await contactUsPage.navigateToContact();
    await contactUsPage.assertContactPageLoaded();

    await expect(page).toHaveURL(/.*(about|contact)/);
  });
});
