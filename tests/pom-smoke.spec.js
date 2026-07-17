const { test, expect } = require('@playwright/test');
const { LoginPage } = require('../src/pages/login.page');
const { SignUpPage } = require('../src/pages/signup.page');
const { DashboardPage } = require('../src/pages/dashboard.page');
const { CartPage } = require('../src/pages/cart.page');
const { PaymentPage } = require('../src/pages/payment.page');

test.describe('POM smoke suite', () => {
  test.skip('should open pages and create a basic flow', async ({ page }) => {
    const loginPage = new LoginPage(page);
    const signUpPage = new SignUpPage(page);
    const dashboardPage = new DashboardPage(page);
    const cartPage = new CartPage(page);
    const paymentPage = new PaymentPage(page);

    await signUpPage.open();
    await signUpPage.signUp('Test User', 'test@example.com', 'password123');

    await loginPage.open();
    await loginPage.login('test@example.com', 'password123');

    await dashboardPage.open();
    await dashboardPage.assertLoaded();

    await cartPage.open();
    await cartPage.proceedToCheckout();

    await paymentPage.pay('4242424242424242', '12/30', '123');

    await expect(page).toHaveURL(/.*(dashboard|cart|payment)/);
  });
});
