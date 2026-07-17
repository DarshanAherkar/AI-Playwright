const { test, expect } = require('@playwright/test');
const { CartPage } = require('../src/pages/cart.page');

test.describe('Cart page', () => {
  test.skip('cart route is not publicly available on the deployed site', async ({ page }) => {
    const cartPage = new CartPage(page);

    await cartPage.open();
    await cartPage.proceedToCheckout();
    await expect(page.locator('body')).toContainText('Checkout');
  });
});
