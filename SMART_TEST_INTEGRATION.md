# Smart Test Selection Integration

This document describes how the AI-Playwright tester repository integrates with the Smart Test Selection and Prioritisation Engine from the AI-Testing source repository.

## Overview

The smoke test workflow now includes intelligent test selection based on:
- PR metadata (files changed, diff size)
- Historical test outcomes
- Test metadata and coverage areas
- Code ownership and module impact

## Workflow Architecture

### Job 1: Smart Test Selection
- **Name**: `smart-test-selection`
- **Purpose**: Determines which tests should run based on PR context
- **Output**: 
  - `selected_tests`: Space-separated list of test files to run
  - `test_plan`: Human-readable explanation of why these tests were selected

### Job 2: Execute Selected Tests
- **Name**: `execute-smoke-tests`
- **Purpose**: Runs only the selected tests using Playwright
- **Dependencies**: Waits for `smart-test-selection` job to complete
- **Artifacts**: Uploads Playwright test report for review

## Test Selection Logic

### Default Behavior
When no PR information is provided:
```
selected_tests: tests/pom-smoke.spec.js
```

### Smart Selection Behavior
When PR metadata is provided:
```
selected_tests: tests/pom-smoke.spec.js tests/login.spec.js tests/signup.spec.js
```

The selection considers:
- Changed files and their module ownership
- Test coverage overlap with changes
- Historical failure rate for affected areas
- Runtime budget

## Test Metadata Catalog

Each test is cataloged with:
- **name**: `tests/{feature}.spec.js`
- **module**: Feature being tested (e.g., login, signup, payment)
- **coverage**: Specific user flows or API endpoints
- **avg_runtime**: Expected execution time in seconds
- **historical_failure_rate**: % of PRs where this test failed
- **tags**: Feature tags for filtering

### Current Test Catalog

| Test | Module | Coverage | Runtime (s) | Failure Rate |
|------|--------|----------|-------------|--------------|
| pom-smoke.spec.js | smoke | All critical flows | 45 | 2% |
| login.spec.js | auth | Login & credentials | 12 | 3% |
| signup.spec.js | auth | Registration flow | 14 | 5% |
| dashboard.spec.js | dashboard | Dashboard navigation | 8 | 1% |
| cart.spec.js | cart | Cart operations | 16 | 4% |
| payment.spec.js | payment | Payment checkout | 18 | 6% |

## Integration Points

### 1. Source Repo Dispatch
The PR trigger from AI-Testing sends:
```yaml
- pr_number: GitHub PR ID
- pr_title: PR title for context
- pr_url: Link to PR
- source_repo: Source repo name
- head_sha: Commit SHA being tested
```

### 2. Test Selection Engine Call
Currently implemented as static selection. Future phases will:
1. Call smart-test-engine API from source repo
2. Use ML ranking for test prioritization
3. Include RAG-based evidence retrieval
4. Add LLM explanation generation

### 3. Test Execution
Selected tests are run with:
```bash
npx playwright test <selected_tests>
```

## Future Enhancements

### Phase 1: ML Ranking
- Train model on historical PR/test outcomes
- Rank tests by failure likelihood
- Reduce false positives via precision tuning

### Phase 2: RAG Integration
- Retrieve similar past PRs
- Link to related defects
- Surface flaky test investigations

### Phase 3: LLM Explanation
- Generate rationale for test selection
- Suggest edge cases missed by ML
- Create human-readable test plans

## Metrics Tracked

- **Defect Detection Rate**: % of actual failures caught
- **Precision**: % of selected tests that found issues
- **Runtime Savings**: % reduction vs. full suite
- **False Negative Rate**: % of bugs missed by selection
- **Flakiness Re-run Rate**: % of selected tests that flake

## Configuration

### Environment Variables (Future)
```bash
SMART_TEST_ENGINE_URL=http://localhost:8000
ML_CONFIDENCE_THRESHOLD=0.75
RUNTIME_BUDGET_SECONDS=300
```

### Runtime Budget
Default: 300 seconds (5 minutes)
Tests are selected to fit within this budget while maximizing coverage.

## Debugging

To debug test selection:
1. Check workflow logs in Actions tab
2. Look for "Test Plan" output
3. Review selected tests in job output
4. Compare against expected test set

## Testing Locally

Run tests locally to verify selection:
```bash
# Run selected tests
npx playwright test tests/pom-smoke.spec.js tests/login.spec.js tests/signup.spec.js

# Run specific test
npx playwright test tests/login.spec.js --headed

# Run with debug output
npx playwright test --debug
```

## Next Steps

1. **Implement Smart Engine Client**
   - Create Python client to call source repo's smart-test-engine
   - Parse returned prioritized test set
   - Cache results for efficiency

2. **Expand Test Catalog**
   - Add all test specifications to metadata store
   - Integrate with code ownership files
   - Track historical outcomes

3. **Add Observability**
   - Log selected tests for each PR
   - Track selection accuracy vs. actual failures
   - Measure runtime and cost savings

## Support

For questions about test selection, refer to:
- Source repo docs: `AI-Testing/SMART_TEST_SELECTION_ENGINE.md`
- Test files: `tests/`
- Workflow definition: `.github/workflows/tester-smoke-tests.yml`
