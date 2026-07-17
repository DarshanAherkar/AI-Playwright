const { BasePage } = require('./base.page');

class CartPage extends BasePage {
  constructor(page) {
    super(page);
    this.cartButton = '#checkout';
  }

  async open() {
    await this.goto('https://darshanaherkar.github.io/AI-Testing/');
  }

  async proceedToCheckout() {
    await this.page.click(this.cartButton);
  }
}

module.exports = { CartPage };
