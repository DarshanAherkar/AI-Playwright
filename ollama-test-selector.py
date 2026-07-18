#!/usr/bin/env python3
"""
Ollama Smart Test Selector - Pure Python, Zero Dependencies
Uses http.server + urllib to call TinyLlama for test selection
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import sys
import urllib.request
import urllib.error

OLLAMA_URL = "http://localhost:11434"
MODEL = "tinyllama"

TEST_MAPPING = {
    "login.page.js":    "tests/login.spec.js",
    "signup.page.js":   "tests/signup.spec.js",
    "about-us.page.js": "tests/about-us.spec.js",
    "contact-us.page.js": "tests/contact-us.spec.js",
    "base.page.js":     "tests/pom-smoke.spec.js",
}

ALL_TESTS = list(TEST_MAPPING.values()) + ["tests/pom-smoke.spec.js"]


def file_based_selection(changed_files):
    """Select tests based on file-to-test mapping."""
    selected = set()
    for f in changed_files:
        for key, test in TEST_MAPPING.items():
            if key in f:
                selected.add(test)
        if f.endswith(".html") or f.startswith("mock-app/"):
            selected.add("tests/pom-smoke.spec.js")
    return sorted(list(selected)) if selected else ["tests/pom-smoke.spec.js"]


def get_ollama_suggestion(changed_files, pr_title):
    """Query TinyLlama for intelligent test selection."""
    all_tests_str = ", ".join(set(ALL_TESTS))
    changed_str = ", ".join(changed_files) if changed_files else "(no files)"

    prompt = (
        f"You are a test selection assistant. "
        f"Changed files: {changed_str}. "
        f"PR title: {pr_title}. "
        f"Available tests: {all_tests_str}. "
        f"Reply with ONLY the relevant test file names, comma-separated, no explanation."
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
        tests = [t.strip() for t in raw.replace("\n", ",").split(",") if "tests/" in t and ".spec.js" in t]
        return tests if tests else None


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
    print(f"[OK] Ollama Smart Test Selector running on port {port}")
    print(f"[OK] Model: {MODEL} | Ollama: {OLLAMA_URL}")
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()
