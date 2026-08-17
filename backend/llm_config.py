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
    if node.get("type") != "n8n-nodes-base.httpRequest":
        return
    params = node.setdefault("parameters", {})
    params["url"] = f"{base_url}/chat/completions"
    for field in ("bodyParametersJson", "jsonBody"):
        if field in params:
            params[field] = params[field].replace("REPLACE_LLM_MODEL", model)
    if "headerParametersJson" in params:
        params["headerParametersJson"] = params["headerParametersJson"].replace(
            "Bearer REPLACE_LLM_KEY", f"Bearer {api_key}"
        )
    for header in params.get("headerParameters", {}).get("parameters", []):
        if header.get("name") == "Authorization":
            header["value"] = f"Bearer {api_key}"


async def fetch_models(base_url: str, api_key: str) -> list[str]:
    async with httpx.AsyncClient(timeout=15) as http:
        resp = await http.get(
            f"{base_url}/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()
        return [m["id"] for m in resp.json().get("data", [])]