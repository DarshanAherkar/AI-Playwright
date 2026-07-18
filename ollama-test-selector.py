#!/usr/bin/env python3
"""
Minimal Ollama-based Smart Test Selector
Lightweight FastAPI wrapper for test selection using Ollama LLM
"""

from fastapi import FastAPI
import httpx
import json

app = FastAPI()

OLLAMA_URL = "http://localhost:11434"
MODEL = "llama2"

TEST_MAPPING = {
    "login.page.js": "tests/login.spec.js",
    "signup.page.js": "tests/signup.spec.js",
    "about-us.page.js": "tests/about-us.spec.js",
    "contact-us.page.js": "tests/contact-us.spec.js",
    "base.page.js": "tests/pom-smoke.spec.js",
}


def get_ollama_suggestion(changed_files: list, pr_title: str) -> list:
    """Query Ollama for test suggestions."""
    try:
        prompt = f"""Given these changed files: {', '.join(changed_files)}
PR title: {pr_title}

Suggest which tests to run from: {', '.join(TEST_MAPPING.values())}
Reply with only test names, comma-separated."""
        
        response = httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": MODEL, "prompt": prompt, "stream": False},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json().get("response", "").strip()
            tests = [t.strip() for t in result.split(",") if t.strip() and "tests/" in t]
            return tests if tests else ["tests/pom-smoke.spec.js"]
    except Exception as e:
        print(f"Ollama error: {e}")
    
    return ["tests/pom-smoke.spec.js"]


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/v1/select-tests")
async def select_tests(request: dict):
    changed_files = request.get("changed_files", [])
    pr_title = request.get("pr_title", "")
    
    # Try Ollama first
    selected = get_ollama_suggestion(changed_files, pr_title)
    
    # Fallback to mapping if Ollama fails
    if not selected:
        selected = set()
        for file in changed_files:
            for key, test in TEST_MAPPING.items():
                if key in file:
                    selected.add(test)
        
        if not selected:
            selected = {"tests/pom-smoke.spec.js"}
        
        selected = sorted(list(selected))
    
    return {
        "status": "success",
        "selected_tests": selected,
        "explanations": [{"test": t, "priority_score": 0.8} for t in selected]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
