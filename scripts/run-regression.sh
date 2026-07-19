#!/bin/bash
# Run full regression test suite and cache results for future comparisons

echo "=========================================="
echo "FULL REGRESSION TEST RUN"
echo "=========================================="
echo ""
echo "[INFO] This will:"
echo "  1. Run the full Playwright test suite"
echo "  2. Save results to regression cache"
echo "  3. Generate comparison report"
echo ""
echo "Cache timestamp will be used for all future PR comparisons"
echo "=========================================="
echo ""

# Run the comparison script in regression mode
python scripts/generate_comparison_report.py --regression

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "[SUCCESS] Regression run complete"
    echo "[INFO] Full suite results cached and available for PR comparisons"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo "[ERROR] Regression run failed with exit code: $exit_code"
    echo "=========================================="
fi

exit $exit_code
