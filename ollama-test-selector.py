#!/usr/bin/env python3
"""
Smart Test Selector: ML + RAG + LLM Pipeline
─────────────────────────────────────────────
Layer 1 - RAG (Retrieval-Augmented Generation):
  Pure Python TF-IDF vectorization + cosine similarity
  Reads actual test file contents to find semantically similar tests

Layer 2 - ML (Ranking):
  Weighted multi-feature scoring (no training data needed)
  Features: RAG similarity, token overlap, content match, path depth

Layer 3 - LLM (Reasoning):
  TinyLlama validates ML candidates and explains the selection

Fully dynamic - no hardcoded mappings.
"""

from collections import defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import math
import os
import re
import sys
import urllib.request

OLLAMA_URL = "http://localhost:11434"
MODEL = "tinyllama"
THRESHOLD = 0.15   # minimum ML score to include a test


# ── Utilities ────────────────────────────────────────────────────────────────

def tokenize(text):
    return re.findall(r'[a-z0-9]+', text.lower())


def discover_tests(workspace):
    """Dynamically scan tests/ directory - no hardcoding."""
    tests_dir = os.path.join(workspace, "tests")
    if not os.path.isdir(tests_dir):
        return ["tests/pom-smoke.spec.js"]
    return sorted(
        f"tests/{f}" for f in os.listdir(tests_dir)
        if f.endswith(".spec.js")
    )


def read_test_contents(workspace, tests):
    """Read each test file's source for semantic analysis."""
    contents = {}
    for test in tests:
        path = os.path.join(workspace, test)
        try:
            with open(path, encoding="utf-8") as fh:
                contents[test] = fh.read()
        except Exception:
            contents[test] = test
    return contents


# ── Layer 1: RAG (TF-IDF Retrieval) ──────────────────────────────────────────

def build_tfidf(docs):
    """Build TF-IDF vectors for a list of documents."""
    tf_list = []
    for doc in docs:
        tokens = tokenize(doc)
        freq = defaultdict(int)
        for t in tokens:
            freq[t] += 1
        total = len(tokens) or 1
        tf_list.append({t: c / total for t, c in freq.items()})

    N = len(docs)
    df = defaultdict(int)
    for tf in tf_list:
        for t in tf:
            df[t] += 1
    idf = {t: math.log((N + 1) / (df[t] + 1)) for t in df}

    return [{t: v * idf.get(t, 0) for t, v in tf.items()} for tf in tf_list]


def cosine_sim(a, b):
    keys = set(a) & set(b)
    if not keys:
        return 0.0
    dot = sum(a[k] * b[k] for k in keys)
    mag = math.sqrt(sum(v**2 for v in a.values())) * math.sqrt(sum(v**2 for v in b.values()))
    return dot / mag if mag else 0.0


def rag_retrieve(changed_files, tests, test_contents):
    """
    RAG Layer: Embed changed files + test content using TF-IDF.
    Returns cosine similarity score per test.
    """
    query = " ".join(changed_files)
    corpus = [query] + [
        f"{test} {test_contents.get(test, '')}" for test in tests
    ]
    vecs = build_tfidf(corpus)
    query_vec = vecs[0]
    return {
        test: cosine_sim(query_vec, vecs[i + 1])
        for i, test in enumerate(tests)
    }


# ── Layer 2: ML (Feature-Based Ranking) ──────────────────────────────────────

def ml_rank(changed_files, tests, test_contents, rag_scores):
    """
    ML Layer: Multi-feature weighted scoring.

    Features:
      F1 (w=0.40) RAG semantic similarity     - TF-IDF cosine similarity
      F2 (w=0.35) Token overlap               - shared tokens in names
      F3 (w=0.15) Content keyword match       - test file mentions changed file terms
      F4 (w=0.10) Path depth penalty          - deeper change = broader impact

    Returns dict of test -> (score, feature_breakdown)
    """
    changed_tokens = set(tokenize(" ".join(changed_files)))
    results = {}

    for test in tests:
        # F1: RAG score
        f1 = rag_scores.get(test, 0.0)

        # F2: Token overlap between changed filenames and test name
        test_stem = re.sub(r'tests/|\.spec\.js', '', test)
        test_tokens = set(tokenize(test_stem))
        union = test_tokens | changed_tokens
        f2 = len(test_tokens & changed_tokens) / len(union) if union else 0.0

        # F3: Content keyword match - does test file reference changed file terms?
        content_tokens = set(tokenize(test_contents.get(test, "")))
        f3 = len(changed_tokens & content_tokens) / (len(changed_tokens) or 1)

        # F4: Avg path depth of changed files (deeper = less specific impact)
        avg_depth = sum(f.count('/') for f in changed_files) / (len(changed_files) or 1)
        f4 = min(1.0, avg_depth / 4)   # normalize 0-1

        score = (f1 * 0.40) + (f2 * 0.35) + (f3 * 0.15) + (f4 * 0.10)

        results[test] = {
            "score": round(min(1.0, score), 4),
            "features": {
                "rag_similarity": round(f1, 4),
                "token_overlap": round(f2, 4),
                "content_match": round(f3, 4),
                "path_depth": round(f4, 4)
            }
        }

    return dict(sorted(results.items(), key=lambda x: x[1]["score"], reverse=True))


