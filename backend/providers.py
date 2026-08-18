"""providers.py — AI provider catalog + live settings helper.

A SINGLE JSON file (backend/credentials.json) holds every credential:
  - provider catalog (name/base_url/default_model/optional api_key)
  - n8n settings (base_url, api_key, webhook URLs)
  - active provider selection
  - any stray env-style settings (in the "env" section)

Built-in presets (groq, openrouter) are seeded from code as defaults; anything
stored in the JSON wins (so the UI can rebind a built-in's key/base_url/model).
API-key values are only ever written to disk; get_all() never leaks them.
"""

import json
import os
import re
import shutil
from pathlib import Path

BACKEND_DIR = Path(__file__).parent
CREDENTIALS_FILE = BACKEND_DIR / "credentials.json"

BUILTIN_PROVIDERS = {
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "key_env": "GROQ_API_KEY",
        "default_model": "llama-3.3-70b-versatile",
        "builtin": True,
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "key_env": "OPENROUTER_API_KEY",
        "default_model": "openai/gpt-4o-mini",
        "builtin": True,
    },
}

DEFAULT_WEBHOOKS = {"research": "", "summarizer": "", "extractor": ""}
DEFAULT_N8N = {"base_url": "http://localhost:5678", "api_key": "", "webhooks": {}}

LEGACY_ENV_KEYS = {
    "N8N_BASE_URL": ("n8n", "base_url"),
    "N8N_API_KEY": ("n8n", "api_key"),
    "N8N_RESEARCH_WEBHOOK": ("n8n", "webhooks", "research"),
    "N8N_SUMMARIZER_WEBHOOK": ("n8n", "webhooks", "summarizer"),
    "N8N_EXTRACTOR_WEBHOOK": ("n8n", "webhooks", "extractor"),
    "LLM_PROVIDER": ("active_provider",),
}


# ---- JSON store -------------------------------------------------------------


def _load() -> dict:
    """Load the JSON store, merging built-in provider defaults underneath."""
    data = {"providers": {}, "n8n": dict(DEFAULT_N8N), "env": {}}
    data["n8n"]["webhooks"] = dict(DEFAULT_WEBHOOKS)
    data["active_provider"] = ""
    for pid, info in BUILTIN_PROVIDERS.items():
        data["providers"][pid] = {k: v for k, v in info.items() if k != "key_env"}
        data["providers"][pid]["api_key"] = ""
    if CREDENTIALS_FILE.exists():
        try:
            stored = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                if isinstance(stored.get("providers"), dict):
                    for pid, entry in stored["providers"].items():
                        if isinstance(entry, dict):
                            data["providers"][pid] = entry
                if isinstance(stored.get("n8n"), dict):
                    n8n = stored["n8n"]
                    data["n8n"]["base_url"] = n8n.get("base_url", data["n8n"]["base_url"])
                    data["n8n"]["api_key"] = n8n.get("api_key", "")
                    if isinstance(n8n.get("webhooks"), dict):
                        data["n8n"]["webhooks"] = n8n["webhooks"]
                if isinstance(stored.get("env"), dict):
                    data["env"] = stored["env"]
                if "active_provider" in stored:
                    data["active_provider"] = stored["active_provider"]
        except FileNotFoundError:
            pass  # File doesn't exist yet, use defaults
        except Exception as e:
            print(f"[providers] WARNING: Failed to read {CREDENTIALS_FILE}: {e}")
            # If the file exists and has content, don't silently discard it
            if CREDENTIALS_FILE.exists() and CREDENTIALS_FILE.stat().st_size > 0:
                raise  # Re-raise — don't overwrite valid data with empty defaults
    return data


def _save(data: dict) -> None:
    out = {
        "active_provider": data.get("active_provider", ""),
        "providers": data.get("providers", {}),
        "n8n": {
            "base_url": data.get("n8n", {}).get("base_url", DEFAULT_N8N["base_url"]),
            "api_key": data.get("n8n", {}).get("api_key", ""),
            "webhooks": data.get("n8n", {}).get("webhooks", {}),
        },
        "env": data.get("env", {}),
    }
    # Backup existing file before overwriting
    if CREDENTIALS_FILE.exists() and CREDENTIALS_FILE.stat().st_size > 0:
        shutil.copy2(CREDENTIALS_FILE, CREDENTIALS_FILE.with_suffix(".json.bak"))

    # Atomic write: write to temp file, then rename
    tmp_file = CREDENTIALS_FILE.with_suffix(".json.tmp")
    tmp_file.write_text(json.dumps(out, indent=2), encoding="utf-8")
    os.replace(str(tmp_file), str(CREDENTIALS_FILE))


def set_setting(key: str, value: str) -> None:
    """Persist to credentials.json AND the live process environment."""
    data = _load()
    if key in LEGACY_ENV_KEYS:
        target = data
        for part in LEGACY_ENV_KEYS[key][:-1]:
            target = target.setdefault(part, {})
        target[LEGACY_ENV_KEYS[key][-1]] = value
    else:
        data.setdefault("env", {})[key] = value
    _save(data)
    os.environ[key] = value


def set_webhook(name: str, url: str) -> None:
    """Persist one webhook URL (research|summarizer|extractor)."""
    data = _load()
    data.setdefault("n8n", {}).setdefault("webhooks", {})[name] = url
    _save(data)
    env_key = f"N8N_{name.upper()}_WEBHOOK"
    os.environ[env_key] = url


