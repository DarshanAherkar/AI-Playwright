#!/usr/bin/env python3
"""
Smart Test Selector: scikit-learn + LLM Pipeline
─────────────────────────────────────────────
Layer 1 - ML (Ranking):
    scikit-learn Logistic Regression
    Features: token overlap, content overlap, path hints, change scope

Layer 2 - LLM (Reasoning):
  TinyLlama validates ML candidates and explains the selection

Fully dynamic - no hardcoded mappings.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import re
import sys
import urllib.request

from sklearn.linear_model import LogisticRegression

OLLAMA_URL = "http://localhost:11434"
MODEL = "tinyllama"
THRESHOLD = 0.15   # minimum ML score to include a test
RELATIVE_CUTOFF = 0.50  # must score >= 50% of top scorer
MAX_LLM_CANDIDATES = 3  # LLM can only validate the top-N ML candidates

# Playwright boilerplate tokens to ignore in TF-IDF
STOPWORDS = {
    "test", "expect", "page", "describe", "async", "await", "const", "let",
    "return", "from", "import", "require", "toBe", "toBeVisible", "toHaveURL",
    "goto", "click", "fill", "locator", "getByText", "getByRole",
    "beforeEach", "afterEach", "browser", "context", "true", "false",
    "js", "spec", "tests", "src", "pages"
}


# ── Utilities ────────────────────────────────────────────────────────────────

def tokenize(text):
    tokens = re.findall(r'[a-z][a-z0-9]+', text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]


def discover_tests(workspace):
    """Dynamically scan tests/ directory - no hardcoding."""
    tests_dir = os.path.join(workspace, "tests")
    if not os.path.isdir(tests_dir):
        return ["tests/pom-smoke.spec.js"]
    return sorted(
        f"tests/{f}" for f in os.listdir(tests_dir)
        if f.endswith(".spec.js")
    )


def extract_meaningful_tokens(content, test_name):
    """
    Extract only meaningful tokens from test files:
    - describe() block names (domain context)
    - test() names (what is being tested)
    - Imported page object names
    - Page method call names
    Ignores Playwright boilerplate that is identical across all tests.
    """
    tokens = []
    # test/describe labels - most informative
    tokens += re.findall(r'(?:describe|test)\([\'"]([^\'"]+)[\'"]', content)
    # import paths e.g. './login.page'
    tokens += re.findall(r'[\'"]\./([\w-]+)\.page', content)
    # page object variable usage e.g. loginPage.xxx
    tokens += re.findall(r'(\w+Page)\.(\w+)', content)
    # test file stem itself
    stem = re.sub(r'tests/|\.spec\.js', '', test_name)
    tokens.append(stem)
    return " ".join(str(t) for t in tokens)


def read_test_contents(workspace, tests):
    """Read each test file and extract meaningful tokens only."""
    contents = {}
    for test in tests:
        path = os.path.join(workspace, test)
        try:
            with open(path, encoding="utf-8") as fh:
                raw = fh.read()
            contents[test] = extract_meaningful_tokens(raw, test)
        except Exception:
            contents[test] = re.sub(r'tests/|\.spec\.js', '', test)
    return contents


def build_features(changed_files, test, test_contents):
    """Create numeric features for one (PR change set, test) pair."""
    changed_text = " ".join(changed_files)
    changed_tokens = set(tokenize(changed_text))

    test_stem = re.sub(r'tests/|\.spec\.js', '', test)
    test_tokens = set(tokenize(test_stem))
    content_tokens = set(tokenize(test_contents.get(test, "")))

    union = test_tokens | changed_tokens
    token_overlap = len(test_tokens & changed_tokens) / len(union) if union else 0.0
    content_overlap = len(content_tokens & changed_tokens) / (len(changed_tokens) or 1)

    stem_exact_in_changed = 1.0 if test_stem.replace("-", "") in changed_text.replace("-", "") else 0.0
    test_file_changed = 1.0 if test in changed_files else 0.0
    page_hint = 1.0 if any(f"{test_stem}.page" in cf for cf in changed_files) else 0.0

    avg_depth = sum(f.count('/') for f in changed_files) / (len(changed_files) or 1)
    depth_norm = min(1.0, avg_depth / 5)
    changed_count_norm = min(1.0, len(changed_files) / 20)

    smoke_boost = 0.0
    if test.endswith("pom-smoke.spec.js"):
        broad_change = any(
            cf.startswith("mock-app/") or (
                cf.startswith("src/") and not any(tag in cf for tag in ["login", "signup", "about", "contact"])
            )
            for cf in changed_files
        )
        smoke_boost = 1.0 if broad_change else 0.0

    features = [
        token_overlap,
        content_overlap,
        stem_exact_in_changed,
        test_file_changed,
        page_hint,
        depth_norm,
        changed_count_norm,
        smoke_boost,
    ]

    feature_map = {
        "token_overlap": round(token_overlap, 4),
        "content_overlap": round(content_overlap, 4),
        "stem_exact": round(stem_exact_in_changed, 4),
        "test_file_changed": round(test_file_changed, 4),
        "page_hint": round(page_hint, 4),
        "path_depth": round(depth_norm, 4),
        "change_scope": round(changed_count_norm, 4),
        "smoke_boost": round(smoke_boost, 4),
    }
    return features, feature_map


def weak_label(changed_files, test):
    """Weak supervision labels for on-the-fly ranking model training."""
    changed_text = " ".join(changed_files).lower()
    stem = re.sub(r'tests/|\.spec\.js', '', test).lower()

    if test in changed_files:
        return 1
    if stem.replace("-", "") in changed_text.replace("-", ""):
        return 1
    if any(f"{stem}.page" in cf.lower() for cf in changed_files):
        return 1
    if stem == "pom-smoke" and any(cf.startswith("mock-app/") for cf in changed_files):
        return 1
    return 0


def ml_rank(changed_files, tests, test_contents):
    """Train a lightweight scikit-learn ranker and score tests."""
    X = []
    y = []
    feature_maps = {}

    for test in tests:
        feature_vec, fmap = build_features(changed_files, test, test_contents)
        X.append(feature_vec)
        y.append(weak_label(changed_files, test))
        feature_maps[test] = fmap

    if len(set(y)) < 2:
        y = [1 if i == 0 else 0 for i in range(len(tests))]

    model = LogisticRegression(random_state=42, solver="liblinear")
    model.fit(X, y)
    probabilities = model.predict_proba(X)

    results = {}
    for i, test in enumerate(tests):
        score = float(probabilities[i][1])
        results[test] = {
            "score": round(score, 4),
            "features": feature_maps[test]
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
    candidate_tests = [c["test"] for c in candidates]
    candidates_str = "\n".join(f"  - {t}" for t in candidate_tests)

    prompt = (
        "You are a precise test selection assistant. Be selective - run minimal tests.\n"
        f"Changed files:\n{changed_str}\n"
        f"PR title: {pr_title}\n\n"
        "Only choose from this candidate list:\n"
        f"{candidates_str}\n\n"
        "Rules:\n"
        "- Only confirm tests DIRECTLY related to the changed files\n"
        "- You MUST choose from candidate list only\n"
        "- Do NOT add unrelated tests\n"
        "- If only login changed, only confirm login test\n"
        "Output ONLY the confirmed test filenames, one per line, nothing else.\n"
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
        filtered = [t for t in found if t in candidate_tests and t in available_tests]
        filtered = list(dict.fromkeys(filtered))
        return filtered or None


# ── Pipeline ──────────────────────────────────────────────────────────────────

def select_tests(changed_files, pr_title, workspace):
    """
    Full scikit-learn + LLM pipeline:
    1. Discover tests dynamically
    2. ML:  scikit-learn ranking over feature vectors
    3. LLM: TinyLlama validation
    """
    available_tests = discover_tests(workspace)
    print(f"[INFO] Discovered tests: {available_tests}")

    if not changed_files:
        default = "tests/pom-smoke.spec.js" if "tests/pom-smoke.spec.js" in available_tests else available_tests[0]
        return [default], "default", [{
            "test": default,
            "priority_score": 0.5,
            "evidence": "No changed files provided",
            "reasoning": "Default smoke coverage"
        }]

    test_contents = read_test_contents(workspace, available_tests)

    print("[ML] Training scikit-learn ranker and scoring tests...")
    ml_scores = ml_rank(changed_files, available_tests, test_contents)
    for t, v in list(ml_scores.items())[:5]:
        print(f"  ML  {v['score']:.4f} | {t} | {v['features']}")

    # Filter by RELATIVE threshold: must score >= 50% of top scorer
    best = max((v["score"] for v in ml_scores.values()), default=0)
    cutoff = max(THRESHOLD, best * RELATIVE_CUTOFF)
    print(f"[ML] Best score: {best:.4f} | Cutoff: {cutoff:.4f}")

    candidates = [
        {"test": t, "score": v["score"], "features": v["features"]}
        for t, v in ml_scores.items()
        if v["score"] >= cutoff
    ]

    if not candidates:
        default = "tests/pom-smoke.spec.js" if "tests/pom-smoke.spec.js" in available_tests else available_tests[0]
        candidates = [{"test": default, "score": 0.1, "features": {}}]

    # Bound LLM scope to top-N ML tests so it cannot expand to entire suite.
    candidates = candidates[:MAX_LLM_CANDIDATES]

    # Layer 2 - LLM
    print(f"[LLM] Sending {len(candidates)} candidates to TinyLlama...")
    try:
        llm_tests = llm_validate(changed_files, pr_title, candidates, available_tests)
        if llm_tests:
            print(f"[OK] LLM validated: {llm_tests}")
            # Keep ML order and only include LLM-confirmed tests.
            llm_confirmed = set(llm_tests)
            final = [c["test"] for c in candidates if c["test"] in llm_confirmed]
            if not final:
                final = [c["test"] for c in candidates]
            mode = "ml+rag+llm"
            explanations = [
                {
                    "test": t,
                    "priority_score": ml_scores.get(t, {}).get("score", 0.5),
                    "evidence": f"sklearn_score={ml_scores.get(t,{}).get('score',0):.3f}",
                    "reasoning": f"ML features: {ml_scores.get(t, {}).get('features', {})} | Confirmed by LLM"
                }
                for t in final
            ]
            final = list(dict.fromkeys(final))
            return final, "sklearn+llm", explanations
    except Exception as e:
        print(f"[WARN] LLM error: {e} - using ML results only")

    # ML-only result
    final = [c["test"] for c in candidates]
    final = list(dict.fromkeys(final))
    mode = "sklearn"
    explanations = [
        {
            "test": c["test"],
            "priority_score": c["score"],
            "evidence": f"sklearn_score={c['score']:.3f}",
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
            self.wfile.write(json.dumps({"status": "ok", "model": MODEL, "pipeline": "scikit-learn+LLM"}).encode())
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
        print(f"[OK] Pipeline: scikit-learn ranking -> LLM (TinyLlama)")
        server.serve_forever()
    except OSError as e:
        print(f"[ERROR] Cannot bind to port {port}: {e}")
        sys.exit(1)
