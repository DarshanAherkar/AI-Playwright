const { BasePage } = require('./base.page');

class LoginPage extends BasePage {
  constructor(page) {
    super(page);
    this.emailInput = 'input[placeholder="name@example.com"]';
    this.passwordInput = 'input[placeholder="Enter your password"]';
    this.loginButton = 'button:has-text("Login")';
    this.loginLink = 'text=Login';
  }

  async open() {
    await this.goto('https://darshanaherkar.github.io/AI-Testing/');
  }

  async clickLoginButton() {
    await this.page.click(this.loginLink);
    // Wait for the login form fields to be visible
    await this.page.locator('input[placeholder="name@example.com"]').waitFor({ state: 'visible', timeout: 10000 });
  }

  async login(email, password) {
    const emailInput = this.page.locator('input[placeholder="name@example.com"]');
    const passwordInput = this.page.locator('input[placeholder="Enter your password"]');
    
    await emailInput.fill(email);
    await passwordInput.fill(password);
    await this.page.click(this.loginButton);
  }
}

module.exports = { LoginPage };
