# Orbit — First-Time Setup Manual

This document is for anyone setting up Orbit on a fresh machine. Follow it top to bottom and you'll have the full stack running in about 10 minutes.

## What is Orbit?

Orbit is an **AI meta-agent factory**: you chat with it in a web UI, and it builds & runs **n8n workflows on demand**.

- You type something like *"get feedback on WhatsApp and store it in Google Sheets"*.
- Orbit's backend classifies the task, designs a specialist agent (via an LLM), pushes a ready-made workflow into n8n, activates it, and runs it — showing you the result in the UI.
- Well-known task types (research / summarize / extract) are routed to pre-deployed sub-agent workflows instead.

```
UI (port 8080)  <->  FastAPI backend (port 8000)  <->  n8n (port 5678)
                                              \--->  LLM provider (Groq / OpenRouter / any OpenAI-compatible API)
```

## Prerequisites

| Tool | Why | Install |
|---|---|---|
| **Node.js 18+** | runs n8n | https://nodejs.org |
| **n8n** (global) | workflow automation engine | `npm install -g n8n` |
| **Python 3.10+** | runs backend + scripts | https://python.org |
| **Python deps** | FastAPI, uvicorn, httpx, openai | `pip install -r backend/requirements.txt` |
| **An LLM API key** | drives the agents | Groq (https://console.groq.com) and/or OpenRouter (https://openrouter.ai) |

> Python 3.14 is known to work. Anything 3.10+ should be fine.

## Step 1 — Install n8n and start it once

```bash
npm install -g n8n
n8n start        # opens http://localhost:5678
```

In n8n's UI: **Settings → n8n API** → generate an **API key** (create a user first if asked). Keep this key for Step 3.

Leave n8n running — `scripts/start.py` detects it and skips it later.

## Step 2 — Install Python deps

```bash
pip install -r backend/requirements.txt
```

## Step 3 — Configure credentials

Credentials live in ONE file: `backend/credentials.json` (secrets are never committed; only `credentials.example.json` is in git).

```bash
copy credentials.example.json backend\credentials.json   # Windows
# cp credentials.example.json backend/credentials.json   # macOS / Linux
```

Edit `backend/credentials.json`:

```jsonc
{
  "active_provider": "groq",                    // which provider is used by default
  "providers": {
    "groq": {
      "base_url": "https://api.groq.com/openai/v1",
      "default_model": "llama-3.3-70b-versatile",  // pick a model you actually have access to
      "api_key": "gsk_..."                          // <-- YOUR Groq key
    },
    "openrouter": {
      "base_url": "https://opencode.ai/zen/v1",     // or https://openrouter.ai/api/v1
      "default_model": "openai/gpt-4o-mini",
      "api_key": "sk-or-..."                        // <-- YOUR OpenRouter key
    }
  },
  "n8n": {
    "base_url": "http://localhost:5678",
    "api_key": "n8n_api_..."                        // <-- key from Step 1
  }
}
```

**No need to fill anything else** — webhook URLs are written automatically on first deploy.

> **Troubleshooting tip:** `llama-3.3-70b-versatile` no longer being available on Groq is the #1 cause of `model_not_found` errors. Open http://localhost:5678 → LLM provider docs, or just pick a model from the UI dropdown (see Step 5) instead.

## Step 4 — Start everything (one command)

```bash
python scripts/start.py        # or double-click start.bat
```

This starts whatever is missing in order and **opens the browser at http://localhost:8080**:

1. n8n (if not running)
2. backend on port 8000
3. deploys the sub-agent workflows and wires their webhook URLs (first run only)
4. UI static server on port 8080

Everything runs **detached** — you can close the console. Logs go to `logs/` (`backend.log`, `n8n.log`, `ui.log`).

Stop everything:

```bash
python scripts/stop.py
```

Sanity-check the whole setup:

```bash
python scripts/setup.py        # preflight: deps, credentials, backend + n8n reachability
```

## Step 5 — Use the UI

- **Chat tab** — type a task and hit Enter. Watch the pipeline stages (classify → design → build → activate → run) as SSE status events.
- **Model selector** (top bar) — pick the provider and model used for this request. This selection is also written into the workflows Orbit spawns, so pick a model you know works.
- **Workflows tab** — lists every workflow in n8n. Click a card to open it in the n8n editor. **Re-click the tab (or refresh) to see new ones** — the list only reloads when you open the view.
- **Settings tab** — manage everything without editing JSON:
  - n8n base URL + API key (leave key empty to keep the stored one)
  - AI providers: add / edit / delete, and **Use** to switch the active provider
  - **Test** button pings the provider with the model to verify credentials

## How the factory works (so it's not magic)

1. `POST /chat` → `orchestrator.classify_task()` decides if the request is a **known task** (research / summarize / extract) or **novel**.
2. **Known** → routed to the matching pre-deployed n8n sub-agent webhook.
3. **Novel** → `orchestrator.design_agent()` asks the LLM for a plan (`{name, summary, steps:[{title, system_prompt}]}`), `workflow_builder.build_workflow()` assembles an n8n workflow JSON (Webhook → LLM HTTP Request per step → Format Result), it's pushed to n8n, **activated**, and its webhook is called with the task text. The last LLM step's answer is streamed back as the chat reply.

## Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| `Error in workflow` in chat | Open the workflow in n8n → **Executions** tab → open the failed run to see the real error. Two common ones below. |
| `model_not_found` 404 inside a step | The model isn't available on that provider (e.g. `llama-3.3-70b-versatile` on Groq). Select a working model in the UI's model dropdown, or fix `default_model` in credentials.json. |
| `Rate limit reached…` 429 inside a step | Free tiers (Groq = 8000 tokens/min) throttle multi-step runs. Wait ~15s and resend — retries already back off 12s. Switch to OpenRouter or a paid tier for heavier use. |
| Port 8000 stuck / stale backend | `python scripts/stop.py`, then `taskkill /F /PID <pid from logs\backend.pid>`, then `python scripts/start.py`. |
| n8n API key rejected (401) | n8n → Settings → n8n API → regenerate; update `backend/credentials.json`. |
| Webhooks not wired | Delete `backend/.env`'s `N8N_*_WEBHOOK` lines and re-run `python scripts/deploy.py` (or just restart `start.py` — it auto-deploys when webhooks are missing). |

## Key files

- `backend/credentials.json` — **all secrets** (n8n key, LLM keys, active provider). Git-ignored.
- `backend/routes.py` — HTTP API + SSE chat stream
- `backend/orchestrator.py` — task classification + agent design
- `backend/workflow_builder.py` — n8n workflow JSON assembly
- `backend/n8n_client.py` — n8n REST API + webhook calls
- `scripts/start.py` / `stop.py` / `setup.py` / `deploy.py` / `uiserve.py` — lifecycle
- `SPECS.md` — architecture + SSE event protocol
