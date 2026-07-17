const { BasePage } = require('./base.page');

class SignUpPage extends BasePage {
  constructor(page) {
    super(page);
    this.tabButton = 'button[data-form="signup"]';
    this.nameInput = '#signupForm input[type="text"]';
    this.emailInput = '#signupForm input[type="email"]';
    this.passwordInput = '#signupForm input[type="password"]';
    this.signUpButton = '#signupForm button[type="submit"]';
  }

  async open() {
    await this.goto('https://darshanaherkar.github.io/AI-Testing/');
  }

  async signUp(name, email, password) {
    await this.page.click(this.tabButton);
    await this.page.fill(this.nameInput, name);
    await this.page.fill(this.emailInput, email);
    await this.page.fill(this.passwordInput, password);
    await this.page.click(this.signUpButton);
  }
}

module.exports = { SignUpPage };
