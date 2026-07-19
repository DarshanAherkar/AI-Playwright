#!/usr/bin/env python3
import json
import os
import subprocess
import time
import sys
from pathlib import Path
from datetime import datetime


FULL_SUITE_CACHE_DIR = Path("test-results/regression-cache")


def run_playwright(command):
    start = time.time()
    completed = subprocess.run(command, capture_output=True, text=True, shell=True)
    duration = time.time() - start

    stdout = completed.stdout.strip()
    json_start = stdout.find("{")
    report = {}
    if json_start >= 0:
        try:
            report = json.loads(stdout[json_start:])
        except Exception:
            report = {}

    return {
        "exit_code": completed.returncode,
        "duration_seconds": round(duration, 2),
        "report": report,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def save_full_suite_result(full_run):
    """Save full suite result to cache for future comparisons"""
    FULL_SUITE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat()
    cache_file = FULL_SUITE_CACHE_DIR / "latest-full-suite.json"
    
    cache_data = {
        "timestamp": timestamp,
        "duration_seconds": full_run["duration_seconds"],
        "exit_code": full_run["exit_code"],
        "report": full_run["report"],
        "stdout": full_run["stdout"],
        "stderr": full_run["stderr"],
    }
    
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2)
    
    print(f"[CACHE] Full suite results saved to {cache_file}")
    return cache_file


def load_full_suite_result():
    """Load the last full suite result from cache"""
    cache_file = FULL_SUITE_CACHE_DIR / "latest-full-suite.json"
    
    if not cache_file.exists():
        return None
    
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cache_data = json.load(f)
        
        timestamp = cache_data.get("timestamp", "unknown")
        print(f"[CACHE] Loaded full suite results from {timestamp}")
        
        return {
            "exit_code": cache_data["exit_code"],
            "duration_seconds": cache_data["duration_seconds"],
            "report": cache_data["report"],
            "stdout": cache_data["stdout"],
            "stderr": cache_data["stderr"],
            "cached": True,
            "cache_timestamp": timestamp,
        }
    except Exception as e:
        print(f"[ERROR] Failed to load cache: {e}")
        return None


def count_results(node):
    totals = {"total": 0, "failed": 0, "passed": 0, "flaky": 0, "skipped": 0}

    def walk_suite(suite):
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                totals["total"] += 1
                results = test.get("results", [])
                statuses = [r.get("status", "") for r in results]
                if "failed" in statuses or "timedOut" in statuses:
                    totals["failed"] += 1
                elif "flaky" in statuses:
                    totals["flaky"] += 1
                elif "skipped" in statuses or "interrupted" in statuses:
                    totals["skipped"] += 1
                else:
                    totals["passed"] += 1
        for child in suite.get("suites", []):
            walk_suite(child)

    for root in node.get("suites", []):
        walk_suite(root)

    return totals


def build_markdown(selected_tests, smart_run, full_run, smart_counts, full_counts):
    smart_time = smart_run["duration_seconds"]
    full_time = full_run["duration_seconds"]
    saved = round(max(0.0, full_time - smart_time), 2)
    reduction = round((saved / full_time * 100.0), 2) if full_time > 0 else 0.0

    full_failed = full_counts["failed"]
    smart_failed = smart_counts["failed"]
    catch_rate = round((smart_failed / full_failed * 100.0), 2) if full_failed > 0 else 100.0

    lines = []
    lines.append("# Smart Selection Comparison Report")
    lines.append("")
    
    # Data source info
    lines.append("## Data Source")
    if full_run.get("cached"):
        cache_timestamp = full_run.get("cache_timestamp", "unknown")
        lines.append(f"- Full-suite reference: From regression cache (timestamp: {cache_timestamp})")
        lines.append(f"- Smart-selected tests: Fresh run (current PR)")
    else:
        lines.append(f"- Full-suite reference: Fresh run (current execution)")
        lines.append(f"- Smart-selected tests: Fresh run (current execution)")
    lines.append("")
    
    lines.append("## Run Inputs")
    lines.append(f"- Selected tests: {' '.join(selected_tests) if selected_tests else 'None'}")
    lines.append("")
    lines.append("## Runtime Comparison")
    lines.append(f"- Smart-selected subset runtime: {smart_time} sec")
    lines.append(f"- Full-suite runtime: {full_time} sec")
    lines.append(f"- Time saved: {saved} sec")
    lines.append(f"- Runtime reduction: {reduction}%")
    lines.append("")
    lines.append("## Defect Detection Comparison")
    lines.append(f"- Failed tests in smart-selected subset: {smart_failed}")
    lines.append(f"- Failed tests in full suite: {full_failed}")
    lines.append(f"- Defects catch ratio vs full suite: {catch_rate}%")
    lines.append("")
    lines.append("## Test Counts")
    lines.append(f"- Smart subset total tests: {smart_counts['total']}")
    lines.append(f"- Full suite total tests: {full_counts['total']}")
    lines.append("")
    lines.append("## Exit Codes")
    lines.append(f"- Smart subset exit code: {smart_run['exit_code']}")
    lines.append(f"- Full suite exit code: {full_run['exit_code']}")
    lines.append("")
    return "\n".join(lines)


