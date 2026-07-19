# Smart Test Selection - Execution Modes

## 🎯 Quick Summary

| Mode | Full Suite | Time | When |
|------|-----------|------|------|
| **PR Tests** | ❌ NO | 30 sec | Every PR (automatic) |
| **Init Cache** | ✅ YES | 3-5 min | First-time setup (manual) |
| **Nightly** | ✅ YES | 3-5 min | Daily at 2 AM UTC (auto) |

**Critical:** PR runs ONLY execute smart-selected tests. **Never full suite.**

---

## 📋 Three Execution Modes

### Mode 1: Smart PR Tests (✅ This is what you want most of the time)

**When:** Every PR via workflow_dispatch  
**Full Suite:** ❌ NO  
**Time:** 30 seconds ⚡  
**What runs:** Only smart-selected tests  
**Cache:** Uses existing cache

```bash
# Automatic - no manual action needed
npx playwright test tests/login.spec.js tests/signup.spec.js

# Time taken: ~30 seconds
# Full suite comparison: Uses cached baseline (if available)
```

---

### Mode 2: Initialize Cache (⚠️ One-time setup)

**When:** First-time setup before any PR tests  
**Full Suite:** ✅ YES  
**Time:** 3-5 minutes  
**What runs:** Full test suite to create baseline  
**Result:** Enables all future PR runs to be fast

#### How to initialize:

**PowerShell (Windows):**
```powershell
.\scripts\init-cache.ps1
```

**Bash (Linux/Mac):**
```bash
bash scripts/init-cache.sh
```

**Or directly:**
```bash
python scripts/generate_comparison_report.py --regression
```

#### Output:
```
==========================================
REGRESSION MODE: Full Suite + Cache Update
==========================================

[ACTION] Running smart-selected subset...
[ACTION] Regression mode: Running full suite and caching results...
[CACHE] Full suite results saved to test-results/regression-cache/latest-full-suite.json
[SUCCESS] Cache initialized successfully
```

After this runs once, all future PR tests will be fast!

---

### Mode 3: Nightly Regression (🔄 Automatic)

**When:** Daily schedule (2 AM UTC)  
**Full Suite:** ✅ YES  
**Time:** 3-5 minutes  
**What runs:** Full suite to refresh baseline  
**Trigger:** GitHub Actions schedule (automatic)

#### What happens:
1. Runs full test suite
2. Updates cache with new results
3. All next day's PR tests use this fresh baseline

#### Manual trigger (if needed):
```bash
python scripts/generate_comparison_report.py --regression
.\scripts\run-regression.ps1    # PowerShell
bash scripts/run-regression.sh  # Bash
```

---

## 🚀 Getting Started

### Step 1: One-time Cache Initialization

```powershell
# Windows
.\scripts\init-cache.ps1
```

Wait for it to complete (~3-5 minutes). This creates your baseline.

### Step 2: Use Smart Selection (All Future Runs)

That's it! PR tests now automatically:
- ✅ Run only smart-selected tests (30 seconds)
- ✅ Use cached baseline for comparison
- ✅ Show efficiency metrics

Cache is refreshed nightly automatically.

---

## 📊 How It Works

### Execution Flow

```
┌─ First Time (Cache Doesn't Exist)
│  ├─ Manual: Run init-cache.ps1
│  ├─ Full suite: 180 seconds
│  ├─ Create: test-results/regression-cache/latest-full-suite.json
│  └─ Status: ✅ Ready for fast PR tests
│
├─ Subsequent PR Runs (Cache Exists)
│  ├─ Auto: GitHub Actions restores cache
│  ├─ Smart tests: 30 seconds
│  ├─ Compare: Against cached baseline
│  └─ Status: ✅ Fast & Accurate
│
└─ Nightly Regression (2 AM UTC)
   ├─ Schedule: GitHub Actions trigger
   ├─ Full suite: 180 seconds
   ├─ Update: test-results/regression-cache/latest-full-suite.json
   └─ Status: ✅ Baseline refreshed
```

### Script Behavior

**Standard Mode (PR tests):**
```python
if not regression_mode and not cache_exists:
    # DON'T run full suite
    # Just show smart results
    # Message: "Cache not available, use init-cache.ps1"
```

**Regression Mode (init/nightly):**
```python
if regression_mode:
    # RUN full suite
    # SAVE cache
    # Show comparison
```

---

## 📁 Cache Structure

### Location
```
test-results/regression-cache/latest-full-suite.json
```

### Contents
```json
{
  "timestamp": "2025-07-19T10:30:00",
  "duration_seconds": 175.5,
  "exit_code": 0,
  "report": { /* full test results */ },
  "stdout": "...",
  "stderr": ""
}
```

### Verify Cache
```bash
# Check if cache exists
ls test-results/regression-cache/

# View cache timestamp
cat test-results/regression-cache/latest-full-suite.json | grep timestamp
```

---

## 💡 Usage Examples

### Example 1: Fresh Setup

