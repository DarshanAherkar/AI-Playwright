# Run full regression test suite and cache results for future comparisons

Write-Host "==========================================" -ForegroundColor Green
Write-Host "FULL REGRESSION TEST RUN" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "[INFO] This will:" -ForegroundColor Cyan
Write-Host "  1. Run the full Playwright test suite" -ForegroundColor Cyan
Write-Host "  2. Save results to regression cache" -ForegroundColor Cyan
Write-Host "  3. Generate comparison report" -ForegroundColor Cyan
Write-Host ""
Write-Host "Cache timestamp will be used for all future PR comparisons" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""

# Run the comparison script in regression mode
python scripts/generate_comparison_report.py --regression

$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "[SUCCESS] Regression run complete" -ForegroundColor Green
    Write-Host "[INFO] Full suite results cached and available for PR comparisons" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host "[ERROR] Regression run failed with exit code: $exitCode" -ForegroundColor Red
    Write-Host "==========================================" -ForegroundColor Red
}

exit $exitCode