def main():
    # Check for regression mode flag
    is_regression_run = "--regression" in sys.argv
    
    selected_tests = os.environ.get("SELECTED_TESTS", "").split()

    smart_cmd = "npx playwright test " + " ".join(selected_tests) + " --reporter=json"
    full_cmd = "npx playwright test --reporter=json"

    if not selected_tests:
        selected_tests = ["tests/pom-smoke.spec.js"]
        smart_cmd = "npx playwright test tests/pom-smoke.spec.js --reporter=json"

    print("[ACTION] Running smart-selected subset for comparison...")
    smart_run = run_playwright(smart_cmd)

    # Handle full suite reference
    if is_regression_run:
        print("[ACTION] Regression run: Running full suite and caching results...")
        full_run = run_playwright(full_cmd)
        save_full_suite_result(full_run)
    else:
        print("[ACTION] Standard run: Loading full suite results from cache...")
        cached_full_run = load_full_suite_result()
        
        if cached_full_run:
            full_run = cached_full_run
            print("[INFO] Using cached full suite results for comparison")
        else:
            print("[WARNING] No cached full suite results found. Running full suite now...")
            full_run = run_playwright(full_cmd)
            save_full_suite_result(full_run)

    smart_counts = count_results(smart_run["report"]) if smart_run["report"] else {
        "total": 0,
        "failed": 0,
        "passed": 0,
        "flaky": 0,
        "skipped": 0,
    }
    full_counts = count_results(full_run["report"]) if full_run["report"] else {
        "total": 0,
        "failed": 0,
        "passed": 0,
        "flaky": 0,
        "skipped": 0,
    }

    artifact_dir = Path("comparison-report")
    artifact_dir.mkdir(exist_ok=True)

    summary = {
        "selected_tests": selected_tests,
        "is_regression_run": is_regression_run,
        "full_suite_cached": full_run.get("cached", False),
        "cache_timestamp": full_run.get("cache_timestamp", None),
        "smart_run": {
            "duration_seconds": smart_run["duration_seconds"],
            "exit_code": smart_run["exit_code"],
            "counts": smart_counts,
        },
        "full_run": {
            "duration_seconds": full_run["duration_seconds"],
            "exit_code": full_run["exit_code"],
            "counts": full_counts,
        },
    }

    with open(artifact_dir / "comparison-summary.json", "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)

    markdown = build_markdown(selected_tests, smart_run, full_run, smart_counts, full_counts)
    with open(artifact_dir / "comparison-report.md", "w", encoding="utf-8") as handle:
        handle.write(markdown)

    with open(artifact_dir / "smart-selected-output.txt", "w", encoding="utf-8") as handle:
        handle.write(smart_run["stdout"])
        if smart_run["stderr"]:
            handle.write("\n\n--- STDERR ---\n")
            handle.write(smart_run["stderr"])

    with open(artifact_dir / "full-suite-output.txt", "w", encoding="utf-8") as handle:
        handle.write(full_run["stdout"])
        if full_run["stderr"]:
            handle.write("\n\n--- STDERR ---\n")
            handle.write(full_run["stderr"])

    print(markdown)
    print("\n[SUCCESS] Comparison report generated")
    print(f"[INFO] Report saved to: {artifact_dir}")


if __name__ == "__main__":
    main()
