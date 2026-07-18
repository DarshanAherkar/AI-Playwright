# AI-Playwright: Smart Test Selection Engine

> Intelligent Playwright test automation powered by a **ML + RAG + LLM pipeline** that automatically selects the right tests to run on every Pull Request — saving time, reducing noise, and giving testers AI-driven insights.

---

## The Problem This Solves

In traditional CI/CD pipelines, **every PR runs every test** regardless of what changed. For a growing codebase this means:

- A one-line change in `login.html` triggers all 50+ tests
- Testers wait minutes for unrelated tests to complete
- Flaky tests in unrelated areas cause false failures
- No visibility into *why* a test was selected

**AI-Playwright solves this** by only running tests that are genuinely relevant to what changed in the PR.

---

## How It Helps Testers

| Without Smart Selection | With Smart Selection |
|------------------------|----------------------|
| All tests run on every PR | Only relevant tests run |
| 5-10 min wait per PR | 20-60 sec for targeted runs |
| No explanation for failures | AI reasoning per test selection |
| Manual triage of failures | Prioritised by ML confidence score |
| New pages require config updates | Zero config — auto-discovers new tests |

### Example

PR title: *"Update login button text to Log-IN"*
Changed file: `login.html`

```
Without AI:  runs all 5 tests  (~93 seconds)
With AI:     runs login.spec.js (~12 seconds)
             Mode: ml+rag+llm
             Score: 0.87 | Evidence: RAG=0.82, ML=0.87
```

---

## AI Pipeline Architecture

The smart selection engine runs a three-layer AI pipeline:

```
Changed Files + PR Title
        │
        ▼
┌───────────────────────────────────┐
│  Layer 1: RAG (Retrieval)         │
│  TF-IDF vectorization of test     │
│  file contents (describe names,   │
│  test names, page object imports) │
│  → Cosine similarity scores       │
└──────────────┬────────────────────┘
               │ similarity scores per test
               ▼
┌───────────────────────────────────┐
│  Layer 2: ML (Ranking)            │
│  Weighted feature scoring:        │
│  F1 (40%) RAG similarity          │
│  F2 (35%) Token overlap           │
│  F3 (15%) Content keyword match   │
│  F4 (10%) Path depth signal       │
│  → Ranked candidates via cutoff   │
│    (relative threshold: top 50%)  │
└──────────────┬────────────────────┘
               │ top candidates only
               ▼
┌───────────────────────────────────┐
│  Layer 3: LLM (Reasoning)         │
│  TinyLlama (637 MB, runs locally) │
│  Validates ML candidates          │
│  Adds missed tests if needed      │
│  Explains selection in plain text │
└──────────────┬────────────────────┘
               │
               ▼
    Final test list + per-test scores
    Mode: ml+rag+llm
```

### Layer 1 — RAG (Retrieval-Augmented Generation)

Instead of matching file names by keyword, the RAG layer reads the **actual source code** of each test file and builds a semantic representation using **TF-IDF (Term Frequency–Inverse Document Frequency)**. Common Playwright boilerplate (`test`, `expect`, `page`, `describe`) is filtered out via a stopword list, leaving only domain-meaningful tokens like test suite names, page object imports, and method calls.

Cosine similarity between the changed-file vector and each test vector determines relevance.

### Layer 2 — ML Feature Ranking

Four features are computed per test and combined with learned weights:

| Feature | Weight | Description |
|---------|--------|-------------|
| RAG similarity | 40% | Semantic cosine similarity from TF-IDF |
| Token overlap | 35% | Shared tokens between changed filenames and test name |
| Content keyword match | 15% | Changed file terms found inside test source |
| Path depth signal | 10% | Deeper file paths indicate broader impact |

A **relative threshold** (≥ 50% of the top scorer) ensures only genuinely relevant tests pass — not everything above an arbitrary fixed value.

### Layer 3 — LLM Reasoning (TinyLlama)

TinyLlama (1.1B parameters, 637 MB) runs locally via **Ollama**. It receives only the ML-filtered candidates (not all tests), validates them, and can add missed tests. The strict prompt instructs the model: *"If only login changed, only confirm login test."*

This layer converts raw scores into human-readable reasoning visible in CI logs.

---

## How We Built This

### Phase 1 — Foundation
- Set up Playwright with **Page Object Model** structure
- Created test specs for: Login, Signup, About Us, Contact Us, POM Smoke
- Built a mock web app (`mock-app/`) for local end-to-end testing
- All 10 tests passing in under 25 seconds

