import os

import httpx
from dotenv import load_dotenv

for candidate in ("backend/.env", ".env"):
    if os.path.exists(candidate):
        load_dotenv(candidate, override=True)
        break

BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
}

DEFAULT_MODELS = {
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "openai/gpt-4o-mini",
}

KEY_ENVS = {
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def resolve_llm_config():
    provider = (os.getenv("LLM_PROVIDER") or "").lower()
    if not provider:
        if os.getenv("GROQ_API_KEY"):
            provider = "groq"
        elif os.getenv("OPENROUTER_API_KEY"):
            provider = "openrouter"
    if provider in BASE_URLS:
        base_url = BASE_URLS[provider]
        api_key = os.getenv(KEY_ENVS[provider], "")
        model = os.getenv("LLM_MODEL") or DEFAULT_MODELS[provider]
    else:
        base_url = os.getenv("LLM_BASE_URL", "") or BASE_URLS["openrouter"]
        api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY", "")
        model = os.getenv("LLM_MODEL") or DEFAULT_MODELS["openrouter"]
    return provider, base_url, api_key, model


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
