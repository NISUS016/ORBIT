"""
setup.py — preflight for teammates running Orbit on a new machine.

Checks:
  1. Python deps import cleanly.
  2. .env exists (copies .env.example if missing, without secrets).
  3. Which of the required vars (n8n base/key, LLM provider/key/model) are set.
  4. Backend is reachable (/health) and n8n is reachable (/api/v1/workflows).

Run from anywhere: python scripts/setup.py
"""

import os
import shutil
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"

sys.path.insert(0, str(BACKEND_DIR))

OK, WARN, FAIL = "[OK]  ", "[WARN]", "[FAIL]"


def check_env() -> Path:
    creds = BACKEND_DIR / "credentials.json"
    if creds.exists():
        print(f"{OK} credentials.json found at {creds}")
        return creds
    example = ROOT / "credentials.example.json"
    if example.exists():
        shutil.copy(example, creds)
        print(f"{WARN} no credentials.json — copied credentials.example.json to {creds}")
        print(f"      fill in your keys at: {creds}")
    else:
        print(f"{FAIL} no credentials.json and no credentials.example.json found")
    return creds


def check_keys(creds: Path) -> None:
    data = {}
    if creds.exists():
        try:
            import json

            data = json.loads(creds.read_text(encoding="utf-8"))
        except Exception:
            pass

    providers_map = data.get("providers", {})
    n8n = data.get("n8n", {})
    active = (data.get("active_provider") or "").lower() or "groq"

    def ok(key: str, label: str) -> bool:
        val = (key or "").strip()
        if not val or "your_" in val:
            print(f"{FAIL} missing/invalid {label}")
            return False
        print(f"{OK} {label} set")
        return True

    ok(n8n.get("base_url"), "N8N_BASE_URL (n8n base URL)")
    ok(n8n.get("api_key"), "N8N_API_KEY (n8n API key)")

    info = providers_map.get(active, {})
    key = info.get("api_key", "")
    print(f"{OK} active provider: {active}")
    ok(key, f"LLM API key (provider: {active})")

    if not info.get("default_model"):
        print(f"{WARN} default_model unset for {active} - using provider default (fine)")


def check_services() -> None:
    import config

    try:
        r = httpx.get(f"http://127.0.0.1:8000/health", timeout=5)
        ok = r.status_code == 200 and r.json().get("status") == "ok"
        print(f"{OK if ok else FAIL} backend /health on :8000" if ok else
              f"{FAIL} backend not running — start it: cd backend && uvicorn main:app --port 8000")
    except Exception:
        print(f"{FAIL} backend not running — start it: cd backend && uvicorn main:app --port 8000")

    try:
        r = httpx.get(f"{config.N8N_BASE_URL}/api/v1/workflows",
                      headers=config.N8N_HEADERS, timeout=5)
        print(f"{OK if r.status_code == 200 else FAIL} n8n API at {config.N8N_BASE_URL} (HTTP {r.status_code})")
        if r.status_code == 401:
            print("      n8n API key rejected — check n8n.api_key in backend/credentials.json")
    except Exception:
        print(f"{FAIL} n8n unreachable at {config.N8N_BASE_URL} - is it running? `n8n start`")


def check_deps() -> None:
    failures = []
    for mod in ("fastapi", "uvicorn", "httpx", "dotenv", "openai"):
        try:
            __import__(mod)
        except ImportError:
            failures.append(mod)
    if failures:
        print(f"{FAIL} missing deps: {', '.join(failures)} — run: cd backend && pip install -r requirements.txt")
    else:
        print(f"{OK} python deps present")


def main() -> None:
    print("Orbit preflight\n---------------")
    check_deps()
    env = check_env()
    check_keys(env)
    check_services()
    print("\nDone. If anything failed above, fix it and re-run.")
    print("Deploy sub-agents once n8n is up: python scripts/deploy.py")


if __name__ == "__main__":
    main()