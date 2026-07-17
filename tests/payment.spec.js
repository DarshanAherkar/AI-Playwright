const { test, expect } = require('@playwright/test');
const { PaymentPage } = require('../src/pages/payment.page');

test.describe('Payment page', () => {
  test.skip('payment route is not publicly available on the deployed site', async ({ page }) => {
    const paymentPage = new PaymentPage(page);

    await paymentPage.pay('4242424242424242', '12/30', '123');
    await expect(page.locator('body')).toContainText('Pay Now');
  });
});
