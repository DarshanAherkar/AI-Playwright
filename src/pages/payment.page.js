const { BasePage } = require('./base.page');

class PaymentPage extends BasePage {
  constructor(page) {
    super(page);
    this.cardNumberInput = 'input[name="cardNumber"]';
    this.expiryInput = 'input[name="expiry"]';
    this.cvvInput = 'input[name="cvv"]';
    this.payButton = '#paymentForm button[type="submit"]';
  }

  async pay(cardNumber, expiry, cvv) {
    await this.page.fill(this.cardNumberInput, cardNumber);
    await this.page.fill(this.expiryInput, expiry);
    await this.page.fill(this.cvvInput, cvv);
    await this.page.click(this.payButton);
  }
}

module.exports = { PaymentPage };