def clear_setting(key: str) -> None:
    """Remove from credentials.json and the live process environment."""
    data = _load()
    if key in LEGACY_ENV_KEYS:
        target = data
        last = LEGACY_ENV_KEYS[key][-1]
        for part in LEGACY_ENV_KEYS[key][:-1]:
            target = target.get(part, {})
        target[last] = ""
    else:
        data.setdefault("env", {}).pop(key, None)
    _save(data)
    os.environ.pop(key, None)


def get_setting(key: str, default: str = "") -> str:
    """Read a legacy env-style key from the JSON store (with env fallback)."""
    data = _load()
    if key in LEGACY_ENV_KEYS:
        target = data
        for part in LEGACY_ENV_KEYS[key]:
            target = target.get(part) if isinstance(target, dict) else None
            if target is None:
                break
        if isinstance(target, str):
            return target
    return os.getenv(key, data.get("env", {}).get(key, default))


def get_webhooks() -> dict:
    return dict(_load().get("n8n", {}).get("webhooks", {}))


# ---- catalog -----------------------------------------------------------------


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug or "provider"


def get_catalog() -> dict:
    """id -> {name, base_url, key_env, default_model, builtin, api_key} (merged)."""
    data = _load()
    catalog = {}
    for pid, info in BUILTIN_PROVIDERS.items():
        catalog[pid] = dict(info)
        catalog[pid]["api_key"] = ""
        stored = data["providers"].get(pid)
        if stored:
            for k in ("name", "base_url", "default_model", "api_key", "builtin"):
                if stored.get(k):
                    catalog[pid][k] = stored[k]
        if info.get("key_env") and os.getenv(info["key_env"]) and not catalog[pid]["api_key"]:
            catalog[pid]["api_key"] = os.getenv(info["key_env"], "")
    for pid, entry in data["providers"].items():
        if pid not in catalog:
            catalog[pid] = dict(entry)
            catalog[pid]["builtin"] = bool(entry.get("builtin", False))
    return catalog


def get_all() -> list[dict]:
    out = []
    for pid, info in get_catalog().items():
        out.append({
            "id": pid,
            "name": info.get("name", pid),
            "base_url": info.get("base_url", ""),
            "key_env": info.get("key_env", "") or f"{pid.upper()}_API_KEY",
            "default_model": info.get("default_model", ""),
            "builtin": bool(info.get("builtin")),
            "has_key": bool(info.get("api_key")),
        })
    return out


def add_provider(name: str, base_url: str, api_key: str = "", default_model: str = "") -> dict:
    pid = slugify(name)
    if pid in BUILTIN_PROVIDERS:
        raise ValueError(f"'{name}' collides with a built-in provider")
    data = _load()
    key_env = f"{pid.upper()}_API_KEY"
    data["providers"][pid] = {
        "name": name.strip(),
        "base_url": base_url.strip().rstrip("/"),
        "key_env": key_env,
        "default_model": default_model.strip(),
        "api_key": api_key.strip(),
        "builtin": False,
    }
    _save(data)
    if api_key:
        os.environ[key_env] = api_key.strip()
    return next(p for p in get_all() if p["id"] == pid)


def update_provider(
    pid: str,
    base_url: str | None = None,
    default_model: str | None = None,
    api_key: str = "",
) -> dict:
    """Update a user provider, or a built-in preset (key + overrides are
    persisted to credentials.json; the preset's base_url etc. act as
    defaults until overridden)."""
    data = _load()
    if pid not in data["providers"]:
        builtin = BUILTIN_PROVIDERS.get(pid)
        if not builtin:
            raise KeyError(pid)
        entry = dict(builtin)
        entry["api_key"] = os.getenv(builtin["key_env"], "")
        entry.pop("key_env", None)
        data["providers"][pid] = entry
    entry = data["providers"][pid]
    if base_url:
        entry["base_url"] = base_url.strip().rstrip("/")
    if default_model is not None:
        entry["default_model"] = default_model.strip()
    if api_key:
        entry["api_key"] = api_key.strip()
        os.environ[entry.get("key_env") or f"{pid.upper()}_API_KEY"] = api_key.strip()
    _save(data)
    return next(p for p in get_all() if p["id"] == pid)


def delete_provider(pid: str) -> None:
    data = _load()
    if pid not in data["providers"]:
        raise KeyError(pid)
    entry = data["providers"].pop(pid)
    _save(data)
    key_env = entry.get("key_env") or f"{pid.upper()}_API_KEY"
    os.environ.pop(key_env, None)
    if data.get("active_provider") == pid:
        set_setting("LLM_PROVIDER", next(iter(BUILTIN_PROVIDERS)))


def get_active_provider() -> str:
    return get_setting("LLM_PROVIDER", "groq") or next(iter(BUILTIN_PROVIDERS))


def set_active_provider(pid: str) -> None:
    set_setting("LLM_PROVIDER", pid)


# ---- n8n helpers -------------------------------------------------------------


def get_n8n_base_url() -> str:
    return get_setting("N8N_BASE_URL", DEFAULT_N8N["base_url"]).rstrip("/")


def get_n8n_api_key() -> str:
    return get_setting("N8N_API_KEY", "")