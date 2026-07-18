const { BasePage } = require('./base.page');

class SignUpPage extends BasePage {
  constructor(page) {
    super(page);
    this.nameInput = 'input[placeholder="Enter your full name"]';
    this.emailInput = 'input[placeholder="name@example.com"]';
    this.passwordInput = 'input[placeholder="Create a password"]';
    this.signUpButton = 'button:has-text("Sign Up")';
    this.signUpLink = 'text=Sign Up';
  }

  async open() {
    await this.goto('https://darshanaherkar.github.io/AI-Testing/');
  }

  async clickSignUpButton() {
    await this.page.click(this.signUpLink);
    // Wait for the signup form fields to be visible
    await this.page.locator('input[placeholder="Enter your full name"]').waitFor({ state: 'visible', timeout: 10000 });
  }

  async signUp(name, email, password) {
    const nameInput = this.page.locator('input[placeholder="Enter your full name"]');
    const emailInput = this.page.locator('input[placeholder="name@example.com"]');
    const passwordInput = this.page.locator('input[placeholder="Create a password"]');
    
    await nameInput.fill(name);
    await emailInput.fill(email);
    await passwordInput.fill(password);
    await this.page.click(this.signUpButton);
  }
}

module.exports = { SignUpPage };
