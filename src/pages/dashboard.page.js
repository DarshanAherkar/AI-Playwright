const { BasePage } = require('./base.page');

class DashboardPage extends BasePage {
  constructor(page) {
    super(page);
    this.dashboardHeading = 'h1';
  }

  async open() {
    await this.goto('https://darshanaherkar.github.io/AI-Testing/');
  }

  async assertLoaded() {
    await this.page.waitForSelector(this.dashboardHeading);
  }
}

module.exports = { DashboardPage };
