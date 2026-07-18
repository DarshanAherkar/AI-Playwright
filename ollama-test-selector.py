#!/usr/bin/env python3
"""
Ollama Smart Test Selector - Dynamic, Zero Hardcoding
Discovers available tests at runtime, uses TinyLlama for intelligent selection.
Adding a new page/test requires NO changes to this file.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import re
import sys
import urllib.request

OLLAMA_URL = "http://localhost:11434"
MODEL = "tinyllama"


def discover_tests(workspace_path):
    """
    Dynamically scan the tests/ directory for all .spec.js files.
    No hardcoding - automatically picks up any new test files.
    """
    tests_dir = os.path.join(workspace_path, "tests")
    if not os.path.isdir(tests_dir):
        return ["tests/pom-smoke.spec.js"]
    return sorted(
        f"tests/{f}" for f in os.listdir(tests_dir)
        if f.endswith(".spec.js")
    )


def get_ollama_suggestion(changed_files, pr_title, available_tests):
    """
    Ask TinyLlama to select tests based on:
    - What files changed (semantic understanding of filenames)
    - PR title (intent)
    - Full list of available tests (discovered dynamically)
    No mapping needed - LLM reasons about the relationship.
    """
    changed_str = "\n".join(f"  - {f}" for f in changed_files) if changed_files else "  (none)"
    tests_str = "\n".join(f"  - {t}" for t in available_tests)

    prompt = (
        "You are a test selection assistant for a web app.\n"
        "Your job: given changed files and a PR title, pick ONLY the relevant tests to run.\n"
        "\n"
        f"Changed files:\n{changed_str}\n"
        f"\nPR title: {pr_title}\n"
        f"\nAvailable tests:\n{tests_str}\n"
        "\nRules:\n"
        "- Pick tests whose name relates to the changed files\n"
        "- A file named login.html or login.page.js relates to login.spec.js\n"
        "- A file named signup relates to signup.spec.js\n"
        "- If unsure or multiple pages changed, include pom-smoke.spec.js\n"
        "- Output ONLY the test filenames, one per line, nothing else\n"
    )

    payload = json.dumps({"model": MODEL, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        raw = result.get("response", "").strip()
        print(f"[LLM] Raw response: {raw[:200]}")

        # Extract paths matching tests/xxx.spec.js pattern
        found = re.findall(r'tests/[\w-]+\.spec\.js', raw)
        # Keep only tests that actually exist
        valid = [t for t in found if t in available_tests]
        return valid if valid else None


def select_tests(changed_files, pr_title, workspace_path):
    """Dynamically discover tests, then use TinyLlama to select."""
    available_tests = discover_tests(workspace_path)
    print(f"[INFO] Discovered {len(available_tests)} tests: {available_tests}")

    try:
        ai_tests = get_ollama_suggestion(changed_files, pr_title, available_tests)
        if ai_tests:
            print(f"[OK] TinyLlama selected: {ai_tests}")
            return ai_tests, "tinyllama"
    except Exception as e:
        print(f"[WARN] Ollama error: {e}")

    # Minimal fallback: match by keyword only (no hardcoded mapping)
    print("[FALLBACK] Keyword matching...")
    selected = set()
    for f in changed_files:
        name = f.replace("-", "").replace("_", "").replace(".", "").lower()
        for test in available_tests:
            # Extract test stem e.g. "login" from "tests/login.spec.js"
            stem = re.sub(r'tests/|[\.-]spec\.js', '', test).replace("-", "")
            if stem in name or name in stem:
                selected.add(test)
                print(f"  {f} -> {test}")
    result = sorted(list(selected)) if selected else ["tests/pom-smoke.spec.js"]
    return result, "keyword-fallback"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "model": MODEL}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/v1/select-tests":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))

            changed_files = body.get("changed_files", [])
            pr_title = body.get("pr_title", "")
            workspace = body.get("workspace", os.getcwd())

            tests, mode = select_tests(changed_files, pr_title, workspace)

            response = {
                "status": "success",
                "selected_tests": tests,
                "mode": mode,
                "explanations": [
                    {
                        "test": t,
                        "priority_score": 0.9 if mode == "tinyllama" else 0.6,
                        "evidence": f"Dynamically selected by {mode}",
                        "reasoning": f"Mode: {mode} | Changed: {', '.join(changed_files[:3])}"
                    }
                    for t in tests
                ]
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    try:
        server = HTTPServer(("0.0.0.0", port), Handler)
        print(f"[OK] Ollama Smart Test Selector running on port {port}")
        print(f"[OK] Model: {MODEL} | Ollama: {OLLAMA_URL}")
        print(f"[OK] Tests auto-discovered at runtime - no hardcoding")
        server.serve_forever()
    except OSError as e:
        print(f"[ERROR] Cannot bind to port {port}: {e}")
        print(f"[ERROR] Kill existing process: netstat -ano | findstr :{port}")
        sys.exit(1)

TEST_MAPPING = {
    # Page objects
    "login.page.js":      "tests/login.spec.js",
    "signup.page.js":     "tests/signup.spec.js",
    "about-us.page.js":   "tests/about-us.spec.js",
    "contact-us.page.js": "tests/contact-us.spec.js",
    "base.page.js":       "tests/pom-smoke.spec.js",
    # HTML files
    "login.html":         "tests/login.spec.js",
    "signup.html":        "tests/signup.spec.js",
    "about-us.html":      "tests/about-us.spec.js",
    "about.html":         "tests/about-us.spec.js",
    "contact-us.html":    "tests/contact-us.spec.js",
    "contact.html":       "tests/contact-us.spec.js",
}

ALL_TESTS = list(TEST_MAPPING.values()) + ["tests/pom-smoke.spec.js"]


# Keyword-to-test mapping for fuzzy matching
KEYWORD_MAPPING = {
    "login":   "tests/login.spec.js",
    "signin":  "tests/login.spec.js",
    "signup":  "tests/signup.spec.js",
    "register": "tests/signup.spec.js",
    "about":   "tests/about-us.spec.js",
    "contact": "tests/contact-us.spec.js",
}


def file_based_selection(changed_files):
    """Select tests based on file-to-test mapping + keyword matching."""
    selected = set()
    for f in changed_files:
        filename = f.split("/")[-1].lower()
        matched = False
        # Exact key match
        for key, test in TEST_MAPPING.items():
            if key in f:
                selected.add(test)
                matched = True
        # Keyword match on filename
        if not matched:
            for keyword, test in KEYWORD_MAPPING.items():
                if keyword in filename:
                    selected.add(test)
                    matched = True
                    break
        # Generic HTML/CSS change → smoke
        if not matched and (f.endswith(".html") or f.endswith(".css") or f.startswith("mock-app/")):
            selected.add("tests/pom-smoke.spec.js")
    return sorted(list(selected)) if selected else ["tests/pom-smoke.spec.js"]


def get_ollama_suggestion(changed_files, pr_title):
    """Query TinyLlama for intelligent test selection."""
    all_tests_str = ", ".join(set(ALL_TESTS))
    changed_str = ", ".join(changed_files) if changed_files else "(no files)"

    prompt = (
        f"Files changed: {changed_str}. "
        f"PR: {pr_title}. "
        f"Pick tests from this list only: {all_tests_str}. "
        f"Output only the exact test filenames from the list above, one per line."
    )

    payload = json.dumps({"model": MODEL, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        raw = result.get("response", "").strip()
        # Extract only valid test paths matching known pattern
        import re
        tests = re.findall(r'tests/[\w-]+\.spec\.js', raw)
        # Filter to only tests that actually exist in our list
        valid = [t for t in tests if t in ALL_TESTS]
        return valid if valid else None


def select_tests(changed_files, pr_title):
    """Try Ollama first, fall back to mapping."""
    try:
        ai_tests = get_ollama_suggestion(changed_files, pr_title)
        if ai_tests:
            print(f"[OK] TinyLlama selected: {ai_tests}")
            return ai_tests, "tinyllama"
    except Exception as e:
        print(f"[WARN] Ollama error: {e} - using file mapping")

    tests = file_based_selection(changed_files)
    print(f"[FALLBACK] File mapping selected: {tests}")
    return tests, "fallback"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "model": MODEL}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/v1/select-tests":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))

            changed_files = body.get("changed_files", [])
            pr_title = body.get("pr_title", "")

            tests, mode = select_tests(changed_files, pr_title)

            response = {
                "status": "success",
                "selected_tests": tests,
                "mode": mode,
                "explanations": [{"test": t, "priority_score": 0.85, "evidence": f"Selected by {mode}", "reasoning": f"Mode: {mode}"} for t in tests]
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    try:
        server = HTTPServer(("0.0.0.0", port), Handler)
        print(f"[OK] Ollama Smart Test Selector running on port {port}")
        print(f"[OK] Model: {MODEL} | Ollama: {OLLAMA_URL}")
        server.serve_forever()
    except OSError as e:
        print(f"[ERROR] Cannot bind to port {port}: {e}")
        print(f"[ERROR] Kill existing process: netstat -ano | findstr :{port}")
        sys.exit(1)
