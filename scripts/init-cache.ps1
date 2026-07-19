# Initialize full suite cache baseline (one-time setup)
# Run this once to establish the cache for future PR comparisons

Write-Host "==========================================" -ForegroundColor Green
Write-Host "CACHE INITIALIZATION (One-time Setup)" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "[INFO] This will:" -ForegroundColor Cyan
Write-Host "  1. Run the full Playwright test suite" -ForegroundColor Cyan
Write-Host "  2. Cache results as the regression baseline" -ForegroundColor Cyan
Write-Host "  3. Enable all future PR runs to use this cache" -ForegroundColor Cyan
Write-Host ""
Write-Host "After this runs, all PR tests will be:" -ForegroundColor Cyan
Write-Host "  - Fast (only smart selected tests)" -ForegroundColor Cyan
Write-Host "  - Accurate (compared against this baseline)" -ForegroundColor Cyan
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

python scripts/generate_comparison_report.py --regression

$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "[SUCCESS] Cache initialized successfully" -ForegroundColor Green
    Write-Host "[INFO] Full suite baseline is ready" -ForegroundColor Green
    Write-Host "[INFO] PR runs will now be fast and accurate" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host "[ERROR] Cache initialization failed (exit code: $exitCode)" -ForegroundColor Red
    Write-Host "==========================================" -ForegroundColor Red
}

exit $exitCode
