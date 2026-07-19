#!/usr/bin/env python3
import json
import os
import subprocess
import time
from pathlib import Path


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
    selected_tests = os.environ.get("SELECTED_TESTS", "").split()

    smart_cmd = "npx playwright test " + " ".join(selected_tests) + " --reporter=json"
    full_cmd = "npx playwright test --reporter=json"

    if not selected_tests:
        selected_tests = ["tests/pom-smoke.spec.js"]
        smart_cmd = "npx playwright test tests/pom-smoke.spec.js --reporter=json"

    print("[ACTION] Running smart-selected subset for comparison...")
    smart_run = run_playwright(smart_cmd)

    print("[ACTION] Running full suite for comparison...")
    full_run = run_playwright(full_cmd)

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


if __name__ == "__main__":
    main()