# ── Layer 3: LLM (TinyLlama Reasoning) ───────────────────────────────────────

def llm_validate(changed_files, pr_title, candidates, available_tests):
    """
    LLM Layer: TinyLlama validates ML candidates and provides reasoning.
    Receives only the top ML candidates, not all tests (focused context).
    """
    changed_str = "\n".join(f"  - {f}" for f in changed_files)
    candidates_str = "\n".join(f"  - {t['test']} (ML score: {t['score']})" for t in candidates)
    all_tests_str = "\n".join(f"  - {t}" for t in available_tests)

    prompt = (
        "You are a test selection assistant.\n"
        f"Changed files:\n{changed_str}\n"
        f"PR title: {pr_title}\n\n"
        f"ML pre-selected candidates:\n{candidates_str}\n\n"
        f"All available tests:\n{all_tests_str}\n\n"
        "Task: Confirm or adjust the candidate list. Output ONLY test filenames, one per line."
    )

    payload = json.dumps({"model": MODEL, "prompt": prompt, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        raw = json.loads(resp.read().decode("utf-8")).get("response", "")
        print(f"[LLM] Response: {raw[:300]}")
        found = re.findall(r'tests/[\w-]+\.spec\.js', raw)
        return [t for t in found if t in available_tests] or None


# ── Pipeline ──────────────────────────────────────────────────────────────────

def select_tests(changed_files, pr_title, workspace):
    """
    Full ML + RAG + LLM pipeline:
    1. Discover tests dynamically
    2. RAG: TF-IDF similarity retrieval
    3. ML:  Feature-based ranking
    4. LLM: TinyLlama validation
    """
    available_tests = discover_tests(workspace)
    print(f"[INFO] Discovered tests: {available_tests}")

    test_contents = read_test_contents(workspace, available_tests)

    # Layer 1 - RAG
    print("[RAG] Computing TF-IDF cosine similarity...")
    rag_scores = rag_retrieve(changed_files, available_tests, test_contents)
    for t, s in sorted(rag_scores.items(), key=lambda x: -x[1]):
        print(f"  RAG {s:.4f} | {t}")

    # Layer 2 - ML
    print("[ML] Computing feature scores...")
    ml_scores = ml_rank(changed_files, available_tests, test_contents, rag_scores)
    for t, v in list(ml_scores.items())[:5]:
        print(f"  ML  {v['score']:.4f} | {t} | {v['features']}")

    # Filter by threshold
    candidates = [
        {"test": t, "score": v["score"], "features": v["features"]}
        for t, v in ml_scores.items()
        if v["score"] >= THRESHOLD
    ]

    if not candidates:
        candidates = [{"test": available_tests[0], "score": 0.1, "features": {}}]

    # Layer 3 - LLM
    print(f"[LLM] Sending {len(candidates)} candidates to TinyLlama...")
    try:
        llm_tests = llm_validate(changed_files, pr_title, candidates, available_tests)
        if llm_tests:
            print(f"[OK] LLM validated: {llm_tests}")
            # Merge: keep ML scores for LLM-confirmed tests
            final = llm_tests
            mode = "ml+rag+llm"
            explanations = [
                {
                    "test": t,
                    "priority_score": ml_scores.get(t, {}).get("score", 0.5),
                    "evidence": f"RAG={rag_scores.get(t,0):.3f}, ML={ml_scores.get(t,{}).get('score',0):.3f}",
                    "reasoning": f"ML features: {ml_scores.get(t, {}).get('features', {})} | Confirmed by LLM"
                }
                for t in final
            ]
            return final, mode, explanations
    except Exception as e:
        print(f"[WARN] LLM error: {e} - using ML results only")

    # ML-only result
    final = [c["test"] for c in candidates]
    mode = "ml+rag"
    explanations = [
        {
            "test": c["test"],
            "priority_score": c["score"],
            "evidence": f"RAG={rag_scores.get(c['test'],0):.3f}",
            "reasoning": str(c["features"])
        }
        for c in candidates
    ]
    return final, mode, explanations


# ── HTTP Server ───────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "model": MODEL, "pipeline": "ML+RAG+LLM"}).encode())
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

            tests, mode, explanations = select_tests(changed_files, pr_title, workspace)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "success",
                "selected_tests": tests,
                "mode": mode,
                "explanations": explanations
            }).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    try:
        server = HTTPServer(("0.0.0.0", port), Handler)
        print(f"[OK] Smart Test Selector running on port {port}")
        print(f"[OK] Pipeline: RAG (TF-IDF) -> ML (features) -> LLM (TinyLlama)")
        server.serve_forever()
    except OSError as e:
        print(f"[ERROR] Cannot bind to port {port}: {e}")
        sys.exit(1)

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
