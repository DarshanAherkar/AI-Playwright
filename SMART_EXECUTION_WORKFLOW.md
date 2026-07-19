# Smart Test Selection Workflow

## Overview

The smart test selection system now uses **hybrid execution** to balance speed with accuracy:

- **Regular PR runs**: Smart selection only (fast) ⚡
- **Scheduled regression runs**: Full suite + cache results 🔄
- **Comparison reports**: Always available, using cached full suite reference 📊

## How It Works

### 1. Regular PR Execution (Default)

When running the comparison report on a normal PR:

```bash
python scripts/generate_comparison_report.py
```

**What happens:**
1. ✅ Runs smart-selected tests (fast, only affected areas)
2. 📦 Loads full suite results from the **latest regression cache**
3. 📊 Generates comparison report against baseline
4. ⏱️ Shows time savings and defect catch rate

**No full suite re-run needed** = Fast feedback ⚡

### 2. Scheduled Regression Runs

When you want to update the baseline, run in regression mode:

**PowerShell (Windows):**
```powershell
.\scripts\run-regression.ps1
```

**Bash (Linux/Mac):**
```bash
bash scripts/run-regression.sh
```

**Or directly:**
```bash
python scripts/generate_comparison_report.py --regression
```

**What happens:**
1. ✅ Runs smart-selected tests
2. ✅ Runs **full test suite** (fresh)
3. 💾 **Caches** the full suite results with timestamp
4. 📊 Generates comparison report
5. ✅ All future PR runs use this cached baseline

## Cache Management

### Cache Location

```
test-results/regression-cache/latest-full-suite.json
```

### Cache Contents

- Full suite test results
- Execution duration
- Exit code
- Timestamp of the regression run

### View Cache Info

```bash
# See when the cache was last updated
cat test-results/regression-cache/latest-full-suite.json | grep timestamp
```

## Workflow Examples

### Example 1: PR Testing (Fast)

```bash
# Set the tests to run via smart selection
export SELECTED_TESTS="tests/login.spec.js tests/signup.spec.js"

# Generate comparison (uses cached full suite)
python scripts/generate_comparison_report.py

# Output: 
# - Smart-selected: 26 sec
# - Full suite (cached from regression): 180 sec  
# - Time saved: 154 sec (85.6% reduction)
# - Defects caught: 100%
```

### Example 2: Nightly Regression (Baseline Update)

```bash
# Run full regression to update baseline
.\scripts\run-regression.ps1

# This runs:
# 1. Full test suite (~3 minutes)
# 2. Saves results to cache
# 3. Shows comparison report

# Output:
# [CACHE] Full suite results saved to test-results/regression-cache/latest-full-suite.json
# [SUCCESS] Regression run complete
# [INFO] Full suite results cached and available for PR comparisons
```

### Example 3: Schedule Integration (GitHub Actions)

```yaml
# .github/workflows/regression.yml
name: Nightly Regression

on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM UTC every day

jobs:
  regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
      - run: npm install
      - run: python scripts/generate_comparison_report.py --regression
      - uses: actions/upload-artifact@v3
        with:
          name: regression-cache
          path: test-results/regression-cache/
```

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| PR execution time | ~180s (full suite every time) | ~26s (smart selection) |
| Regression baseline | Manual tracking | Automated cache |
| Comparison accuracy | ✅ Always current | ✅ Baseline + smart |
| CI/CD efficiency | ❌ Redundant runs | ✅ Optimized |
| False negatives | Risk if smart selects poorly | Caught via regression |

## Troubleshooting

### No cached results found

**Symptom:**
```
[WARNING] No cached full suite results found. Running full suite now...
```

**Solution:**
Run a regression test to create the cache:
```bash
.\scripts\run-regression.ps1
```

### Cache is too old

**Check cache age:**
```bash
cat test-results/regression-cache/latest-full-suite.json | grep timestamp
```

**Update if needed:**
```bash
.\scripts\run-regression.ps1
```

### Comparison report shows unexpected results

**Debug:**
1. Check if you're using the right cache
2. Verify smart selection is working: `echo $SELECTED_TESTS`
3. Check if cache was created recently

## Advanced: Manual Cache Management

### Clear cache (force full suite run next time)

```bash
rm test-results/regression-cache/latest-full-suite.json
```

### View cache contents

```bash
cat test-results/regression-cache/latest-full-suite.json | python -m json.tool
```

### Track cache history

Modify `generate_comparison_report.py` to keep multiple timestamped caches:
```python
cache_file = FULL_SUITE_CACHE_DIR / f"full-suite-{timestamp}.json"
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
# PR workflow - Uses cached baseline
- name: Smart Selection Comparison
  run: |
    export SELECTED_TESTS="$(python scripts/smart-selector.py)"
    python scripts/generate_comparison_report.py
    # Fast feedback in ~30s ⚡

# Scheduled regression - Updates cache
- name: Nightly Regression
  if: github.event_name == 'schedule'
  run: python scripts/generate_comparison_report.py --regression
    # Full validation + cache update ~3 minutes
```

## Summary

- 🚀 **Regular PRs**: 85% faster with smart selection
- 🔄 **Regression**: Scheduled, manual control of baseline
- 📊 **Reporting**: Always shows comparison, no double-runs
- ✅ **Accuracy**: Validated against full regression baseline
