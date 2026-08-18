import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Legacy .env support: keep reading backend/.env so old setups still work,
# but credentials.json (via providers.py) is the primary source of truth.
for candidate in (Path(__file__).parent / ".env", Path.cwd() / ".env"):
    if candidate.exists():
        load_dotenv(candidate, override=False)
        break

import providers  # noqa: E402
from providers import get_catalog  # noqa: E402


def resolve_llm_config() -> tuple[str, str, str, str]:
    """Live-resolve the active LLM provider from the JSON store + catalog.
    Returns (provider, base_url, api_key, model)."""
    provider = providers.get_active_provider().lower() or ""
    catalog = get_catalog()

    if not provider:
        # Legacy inference: pick the provider whose key is present
        if providers.get_setting("GROQ_API_KEY"):
            provider = "groq"
        elif providers.get_setting("OPENROUTER_API_KEY"):
            provider = "openrouter"

    info = catalog.get(provider)
    if info:
        base_url = info["base_url"]
        api_key = info.get("api_key", "") or providers.get_setting(
            info.get("key_env", ""), ""
        )
        model = providers.get_setting("LLM_MODEL", "") or info.get("default_model", "") or ""
        return provider, base_url, api_key, model

    # Fallback: custom provider via explicit env vars
    base_url = (providers.get_setting("LLM_BASE_URL", "") or "").rstrip("/") or catalog.get(
        "openrouter", {}
    ).get("base_url", "https://openrouter.ai/api/v1")
    api_key = providers.get_setting("LLM_API_KEY", "") or providers.get_setting(
        "OPENROUTER_API_KEY", ""
    )
    model = providers.get_setting("LLM_MODEL", "") or "openai/gpt-4o-mini"
    return provider or "custom", base_url, api_key, model


def patch_llm_node(node, base_url, api_key, model):
    """Patch LLM credential placeholders in an HTTP Request node.
    Handles both old (typeVersion 2) and new (typeVersion 4+) formats."""
    if node.get("type") != "n8n-nodes-base.httpRequest":
        return

    params = node.setdefault("parameters", {})

    # Patch URL
    if params.get("url") == "REPLACE_LLM_URL":
        params["url"] = f"{base_url.rstrip('/')}/chat/completions"

    # Old format (typeVersion 2): string-based fields
    for field in ("headerParametersJson", "bodyParametersJson"):
        if field in params and isinstance(params[field], str):
            params[field] = params[field].replace("REPLACE_LLM_KEY", api_key)
            params[field] = params[field].replace("REPLACE_LLM_MODEL", model)

    # New format (typeVersion 4+): structured fields
    header_params = params.get("headerParameters", {})
    if isinstance(header_params, dict):
        for p in header_params.get("parameters", []):
            if isinstance(p, dict) and isinstance(p.get("value"), str):
                p["value"] = p["value"].replace("REPLACE_LLM_KEY", api_key)

    json_body = params.get("jsonBody")
    if isinstance(json_body, str):
        params["jsonBody"] = json_body.replace("REPLACE_LLM_MODEL", model)
        params["jsonBody"] = params["jsonBody"].replace("REPLACE_LLM_KEY", api_key)

    # Normalize old requestMethod to method
    if "requestMethod" in params and "method" not in params:
        params["method"] = params.pop("requestMethod")


async def fetch_models(base_url: str, api_key: str) -> list[str]:
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()
        return [m["id"] for m in resp.json().get("data", [])]