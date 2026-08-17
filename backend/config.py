"""config.py — single source of truth for settings.

Credentials live in backend/credentials.json (see providers.py). This module
re-exports resolved values for import-time compat and live accessors for hot
paths. Legacy .env values are still honored as fallbacks via providers.py.
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

from llm_config import resolve_llm_config
from providers import (
    get_n8n_api_key as providers_get_n8n_api_key,
    get_n8n_base_url as providers_get_n8n_base_url,
    get_webhooks,
)

# Prefer backend/.env, then ./.env — legacy fallback, values are only used
# where credentials.json has nothing set.
for _candidate in (os.path.join(os.path.dirname(__file__), ".env"), ".env"):
    if os.path.exists(_candidate):
        load_dotenv(_candidate, override=False)
        break

# --- LLM ---
# Snapshot constants for import-time compat (empty strings are fine — the
# backend must boot even when the selected provider has no key yet).
LLM_PROVIDER, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL = resolve_llm_config()
# NOTE: no eager OpenAI() client here — building one with an empty key raises
# at import and bricks the whole backend. Use get_llm_client() (lazy) instead.

# --- n8n ---
N8N_BASE_URL = providers_get_n8n_base_url()
N8N_API_KEY = providers_get_n8n_api_key()
N8N_HEADERS = {"X-N8N-API-KEY": N8N_API_KEY, "Content-Type": "application/json"}

WEBHOOKS = get_webhooks()

# How long to wait for an n8n workflow execution (multi-step LLM chains are slow)
N8N_TIMEOUT = float(os.getenv("N8N_TIMEOUT", "180"))

# ---- live accessors -----------------------------------------------------------
# Settings written via the settings panel land in credentials.json + os.environ,
# so these re-resolve per call — no restart needed. Module-level constants above
# exist for import-time compat; new code should prefer these.


def get_llm_model() -> str:
    _, _, _, model = resolve_llm_config()
    return model


def get_llm_provider() -> str:
    provider, _, _, _ = resolve_llm_config()
    return provider


def get_llm_base_url() -> str:
    _, base_url, _, _ = resolve_llm_config()
    return base_url


def get_llm_api_key() -> str:
    _, _, api_key, _ = resolve_llm_config()
    return api_key


_llm_client_cache: dict = {}


def get_llm_client():
    """OpenAI client for the CURRENT provider, cached per (base_url, key)."""
    _, base_url, api_key, _ = resolve_llm_config()
    cache_key = (base_url, api_key)
    if cache_key not in _llm_client_cache:
        _llm_client_cache[cache_key] = OpenAI(api_key=api_key, base_url=base_url)
    return _llm_client_cache[cache_key]


def get_n8n_base_url() -> str:
    return providers_get_n8n_base_url()


def get_n8n_api_key() -> str:
    return providers_get_n8n_api_key()


REQUIRED_ENV = [
    ("N8N_BASE_URL", N8N_BASE_URL, "n8n base URL"),
    ("N8N_API_KEY", N8N_API_KEY, "n8n API key"),
    ("LLM_PROVIDER", LLM_PROVIDER, "LLM provider (groq|openrouter|custom)"),
    ("LLM_API_KEY", LLM_API_KEY, "LLM API key"),
    ("LLM_MODEL", LLM_MODEL, "default LLM model"),
]