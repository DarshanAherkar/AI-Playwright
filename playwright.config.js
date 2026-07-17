const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  timeout: 30_000,
  expect: {
    timeout: 5_000,
  },
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    headless: false,
    baseURL: 'http://127.0.0.1:4173',
    trace: 'on-first-retry',
  },
});
