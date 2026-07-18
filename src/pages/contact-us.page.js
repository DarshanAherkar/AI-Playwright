const { BasePage } = require('./base.page');

class ContactUsPage extends BasePage {
  constructor(page) {
    super(page);
    this.contactButton = 'text=Contact';
    this.contactHeading = 'h1';
    this.nameField = 'input[name="name"]';
    this.emailField = 'input[name="email"]';
    this.messageField = 'textarea[name="message"]';
    this.submitButton = 'button[type="submit"]';
  }

  async open() {
    await this.goto('https://darshanaherkar.github.io/AI-Testing/');
  }

  async navigateToContact() {
    await this.page.click(this.contactButton);
  }

  async assertContactPageLoaded() {
    await this.page.waitForSelector(this.contactHeading);
  }

  async fillContactForm(name, email, message) {
    await this.page.fill(this.nameField, name);
    await this.page.fill(this.emailField, email);
    await this.page.fill(this.messageField, message);
  }

  async submitContactForm() {
    await this.page.click(this.submitButton);
  }

  async verifyContactFormVisible() {
    await this.page.waitForSelector(this.nameField);
  }
}

module.exports = { ContactUsPage };
