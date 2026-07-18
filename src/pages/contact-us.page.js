const { BasePage } = require('./base.page');
const { expect } = require('@playwright/test');

class ContactUsPage extends BasePage {
  constructor(page) {
    super(page);
    this.contactButton = 'text=Contact Us';
    this.contactHeading = 'h1';
    this.nameField = 'input[placeholder="Enter your name"]';
    this.emailField = 'input[placeholder="name@example.com"]';
    this.messageField = 'textarea[placeholder="How can we help?"]';
    this.submitButton = 'button:has-text("Send Message")';
  }

  async open() {
    await this.goto('https://darshanaherkar.github.io/AI-Testing/');
  }

  async navigateToContact() {
    await this.page.click(this.contactButton);
    // Wait for the contact form fields to be visible
    await this.page.locator('input[placeholder="Enter your name"]').waitFor({ state: 'visible', timeout: 10000 });
  }

  async assertContactPageLoaded() {
    await this.page.waitForSelector(this.contactHeading);
  }

  async fillContactForm(name, email, message) {
    const nameInput = this.page.locator('input[placeholder="Enter your name"]');
    const emailInput = this.page.locator('input[placeholder="name@example.com"]');
    const messageInput = this.page.locator('input[placeholder="How can we help?"]');
    
    await nameInput.fill(name);
    await emailInput.fill(email);
    await messageInput.fill(message);
  }

  async submitContactForm() {
    await this.page.click(this.submitButton);
  }

  async verifyContactFormVisible() {
    await this.page.waitForSelector(this.nameField);
  }
}

module.exports = { ContactUsPage };
