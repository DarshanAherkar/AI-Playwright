#!/usr/bin/env python3
"""
Smart Test Selector: scikit-learn + RAG + LLM Pipeline
─────────────────────────────────────────────
Layer 1 - ML (Ranking):
    scikit-learn Logistic Regression
    Features: token overlap, content overlap, path hints, change scope, RAG signals

Layer 2 - RAG (Historical Retrieval):
    Retrieves similar historical PRs using TF-IDF cosine similarity
    Adds failure/selection evidence for impacted tests

Layer 3 - LLM (Reasoning):
  TinyLlama validates ML candidates and explains the selection

Fully dynamic - no hardcoded mappings.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
import re
import sys
import urllib.request

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics.pairwise import cosine_similarity

OLLAMA_URL = "http://localhost:11434"
MODEL = "tinyllama"
THRESHOLD = 0.15   # minimum ML score to include a test
RELATIVE_CUTOFF = 0.50  # must score >= 50% of top scorer
MAX_LLM_CANDIDATES = 3  # LLM can only validate the top-N ML candidates
RAG_TOP_K = 5

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


def normalize_test_name(test_name):
    if not test_name:
        return None
    name = str(test_name).strip()
    if not name:
        return None
    if name.startswith("tests/"):
        return name
    if name.endswith(".spec.js"):
        return f"tests/{name}"
    return None


def load_historical_records(workspace):
    """Load historical PR execution records for RAG retrieval."""
    records = []

    history_path = os.path.join(workspace, "historical-pr-data.json")
    if os.path.isfile(history_path):
        try:
            with open(history_path, encoding="utf-8") as fh:
                payload = json.load(fh)
            records.extend(payload.get("records", []))
        except Exception as exc:
            print(f"[WARN] Could not load historical-pr-data.json: {exc}")

    metadata_path = os.path.join(workspace, "test-metadata.json")
    if os.path.isfile(metadata_path):
        try:
            with open(metadata_path, encoding="utf-8") as fh:
                payload = json.load(fh)
            records.extend(payload.get("historical_pr_runs", []))
        except Exception as exc:
            print(f"[WARN] Could not load historical_pr_runs from test-metadata.json: {exc}")

    cleaned = []
    for record in records:
        selected = [normalize_test_name(t) for t in record.get("selected_tests", [])]
        failed = [normalize_test_name(t) for t in record.get("failed_tests", [])]
        record["selected_tests"] = [t for t in selected if t]
        record["failed_tests"] = [t for t in failed if t]
        cleaned.append(record)
    return cleaned


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


def record_to_text(record):
    changed_files = " ".join(record.get("changed_files", []))
    selected_tests = " ".join(record.get("selected_tests", []))
    failed_tests = " ".join(record.get("failed_tests", []))
    tags = " ".join(record.get("tags", []))
    return " ".join([
        str(record.get("pr_title", "")),
        str(record.get("summary", "")),
        changed_files,
        selected_tests,
        failed_tests,
        tags,
    ])


def retrieve_historical_context(changed_files, pr_title, historical_records):
    """RAG retrieval over historical PR records using TF-IDF cosine similarity."""
    if not historical_records:
        return {"top_records": [], "test_signals": {}, "total_similarity": 0.0}

    query = " ".join([pr_title, " ".join(changed_files)]).strip()
    corpus = [record_to_text(record) for record in historical_records]

    try:
        vectorizer = TfidfVectorizer(token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9_-]+\b")
        matrix = vectorizer.fit_transform(corpus + [query])
        similarities = cosine_similarity(matrix[-1], matrix[:-1])[0]
    except Exception as exc:
        print(f"[WARN] Historical RAG retrieval failed: {exc}")
        return {"top_records": [], "test_signals": {}, "total_similarity": 0.0}

    ranked_indices = sorted(range(len(similarities)), key=lambda i: similarities[i], reverse=True)
    top_records = []
    test_signals = {}
    total_similarity = 0.0

    for idx in ranked_indices[:RAG_TOP_K]:
        sim = float(similarities[idx])
        if sim <= 0:
            continue
        record = historical_records[idx]
        total_similarity += sim

        top_records.append({
            "pr_id": record.get("pr_id", "n/a"),
            "pr_title": record.get("pr_title", ""),
            "similarity": round(sim, 4),
            "selected_tests": record.get("selected_tests", []),
            "failed_tests": record.get("failed_tests", []),
        })

        for test in record.get("selected_tests", []):
            signal = test_signals.setdefault(test, {
                "selection_sum": 0.0,
                "failure_sum": 0.0,
                "max_similarity": 0.0,
                "hits": 0,
            })
            signal["selection_sum"] += sim
            signal["max_similarity"] = max(signal["max_similarity"], sim)
            signal["hits"] += 1

        for test in record.get("failed_tests", []):
            signal = test_signals.setdefault(test, {
                "selection_sum": 0.0,
                "failure_sum": 0.0,
                "max_similarity": 0.0,
                "hits": 0,
            })
            signal["failure_sum"] += sim
            signal["max_similarity"] = max(signal["max_similarity"], sim)
            signal["hits"] += 1

    return {
        "top_records": top_records,
        "test_signals": test_signals,
        "total_similarity": total_similarity,
    }


def build_rag_evidence_lines(candidate_tests, rag_context):
    lines = []
    signals = rag_context.get("test_signals", {})
    total_similarity = rag_context.get("total_similarity", 0.0)
    denom = total_similarity if total_similarity > 0 else 1.0

    for test in candidate_tests:
        signal = signals.get(test, {})
        rag_select = signal.get("selection_sum", 0.0) / denom
        rag_fail = signal.get("failure_sum", 0.0) / denom
        rag_sim = signal.get("max_similarity", 0.0)
        lines.append(
            f"- {test}: hist_select={rag_select:.3f}, hist_fail={rag_fail:.3f}, best_sim={rag_sim:.3f}"
        )
    return lines


def build_features(changed_files, test, test_contents, rag_context):
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

    test_signal = rag_context.get("test_signals", {}).get(test, {})
    total_similarity = rag_context.get("total_similarity", 0.0)
    denom = total_similarity if total_similarity > 0 else 1.0
    rag_selection = test_signal.get("selection_sum", 0.0) / denom
    rag_failure = test_signal.get("failure_sum", 0.0) / denom
    rag_similarity = test_signal.get("max_similarity", 0.0)

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
        rag_selection,
        rag_failure,
        rag_similarity,
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
        "rag_selection": round(rag_selection, 4),
        "rag_failure": round(rag_failure, 4),
        "rag_similarity": round(rag_similarity, 4),
    }
    return features, feature_map


def weak_label(changed_files, test, rag_context):
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
    signal = rag_context.get("test_signals", {}).get(test, {})
    if signal.get("selection_sum", 0.0) > 0:
        return 1
    return 0


def ml_rank(changed_files, tests, test_contents, rag_context):
    """Train a lightweight scikit-learn ranker and score tests."""
    X = []
    y = []
    feature_maps = {}

    for test in tests:
        feature_vec, fmap = build_features(changed_files, test, test_contents, rag_context)
        X.append(feature_vec)
        y.append(weak_label(changed_files, test, rag_context))
        feature_maps[test] = fmap

    if len(set(y)) < 2:
        y = [1 if i == 0 else 0 for i in range(len(tests))]

    model = LogisticRegression(random_state=42, solver="liblinear")
    model.fit(X, y)
    probabilities = model.predict_proba(X)

    results = {}
    for i, test in enumerate(tests):
        model_score = float(probabilities[i][1])
        fmap = feature_maps[test]

        # Blend model output with deterministic relevance to improve stability
        # on tiny per-request training samples.
        heuristic_score = (
            (fmap.get("token_overlap", 0.0) * 0.30)
            + (fmap.get("content_overlap", 0.0) * 0.15)
            + (fmap.get("stem_exact", 0.0) * 0.20)
            + (fmap.get("page_hint", 0.0) * 0.15)
            + (fmap.get("rag_selection", 0.0) * 0.15)
            + (fmap.get("rag_failure", 0.0) * 0.05)
        )

        score = (model_score * 0.65) + (heuristic_score * 0.35)
        results[test] = {
            "score": round(min(1.0, max(0.0, score)), 4),
            "features": feature_maps[test]
        }

    return dict(sorted(results.items(), key=lambda x: x[1]["score"], reverse=True))


# ── Layer 3: LLM (TinyLlama Reasoning) ───────────────────────────────────────

def llm_validate(changed_files, pr_title, candidates, available_tests, rag_evidence):
    """
    LLM Layer: TinyLlama validates ML candidates and provides reasoning.
    Receives only the top ML candidates, not all tests (focused context).
    """
    changed_str = "\n".join(f"  - {f}" for f in changed_files)
    candidate_tests = [c["test"] for c in candidates]
    candidates_str = "\n".join(f"  - {t}" for t in candidate_tests)
    rag_evidence_str = "\n".join(rag_evidence) if rag_evidence else "- No historical matches"

    prompt = (
        "You are a precise test selection assistant. Be selective - run minimal tests.\n"
        f"Changed files:\n{changed_str}\n"
        f"PR title: {pr_title}\n\n"
        "Historical RAG evidence from similar PRs:\n"
        f"{rag_evidence_str}\n\n"
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
    Full scikit-learn + RAG + LLM pipeline:
    1. Discover tests dynamically
    2. RAG: retrieve similar historical PRs
    3. ML:  scikit-learn ranking over feature vectors + RAG signals
    4. LLM: TinyLlama validation with retrieved evidence
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

    historical_records = load_historical_records(workspace)
    rag_context = retrieve_historical_context(changed_files, pr_title, historical_records)
    print(f"[RAG] Historical records loaded: {len(historical_records)}")
    print(f"[RAG] Similar records matched: {len(rag_context.get('top_records', []))}")
    for rec in rag_context.get("top_records", [])[:3]:
        print(f"  RAG {rec['similarity']:.4f} | PR {rec['pr_id']} | {rec['pr_title']}")

    print("[ML] Training scikit-learn ranker and scoring tests...")
    ml_scores = ml_rank(changed_files, available_tests, test_contents, rag_context)
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

    direct_match_tests = {
        t for t, v in ml_scores.items()
        if (
            v["features"].get("stem_exact", 0.0) > 0
            or v["features"].get("page_hint", 0.0) > 0
            or v["features"].get("test_file_changed", 0.0) > 0
            or v["features"].get("token_overlap", 0.0) >= 0.5
        )
    }
    if direct_match_tests:
        narrowed = [c for c in candidates if c["test"] in direct_match_tests]
        if narrowed:
            candidates = narrowed
            print(f"[ML] Direct-match narrowing applied: {sorted(direct_match_tests)}")

    if not candidates:
        default = "tests/pom-smoke.spec.js" if "tests/pom-smoke.spec.js" in available_tests else available_tests[0]
        candidates = [{"test": default, "score": 0.1, "features": {}}]

    # Bound LLM scope to top-N ML tests so it cannot expand to entire suite.
    candidates = candidates[:MAX_LLM_CANDIDATES]
    rag_evidence = build_rag_evidence_lines([c["test"] for c in candidates], rag_context)

    # Layer 2 - LLM
    print(f"[LLM] Sending {len(candidates)} candidates to TinyLlama...")
    try:
        llm_tests = llm_validate(changed_files, pr_title, candidates, available_tests, rag_evidence)
        if llm_tests:
            print(f"[OK] LLM validated: {llm_tests}")
            # Keep ML order and only include LLM-confirmed tests.
            llm_confirmed = set(llm_tests)
            final = [c["test"] for c in candidates if c["test"] in llm_confirmed]
            if not final:
                final = [c["test"] for c in candidates]
            explanations = [
                {
                    "test": t,
                    "priority_score": ml_scores.get(t, {}).get("score", 0.5),
                    "evidence": (
                        f"sklearn_score={ml_scores.get(t,{}).get('score',0):.3f}, "
                        f"rag_similarity={ml_scores.get(t,{}).get('features',{}).get('rag_similarity',0):.3f}"
                    ),
                    "reasoning": f"ML features: {ml_scores.get(t, {}).get('features', {})} | Confirmed by LLM"
                }
                for t in final
            ]
            final = list(dict.fromkeys(final))
            return final, "sklearn+rag+llm", explanations
    except Exception as e:
        print(f"[WARN] LLM error: {e} - using ML results only")

    # ML-only result
    final = [c["test"] for c in candidates]
    final = list(dict.fromkeys(final))
    mode = "sklearn+rag"
    explanations = [
        {
            "test": c["test"],
            "priority_score": c["score"],
            "evidence": (
                f"sklearn_score={c['score']:.3f}, "
                f"rag_similarity={c['features'].get('rag_similarity', 0):.3f}"
            ),
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
            self.wfile.write(json.dumps({"status": "ok", "model": MODEL, "pipeline": "scikit-learn+RAG+LLM"}).encode())
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
        print(f"[OK] Pipeline: scikit-learn ranking + historical RAG -> LLM (TinyLlama)")
        server.serve_forever()
    except OSError as e:
        print(f"[ERROR] Cannot bind to port {port}: {e}")
        sys.exit(1)