```bash
# Day 1: Initialize cache (one-time)
.\scripts\init-cache.ps1
# Time: ~3-5 minutes
# Result: test-results/regression-cache/latest-full-suite.json created ✅

# Day 1+: All PR tests are now fast
export SELECTED_TESTS="tests/login.spec.js"
python scripts/generate_comparison_report.py
# Time: ~30 seconds
# Result: Smart tests + cached comparison ⚡
```

### Example 2: No Cache Scenario

```bash
# If cache doesn't exist yet:
python scripts/generate_comparison_report.py

# Output:
# STANDARD MODE: Smart Tests Only (No Full Suite)
# [ACTION] Running smart-selected subset... ✅
# [ACTION] Standard mode: NOT running full suite ✅
# [WARNING] No cached baseline available
# [INFO] To initialize cache, run: .\scripts\init-cache.ps1

# Time: ~30 seconds (NO full suite run)
```

### Example 3: Nightly Refresh

```bash
# Automatic at 2 AM UTC (GitHub Actions)
# Or manual:
.\scripts\run-regression.ps1

# Output:
# REGRESSION MODE: Full Suite + Cache Update
# [ACTION] Running smart-selected subset...
# [ACTION] Regression mode: Running full suite... ✅
# [CACHE] Full suite results saved
# [SUCCESS] Cache initialized successfully

# Time: ~3-5 minutes
# Result: Cache updated for next day's PRs
```

---

## ⚙️ Configuration

### Nightly Schedule

Set in `.github/workflows/tester-smoke-tests.yml`:
```yaml
schedule:
  - cron: '0 2 * * *'  # 2 AM UTC daily
```

To change: Edit the cron expression and push.

### Manual Regression Input

Enable in workflow dispatch:
```yaml
regression_mode:
  description: Run as full regression (updates cache baseline)
  required: false
  type: boolean
  default: false
```

Check the input checkbox when triggering manually.

---

## 🐛 Troubleshooting

### Problem: "No cached baseline available"

**Cause:** Cache not initialized  
**Solution:**
```powershell
.\scripts\init-cache.ps1
```
Then re-run the test.

### Problem: Full suite still running on PR

**Diagnosis:**
```bash
grep "STANDARD MODE\|REGRESSION MODE" comparison-report/comparison-report.md
```

**Expected output:**
```
STANDARD MODE: Smart Tests Only (No Full Suite)
```

If showing `REGRESSION MODE`: Check that `--regression` flag isn't being passed.

### Problem: Cache not being used

**Verify cache exists:**
```bash
cat test-results/regression-cache/latest-full-suite.json
```

**If missing:** Run `init-cache.ps1`

### Problem: Tests taking too long

**Check execution mode:**
1. Look for "STANDARD MODE" or "REGRESSION MODE" in output
2. Should see "STANDARD MODE" for PR runs
3. Should see ~30 seconds, not 180+

---

## 📈 Performance Metrics

### Time Comparison

| Scenario | Full Suite | Smart Selection | Savings |
|----------|-----------|-----------------|---------|
| First setup (init-cache) | N/A | 180 sec full suite | One-time |
| Typical PR run | 180 sec | 30 sec | **150 sec (83%)** |
| Nightly regression | 180 sec | N/A | Scheduled |

### Defect Detection

When cache is used, typical catch rate: **98-100%**
- Smart tests detect most failures
- Cache baseline provides comprehensive comparison

---

## ✅ Verification Checklist

After setup, verify:

- [ ] Cache file exists: `ls test-results/regression-cache/latest-full-suite.json`
- [ ] Cache has recent timestamp
- [ ] PR test output shows "STANDARD MODE"
- [ ] PR test execution time is ~30 seconds
- [ ] Comparison report shows cached baseline used
- [ ] Nightly regression scheduled (check GitHub Actions)

---

## 📝 Quick Reference

```bash
# Initialize cache (first-time, one-time)
.\scripts\init-cache.ps1

# Run smart PR tests
npx playwright test tests/login.spec.js

# Generate comparison report
python scripts/generate_comparison_report.py

# Manual regression (updates cache)
.\scripts\run-regression.ps1
# OR
python scripts/generate_comparison_report.py --regression

# Check cache status
cat test-results/regression-cache/latest-full-suite.json | grep timestamp
```

---

## 🎓 Key Concepts

| Term | Meaning |
|------|---------|
| **Smart Selection** | ML algorithm that picks relevant tests for a PR change |
| **Cache Baseline** | Stored full suite results for comparison purposes |
| **Regression Run** | Full suite execution that creates/updates cache |
| **PR Run** | Fast execution using only smart-selected tests |
| **Comparison** | Metrics comparing smart selection against baseline |

---

## 🏁 Summary

1. **First day:** Run `init-cache.ps1` (~3-5 min, one-time)
2. **All PRs after:** Automatic smart selection (~30 sec, every time)
3. **Every night:** Automatic regression refreshes cache (2 AM UTC)
4. **Key guarantee:** PR runs NEVER run full suite (only smart tests)

That's it! 🚀
