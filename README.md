# AI-Playwright

This repository contains a JavaScript-based Playwright Page Object Model (POM) project for browser automation testing.

## Project Structure

- `src/pages/` - Page Object Model classes for login, signup, dashboard, cart, and payment flows
- `tests/` - Playwright spec files for page-wise execution
- `mock-app/` - Lightweight local mock UI used for end-to-end demo flow validation
- `playwright.config.js` - Playwright configuration

## Features

- JavaScript-only Playwright automation setup
- Page Object Model structure
- Separate test specs for login/signup and page-wise execution
- Local mock app for end-to-end flow validation

## Install

```bash
npm install
```

## Run Tests

```bash
npx playwright test
```

## Run a Specific Page Test

```bash
npx playwright test tests/login.spec.js
```

## Notes

The public GitHub Pages demo site is used for the login/signup auth flow, while the mock app helps verify the full POM route structure locally.
