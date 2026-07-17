class BasePage {
  constructor(page) {
    this.page = page;
  }

  async goto(path) {
    await this.page.goto(path);
  }

  async waitForPageTitle(title) {
    await this.page.waitForFunction((expectedTitle) => document.title.includes(expectedTitle), title);
  }
}

module.exports = { BasePage };
