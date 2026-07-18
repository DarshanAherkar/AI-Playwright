const { BasePage } = require('./base.page');
const { expect } = require('@playwright/test');

class AboutUsPage extends BasePage {
  constructor(page) {
    super(page);
    this.aboutButton = 'text=About Us';
    this.aboutHeading = 'h1';
    this.companyDescription = 'text=Who we are';
  }

  async open() {
    await this.goto('https://darshanaherkar.github.io/AI-Testing/');
  }

  async navigateToAbout() {
    await this.page.click(this.aboutButton);
  }

  async assertAboutPageLoaded() {
    await this.page.waitForSelector(this.aboutHeading);
  }

  async verifyCompanyDescription() {
    const description = await this.page.locator(this.companyDescription);
    await expect(description).toBeVisible();
  }
}

module.exports = { AboutUsPage };
