class BasePage {
  constructor(page) {
    this.page = page;
  }

  getBaseUrl() {
    return process.env.TARGET_BASE_URL || 'https://darshanaherkar.github.io/AI-Testing/';
  }

  async goto(path) {
    await this.page.goto(path);
  }

  async openHome() {
    await this.goto(this.getBaseUrl());
  }

  async waitForPageTitle(title) {
    await this.page.waitForFunction((expectedTitle) => document.title.includes(expectedTitle), title);
  }
}

module.exports = { BasePage };