### Phase 2 — CI/CD Integration
- Created GitHub Actions workflow (`tester-smoke-tests.yml`) triggered via `workflow_dispatch`
- Connected **AI-Testing** (dev repo) → **AI-Playwright** (tester repo) via cross-repo dispatch
- Workflow fetches changed files from the source PR via GitHub API
- Fixed multiple compatibility issues: Windows PowerShell (`pwsh` vs `powershell`), Unicode encoding, duplicate YAML keys

### Phase 3 — Smart Selection v1 (Hardcoded Fallback)
- Built initial fallback: file-to-test mapping dictionary
- Recognised limitation: adding new pages required manual mapping updates
- Identified need for a fully dynamic approach

### Phase 4 — Smart Engine (ML + RAG + LLM)
- Replaced hardcoded mapping with `discover_tests()` — scans `tests/` at runtime
- Built pure Python HTTP server (`ollama-test-selector.py`) — zero external dependencies
- Integrated **Ollama + TinyLlama** for LLM reasoning
- Implemented **TF-IDF RAG** with domain-specific stopwords
- Implemented **multi-feature ML scoring** with relative threshold
- Fixed over-selection bug: all tests were selected because full test content (boilerplate-heavy) made TF-IDF scores uniform — solved by extracting only meaningful tokens

### Phase 5 — Zero Hardcoding
- Removed all `TEST_MAPPING` and `KEYWORD_MAPPING` dictionaries
- System now works with zero configuration for new pages/tests
- Verified no hardcoded test names remain in logic code

---

## Project Structure

```
AI-Playwright/
├── .github/workflows/
│   └── tester-smoke-tests.yml    # CI/CD workflow with ML+RAG+LLM selection
├── src/pages/
│   ├── base.page.js              # Base page object
│   ├── login.page.js             # Login page interactions
│   ├── signup.page.js            # Signup page interactions
│   ├── about-us.page.js          # About Us page
│   └── contact-us.page.js        # Contact Us page
├── tests/
│   ├── login.spec.js             # Login test suite
│   ├── signup.spec.js            # Signup test suite
│   ├── about-us.spec.js          # About Us test suite
│   ├── contact-us.spec.js        # Contact Us test suite
│   └── pom-smoke.spec.js         # Full POM smoke test
├── mock-app/                     # Local mock web app for testing
├── ollama-test-selector.py       # Smart selection engine (ML+RAG+LLM)
├── test-metadata.json            # Test catalog with runtime and priority
└── playwright.config.js          # Playwright configuration
```

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Test Framework | Playwright + Node.js |
| Page Objects | JavaScript POM pattern |
| CI/CD | GitHub Actions (self-hosted Windows runner) |
| RAG | TF-IDF cosine similarity (pure Python stdlib) |
| ML Ranking | Weighted feature scoring (pure Python) |
| LLM | TinyLlama 1.1B via Ollama |
| Smart Engine | Pure Python `http.server` — zero dependencies |

---

## Setup

### Prerequisites
- Node.js 18+
- Python 3.11+
- [Ollama](https://ollama.ai) installed on the runner machine

### Install

```bash
npm install
npx playwright install
```

### Pull TinyLlama Model (one-time, 637 MB)

```bash
ollama pull tinyllama
```

### Start Smart Selection Engine

```bash
py ollama-test-selector.py 8000
```

### Run Tests Locally

```bash
# All tests
npx playwright test

# Specific test
npx playwright test tests/login.spec.js
```

---

## GitHub Actions Workflow

The workflow is triggered by PRs from the source repo (`AI-Testing`) via `workflow_dispatch`. It:

1. Checks out this repository
2. Sets up Python and installs dependencies
3. Verifies Ollama is running
4. Starts the smart selection server
5. Fetches changed files from the source PR via GitHub API
6. Calls the ML+RAG+LLM engine to select relevant tests
7. Runs only the selected Playwright tests
8. Uploads HTML test report as an artifact (30-day retention)

---

## Adding a New Feature (Zero Config)

```bash
# 1. Create page object
touch src/pages/profile.page.js

# 2. Create test spec
touch tests/profile.spec.js

# 3. Commit and open a PR
# Smart engine auto-discovers profile.spec.js
# No changes needed to ollama-test-selector.py
```
