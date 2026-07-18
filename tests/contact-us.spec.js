const { test, expect } = require('@playwright/test');
const { ContactUsPage } = require('../src/pages/contact-us.page');

test.describe('Contact Us Page', () => {
  let contactUsPage;

  test.beforeEach(async ({ page }) => {
    contactUsPage = new ContactUsPage(page);
  });

  test('should navigate to contact us page', async ({ page }) => {
    await contactUsPage.open();
    await contactUsPage.navigateToContact();
    await contactUsPage.assertContactPageLoaded();
  });

  test('should verify contact form is visible', async ({ page }) => {
    await contactUsPage.open();
    await contactUsPage.navigateToContact();
    await contactUsPage.verifyContactFormVisible();
  });

  test('should fill and submit contact form with valid data', async ({ page }) => {
    await contactUsPage.open();
    await contactUsPage.navigateToContact();
    await contactUsPage.fillContactForm('John Doe', 'john@example.com', 'Test message');
    const nameField = page.locator('input[placeholder="Enter your name"]');
    await expect(nameField).toHaveValue('John Doe');
  });

  test('should display contact page heading', async ({ page }) => {
    await contactUsPage.open();
    await contactUsPage.navigateToContact();
    const heading = page.locator('h1');
    await expect(heading).toBeVisible();
  });
});
