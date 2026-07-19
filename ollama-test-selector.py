#!/usr/bin/env python3
"""
Smart Test Selector: scikit-learn + RAG + LLM Pipeline

Layer 1 - ML (Ranking):
    scikit-learn Logistic Regression
    Features: code relevance, ownership overlap, business risk, and RAG signals

Layer 2 - RAG (Historical Retrieval):
    Retrieves similar historical PRs via TF-IDF cosine similarity
    Adds historical selection/failure evidence per test

Layer 3 - LLM (Reasoning):
    TinyLlama validates top ML candidates and explains selection
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
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
THRESHOLD = 0.15
RELATIVE_CUTOFF = 0.50
MAX_LLM_CANDIDATES = 3
RAG_TOP_K = 5

STOPWORDS = {
    "test", "expect", "page", "describe", "async", "await", "const", "let",
    "return", "from", "import", "require", "tobe", "tobevisible", "tohaveurl",
    "goto", "click", "fill", "locator", "getbytext", "getbyrole",
    "beforeeach", "aftereach", "browser", "context", "true", "false",
    "js", "spec", "tests", "src", "pages"
}

PRIORITY_TO_RISK = {
    "P0": 1.0,
    "P1": 0.8,
    "P2": 0.5,
    "P3": 0.3,
}


def tokenize(text):
    tokens = re.findall(r"[a-z][a-z0-9_-]+", text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]


def discover_tests(workspace):
    tests_dir = os.path.join(workspace, "tests")
    if not os.path.isdir(tests_dir):
        return ["tests/pom-smoke.spec.js"]
    return sorted(f"tests/{f}" for f in os.listdir(tests_dir) if f.endswith(".spec.js"))


def normalize_test_name(test_name):
    if not test_name:
        return None
    value = str(test_name).strip()
    if not value:
        return None
    if value.startswith("tests/"):
        return value
    if value.endswith(".spec.js"):
        return f"tests/{value}"
    return None


def load_historical_records(workspace):
    records = []

    history_path = os.path.join(workspace, "historical-pr-data.json")
    if os.path.isfile(history_path):
        try:
            with open(history_path, encoding="utf-8") as handle:
                payload = json.load(handle)
            records.extend(payload.get("records", []))
        except Exception as exc:
            print(f"[WARN] Could not load historical-pr-data.json: {exc}")

    metadata_path = os.path.join(workspace, "test-metadata.json")
    if os.path.isfile(metadata_path):
        try:
            with open(metadata_path, encoding="utf-8") as handle:
                payload = json.load(handle)
            records.extend(payload.get("historical_pr_runs", []))
        except Exception as exc:
            print(f"[WARN] Could not load historical_pr_runs from test-metadata.json: {exc}")

    cleaned = []
    for record in records:
        selected = [normalize_test_name(t) for t in record.get("selected_tests", [])]
        failed = [normalize_test_name(t) for t in record.get("failed_tests", [])]
        cleaned.append(
            {
                "pr_id": record.get("pr_id", "n/a"),
                "pr_title": record.get("pr_title", ""),
                "summary": record.get("summary", ""),
                "changed_files": record.get("changed_files", []),
                "selected_tests": [t for t in selected if t],
                "failed_tests": [t for t in failed if t],
                "tags": record.get("tags", []),
            }
        )
    return cleaned


def load_business_context(workspace, tests):
    context = {
        "test_module": {},
        "module_risk": {},
        "test_risk": {},
        "file_owners": {},
        "module_owners": {},
    }

    metadata_path = os.path.join(workspace, "test-metadata.json")
    if os.path.isfile(metadata_path):
        try:
            with open(metadata_path, encoding="utf-8") as handle:
                payload = json.load(handle)
            catalog = payload.get("test_catalog", {})
            for key, value in catalog.items():
                test_name = normalize_test_name(key)
                if test_name and test_name in tests:
                    module = value.get("module", "unknown")
                    context["test_module"][test_name] = module
                    priority = value.get("priority", "P2")
                    fail_rate = float(value.get("historical_failure_rate", 0.0))
                    priority_risk = PRIORITY_TO_RISK.get(priority, 0.5)
                    context["test_risk"][test_name] = round(min(1.0, max(priority_risk, fail_rate * 10)), 4)
                    context["module_risk"].setdefault(module, context["test_risk"][test_name])
        except Exception as exc:
            print(f"[WARN] Could not load business context from test-metadata.json: {exc}")

    business_path = os.path.join(workspace, "business-context.json")
    if os.path.isfile(business_path):
        try:
            with open(business_path, encoding="utf-8") as handle:
                payload = json.load(handle)
            context["file_owners"].update(payload.get("file_owners", {}))
            context["module_owners"].update(payload.get("module_owners", {}))
            for module, risk in payload.get("module_risk", {}).items():
                context["module_risk"][module] = float(risk)
        except Exception as exc:
            print(f"[WARN] Could not load business-context.json: {exc}")

    for test in tests:
        context["test_module"].setdefault(test, infer_test_module(test))
        module = context["test_module"][test]
        context["module_risk"].setdefault(module, 0.5)
        context["test_risk"].setdefault(test, context["module_risk"][module])

    return context


def infer_test_module(test_name):
    stem = re.sub(r"tests/|\.spec\.js", "", test_name)
    if stem in {"login", "signup", "pom-smoke"}:
        return "auth"
    if stem in {"about-us", "contact-us"}:
        return "content"
    return "core"


def infer_owners_for_file(file_path, business_context):
    owners = set()
    normalized = file_path.replace("\\", "/")

    for prefix, mapped_owners in business_context.get("file_owners", {}).items():
        if normalized.startswith(prefix):
            owners.update(mapped_owners)

    if normalized.startswith("src/pages/login"):
        owners.add("team-auth")
    if normalized.startswith("src/pages/signup"):
        owners.add("team-auth")
    if normalized.startswith("src/pages/about") or normalized.startswith("src/pages/contact"):
        owners.add("team-content")
    if normalized.startswith("mock-app/"):
        owners.add("team-ui")

    return owners


def get_test_owners(test_name, business_context):
    module = business_context["test_module"].get(test_name, "core")
    owners = set(business_context.get("module_owners", {}).get(module, []))
    if not owners:
        if module == "auth":
            owners = {"team-auth"}
        elif module == "content":
            owners = {"team-content"}
        else:
            owners = {"team-core"}
    return owners


def extract_meaningful_tokens(content, test_name):
    tokens = []
    tokens += re.findall(r"(?:describe|test)\([\"']([^\"']+)[\"']", content)
    tokens += re.findall(r"[\"']\./([\w-]+)\.page", content)
    tokens += [f"{a} {b}" for a, b in re.findall(r"(\w+Page)\.(\w+)", content)]
    stem = re.sub(r"tests/|\.spec\.js", "", test_name)
    tokens.append(stem)
    return " ".join(tokens)


def read_test_contents(workspace, tests):
    contents = {}
    for test in tests:
        path = os.path.join(workspace, test)
        try:
            with open(path, encoding="utf-8") as handle:
                raw = handle.read()
            contents[test] = extract_meaningful_tokens(raw, test)
        except Exception:
            contents[test] = re.sub(r"tests/|\.spec\.js", "", test)
    return contents


def record_to_text(record):
    return " ".join(
        [
            str(record.get("pr_title", "")),
            str(record.get("summary", "")),
            " ".join(record.get("changed_files", [])),
            " ".join(record.get("selected_tests", [])),
            " ".join(record.get("failed_tests", [])),
            " ".join(record.get("tags", [])),
        ]
    )


def retrieve_historical_context(changed_files, pr_title, historical_records):
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

    top_records = []
    test_signals = {}
    total_similarity = 0.0

    ranked_indices = sorted(range(len(similarities)), key=lambda i: similarities[i], reverse=True)
    for idx in ranked_indices[:RAG_TOP_K]:
        sim = float(similarities[idx])
        if sim <= 0:
            continue

        record = historical_records[idx]
        total_similarity += sim
        top_records.append(
            {
                "pr_id": record.get("pr_id", "n/a"),
                "pr_title": record.get("pr_title", ""),
                "similarity": round(sim, 4),
                "selected_tests": record.get("selected_tests", []),
                "failed_tests": record.get("failed_tests", []),
            }
        )

        for test in record.get("selected_tests", []):
            signal = test_signals.setdefault(
                test,
                {"selection_sum": 0.0, "failure_sum": 0.0, "max_similarity": 0.0, "hits": 0},
            )
            signal["selection_sum"] += sim
            signal["max_similarity"] = max(signal["max_similarity"], sim)
            signal["hits"] += 1

        for test in record.get("failed_tests", []):
            signal = test_signals.setdefault(
                test,
                {"selection_sum": 0.0, "failure_sum": 0.0, "max_similarity": 0.0, "hits": 0},
            )
            signal["failure_sum"] += sim
            signal["max_similarity"] = max(signal["max_similarity"], sim)
            signal["hits"] += 1

    return {"top_records": top_records, "test_signals": test_signals, "total_similarity": total_similarity}


def build_rag_evidence_lines(candidate_tests, rag_context):
    lines = []
    signals = rag_context.get("test_signals", {})
    total_similarity = rag_context.get("total_similarity", 0.0) or 1.0

    for test in candidate_tests:
        signal = signals.get(test, {})
        rag_select = signal.get("selection_sum", 0.0) / total_similarity
        rag_fail = signal.get("failure_sum", 0.0) / total_similarity
        rag_sim = signal.get("max_similarity", 0.0)
        lines.append(f"- {test}: hist_select={rag_select:.3f}, hist_fail={rag_fail:.3f}, best_sim={rag_sim:.3f}")

    if not lines:
        lines.append("- No historical matches")
    return lines


def build_features(changed_files, test, test_contents, rag_context, business_context):
    changed_text = " ".join(changed_files)
    changed_tokens = set(tokenize(changed_text))

    test_stem = re.sub(r"tests/|\.spec\.js", "", test)
    test_tokens = set(tokenize(test_stem))
    content_tokens = set(tokenize(test_contents.get(test, "")))

    union = test_tokens | changed_tokens
    token_overlap = len(test_tokens & changed_tokens) / len(union) if union else 0.0
    content_overlap = len(content_tokens & changed_tokens) / (len(changed_tokens) or 1)

    stem_exact_in_changed = 1.0 if test_stem.replace("-", "") in changed_text.replace("-", "") else 0.0
    test_file_changed = 1.0 if test in changed_files else 0.0
    page_hint = 1.0 if any(f"{test_stem}.page" in cf for cf in changed_files) else 0.0

    avg_depth = sum(f.count("/") for f in changed_files) / (len(changed_files) or 1)
    depth_norm = min(1.0, avg_depth / 5)
    changed_count_norm = min(1.0, len(changed_files) / 20)

    signal = rag_context.get("test_signals", {}).get(test, {})
    denom = rag_context.get("total_similarity", 0.0) or 1.0
    rag_selection = signal.get("selection_sum", 0.0) / denom
    rag_failure = signal.get("failure_sum", 0.0) / denom
    rag_similarity = signal.get("max_similarity", 0.0)

    changed_owners = set()
    for changed_file in changed_files:
        changed_owners.update(infer_owners_for_file(changed_file, business_context))
    test_owners = get_test_owners(test, business_context)
    owner_overlap = 1.0 if changed_owners and test_owners and (changed_owners & test_owners) else 0.0

    business_risk = float(business_context.get("test_risk", {}).get(test, 0.5))

    smoke_boost = 0.0
    if test.endswith("pom-smoke.spec.js"):
        broad_change = any(cf.startswith("mock-app/") or cf.startswith("src/pages/base") for cf in changed_files)
        smoke_boost = 1.0 if broad_change else 0.0

    vector = [
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
        owner_overlap,
        business_risk,
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
        "owner_overlap": round(owner_overlap, 4),
        "business_risk": round(business_risk, 4),
    }

    return vector, feature_map


def build_training_dataset(historical_records, tests, test_contents, business_context):
    x_train = []
    y_train = []

    empty_rag = {"test_signals": {}, "total_similarity": 0.0}
    for record in historical_records:
        changed_files = record.get("changed_files", [])
        failed = set(record.get("failed_tests", []))
        selected = set(record.get("selected_tests", []))

        for test in tests:
            vec, _ = build_features(changed_files, test, test_contents, empty_rag, business_context)
            # Positive labels prioritize real failures and selected risky tests.
            label = 1 if (test in failed or (test in selected and len(failed) > 0)) else 0
            x_train.append(vec)
            y_train.append(label)

    return x_train, y_train


def weak_label(changed_files, test, rag_context):
    changed_text = " ".join(changed_files).lower()
    stem = re.sub(r"tests/|\.spec\.js", "", test).lower()

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


def ml_rank(changed_files, tests, test_contents, rag_context, historical_records, business_context):
    x_current = []
    feature_maps = {}

    for test in tests:
        vec, fmap = build_features(changed_files, test, test_contents, rag_context, business_context)
        x_current.append(vec)
        feature_maps[test] = fmap

    x_train, y_train = build_training_dataset(historical_records, tests, test_contents, business_context)

    model = LogisticRegression(random_state=42, solver="liblinear")
    trained_on_history = False

    if len(set(y_train)) >= 2 and len(x_train) >= max(10, len(tests) * 2):
        model.fit(x_train, y_train)
        trained_on_history = True
    else:
        y_fallback = [weak_label(changed_files, test, rag_context) for test in tests]
        if len(set(y_fallback)) < 2:
            y_fallback = [1 if i == 0 else 0 for i in range(len(tests))]
        model.fit(x_current, y_fallback)

    probabilities = model.predict_proba(x_current)

    results = {}
    for i, test in enumerate(tests):
        model_score = float(probabilities[i][1])
        fmap = feature_maps[test]

        heuristic_score = (
            (fmap.get("token_overlap", 0.0) * 0.25)
            + (fmap.get("content_overlap", 0.0) * 0.10)
            + (fmap.get("stem_exact", 0.0) * 0.20)
            + (fmap.get("page_hint", 0.0) * 0.15)
            + (fmap.get("rag_selection", 0.0) * 0.10)
            + (fmap.get("rag_failure", 0.0) * 0.05)
            + (fmap.get("owner_overlap", 0.0) * 0.05)
            + (fmap.get("business_risk", 0.0) * 0.10)
        )

        score = (model_score * 0.65) + (heuristic_score * 0.35)
        results[test] = {
            "score": round(min(1.0, max(0.0, score)), 4),
            "model_score": round(model_score, 4),
            "trained_on_history": trained_on_history,
            "features": fmap,
        }

    return dict(sorted(results.items(), key=lambda x: x[1]["score"], reverse=True))


def llm_validate(changed_files, pr_title, candidates, available_tests, rag_evidence):
    changed_str = "\n".join(f"  - {f}" for f in changed_files)
    candidate_tests = [c["test"] for c in candidates]
    candidates_str = "\n".join(f"  - {t}" for t in candidate_tests)
    rag_evidence_str = "\n".join(rag_evidence)

    prompt = (
        "You are a precise test selection assistant. Be selective and practical.\n"
        f"Changed files:\n{changed_str}\n"
        f"PR title: {pr_title}\n\n"
        "Historical RAG evidence from similar PRs:\n"
        f"{rag_evidence_str}\n\n"
        "Only choose from this candidate list:\n"
        f"{candidates_str}\n\n"
        "Rules:\n"
        "- Only confirm tests directly related to changed files\n"
        "- Prefer direct-match tests over peripheral tests\n"
        "- You MUST choose only from candidate list\n"
        "Output only confirmed test filenames, one per line.\n"
    )

    payload = json.dumps({"model": MODEL, "prompt": prompt, "stream": False}).encode("utf-8")
    request = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=45) as response:
        raw = json.loads(response.read().decode("utf-8")).get("response", "")
        print(f"[LLM] Response: {raw[:300]}")
        found = re.findall(r"tests/[\w-]+\.spec\.js", raw)
        filtered = [t for t in found if t in candidate_tests and t in available_tests]
        return list(dict.fromkeys(filtered)) or None


def select_tests(changed_files, pr_title, workspace):
    available_tests = discover_tests(workspace)
    print(f"[INFO] Discovered tests: {available_tests}")

    if not changed_files:
        default = "tests/pom-smoke.spec.js" if "tests/pom-smoke.spec.js" in available_tests else available_tests[0]
        return [default], "default", [
            {
                "test": default,
                "priority_score": 0.5,
                "evidence": "No changed files provided",
                "reasoning": "Default smoke coverage",
            }
        ]

    test_contents = read_test_contents(workspace, available_tests)
    historical_records = load_historical_records(workspace)
    business_context = load_business_context(workspace, available_tests)

    rag_context = retrieve_historical_context(changed_files, pr_title, historical_records)
    print(f"[RAG] Historical records loaded: {len(historical_records)}")
    print(f"[RAG] Similar records matched: {len(rag_context.get('top_records', []))}")
    for record in rag_context.get("top_records", [])[:3]:
        print(f"  RAG {record['similarity']:.4f} | PR {record['pr_id']} | {record['pr_title']}")

    print("[ML] Training scikit-learn ranker and scoring tests...")
    ml_scores = ml_rank(changed_files, available_tests, test_contents, rag_context, historical_records, business_context)
    for test, value in list(ml_scores.items())[:5]:
        source = "history" if value.get("trained_on_history") else "weak-supervision"
        print(f"  ML  {value['score']:.4f} | {test} | source={source} | {value['features']}")

    best = max((v["score"] for v in ml_scores.values()), default=0)
    cutoff = max(THRESHOLD, best * RELATIVE_CUTOFF)
    print(f"[ML] Best score: {best:.4f} | Cutoff: {cutoff:.4f}")

    candidates = [
        {"test": t, "score": v["score"], "features": v["features"]}
        for t, v in ml_scores.items()
        if v["score"] >= cutoff
    ]

    direct_match_tests = {
        t
        for t, v in ml_scores.items()
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

    candidates = candidates[:MAX_LLM_CANDIDATES]
    rag_evidence = build_rag_evidence_lines([c["test"] for c in candidates], rag_context)

    print(f"[LLM] Sending {len(candidates)} candidates to TinyLlama...")
    try:
        llm_tests = llm_validate(changed_files, pr_title, candidates, available_tests, rag_evidence)
        if llm_tests:
            print(f"[OK] LLM validated: {llm_tests}")
            llm_confirmed = set(llm_tests)
            final = [c["test"] for c in candidates if c["test"] in llm_confirmed]
            if not final:
                final = [c["test"] for c in candidates]
            final = list(dict.fromkeys(final))

            explanations = []
            for test in final:
                feat = ml_scores.get(test, {}).get("features", {})
                score = ml_scores.get(test, {}).get("score", 0.0)
                explanations.append(
                    {
                        "test": test,
                        "priority_score": score,
                        "evidence": (
                            f"sklearn_score={score:.3f}, "
                            f"rag_similarity={feat.get('rag_similarity', 0):.3f}, "
                            f"owner_overlap={feat.get('owner_overlap', 0):.3f}, "
                            f"business_risk={feat.get('business_risk', 0):.3f}"
                        ),
                        "reasoning": f"ML features: {feat} | Confirmed by LLM",
                    }
                )
            return final, "sklearn+rag+llm", explanations
    except Exception as exc:
        print(f"[WARN] LLM error: {exc} - using ML results only")

    final = list(dict.fromkeys([c["test"] for c in candidates]))
    explanations = []
    for candidate in candidates:
        test = candidate["test"]
        feat = candidate.get("features", {})
        score = candidate.get("score", 0.0)
        explanations.append(
            {
                "test": test,
                "priority_score": score,
                "evidence": (
                    f"sklearn_score={score:.3f}, "
                    f"rag_similarity={feat.get('rag_similarity', 0):.3f}, "
                    f"owner_overlap={feat.get('owner_overlap', 0):.3f}, "
                    f"business_risk={feat.get('business_risk', 0):.3f}"
                ),
                "reasoning": str(feat),
            }
        )
    return final, "sklearn+rag", explanations


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps({"status": "ok", "model": MODEL, "pipeline": "scikit-learn+RAG+LLM"}).encode()
            )
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if self.path != "/api/v1/select-tests":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length).decode("utf-8"))

        changed_files = body.get("changed_files", [])
        pr_title = body.get("pr_title", "")
        workspace = body.get("workspace", os.getcwd())

        tests, mode, explanations = select_tests(changed_files, pr_title, workspace)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(
            json.dumps(
                {
                    "status": "success",
                    "selected_tests": tests,
                    "mode": mode,
                    "explanations": explanations,
                }
            ).encode()
        )

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    try:
        server = HTTPServer(("0.0.0.0", port), Handler)
        print(f"[OK] Smart Test Selector running on port {port}")
        print("[OK] Pipeline: scikit-learn (historical training) + RAG + LLM (TinyLlama)")
        server.serve_forever()
    except OSError as exc:
        print(f"[ERROR] Cannot bind to port {port}: {exc}")
        sys.exit(1)
