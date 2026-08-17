"""
deploy.py — pushes all workflow JSONs + factory template to n8n via API.
Run: python scripts/deploy.py
Requires N8N_BASE_URL and N8N_API_KEY in backend/credentials.json (or .env).
Patches each LLM node with the configured provider (see backend/llm_config.py),
deploys workflows/ (activated) and templates/ (not activated), then writes
the live webhook URLs back into backend/credentials.json.
"""

import glob
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT / "backend"

sys.path.insert(0, str(BACKEND_DIR))
import providers  # noqa: E402
from llm_config import resolve_llm_config, patch_llm_node  # noqa: E402

N8N_BASE = providers.get_n8n_base_url()
N8N_KEY = providers.get_n8n_api_key()
HEADERS = {"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"}

WEBHOOK_ENV_MAP = {
    "research": "research",
    "summarizer": "summarizer",
    "extractor": "extractor",
}

WORKFLOWS_GLOB = str(BACKEND_DIR.parent / "workflows" / "*.json")
TEMPLATES_GLOB = str(BACKEND_DIR.parent / "templates" / "*.json")


def find_workflow_id(client: httpx.Client, name: str) -> str | None:
    resp = client.get(f"{N8N_BASE}/api/v1/workflows")
    if resp.status_code != 200:
        return None
    for wf in resp.json().get("data", []):
        if wf.get("name") == name:
            return wf["id"]
    return None


def deploy_file(
    client: httpx.Client,
    path: str,
    activate: bool,
    llm: tuple,
) -> tuple[str | None, str | None]:
    name = os.path.basename(path)
    with open(path, encoding="utf-8") as f:
        workflow = json.load(f)

    for node in workflow.get("nodes", []):
        patch_llm_node(node, *llm)

    webhook_path = None
    for node in workflow.get("nodes", []):
        if node.get("type") == "n8n-nodes-base.webhook":
            webhook_path = node.get("parameters", {}).get("path")

    wf_name = workflow.get("name", name)
    existing_id = find_workflow_id(client, wf_name)
    url = f"{N8N_BASE}/api/v1/workflows"
    if existing_id:
        resp = client.put(f"{url}/{existing_id}", json=workflow, headers=HEADERS)
    else:
        resp = client.post(url, json=workflow, headers=HEADERS)

    if resp.status_code not in (200, 201):
        print(f"  [FAIL] {name}: {resp.status_code} {resp.text[:200]}")
        return webhook_path, None

    wf_id = resp.json().get("id", existing_id)
    if activate and wf_id:
        client.post(f"{url}/{wf_id}/activate", headers=HEADERS)
        print(f"  [OK] {name} -> id={wf_id} (active)")
    else:
        print(f"  [OK] {name} -> id={wf_id} (inactive template)")
    return webhook_path, wf_id


def main() -> None:
    if not N8N_KEY:
        raise SystemExit("N8N_API_KEY is missing. Add it to backend/credentials.json.")

    provider, base_url, api_key, model = resolve_llm_config()
    print(f"LLM provider: {provider} | model: {model} | base: {base_url}")
    if api_key.startswith("your_"):
        print("  [WARN] LLM API key looks like a placeholder - calls will fail.")

    client = httpx.Client(timeout=30, headers=HEADERS)
    try:
        # Preflight n8n connectivity with a friendly failure
        try:
            client.get(f"{N8N_BASE}/api/v1/workflows")
        except httpx.ConnectError:
            raise SystemExit(
                f"\nCannot reach n8n at {N8N_BASE}.\n"
                "Is it running? Start it with `n8n start` (or docker), then re-run."
            )

        print("\nDeploying sub-agent workflows (workflows/)...")
        wired = {}
        for path in sorted(glob.glob(WORKFLOWS_GLOB)):
            webhook_path, _ = deploy_file(client, path, activate=True, llm=(base_url, api_key, model))
            if webhook_path and webhook_path in WEBHOOK_ENV_MAP:
                wired[webhook_path] = f"{N8N_BASE}/webhook/{webhook_path}"

        print("\nDeploying factory templates (templates/) - NOT activating...")
        for path in sorted(glob.glob(TEMPLATES_GLOB)):
            deploy_file(client, path, activate=False, llm=(base_url, api_key, model))

        for name, url in wired.items():
            providers.set_webhook(name, url)
            print(f"\n  [WIRED] {name}={url} -> backend/credentials.json")

        print(f"\nDone! Check n8n at {N8N_BASE}")
    finally:
        client.close()


if __name__ == "__main__":
    main()