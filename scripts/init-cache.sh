#!/bin/bash
# Initialize full suite cache baseline (one-time setup)
# Run this once to establish the cache for future PR comparisons

echo "=========================================="
echo "CACHE INITIALIZATION (One-time Setup)"
echo "=========================================="
echo ""
echo "[INFO] This will:"
echo "  1. Run the full Playwright test suite"
echo "  2. Cache results as the regression baseline"
echo "  3. Enable all future PR runs to use this cache"
echo ""
echo "After this runs, all PR tests will be:"
echo "  - Fast (only smart selected tests)"
echo "  - Accurate (compared against this baseline)"
echo ""
echo "=========================================="
echo ""

python scripts/generate_comparison_report.py --regression

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "[SUCCESS] Cache initialized successfully"
    echo "[INFO] Full suite baseline is ready"
    echo "[INFO] PR runs will now be fast and accurate"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo "[ERROR] Cache initialization failed (exit code: $exit_code)"
    echo "=========================================="
fi

exit $exit_code
