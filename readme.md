# Orbit — AI Meta-Agent Factory

FastAPI backend that classifies chat tasks (research / summarize / extract / novel) and routes them to n8n sub-agent webhooks, spawning new agents from templates for novel tasks.

> **New to the project? Read [`SETUP.md`](SETUP.md) first** — full first-time configuration walkthrough (n8n, credentials, providers, troubleshooting).

## Quickstart (one command)

```bash
python scripts/start.py     # or double-click start.bat
```

Starts whatever is missing (n8n → backend → deploys workflows → UI server), skips anything already running, and opens the browser. Stop everything with Ctrl+C.

## Structure

- `backend/` — FastAPI server (`main.py` → `routes.py` + modules)
- `workflows/` — n8n workflow exports
- `templates/` — agent template JSONs for the factory
- `ui/` — frontend
- `scripts/` — start / setup / deploy scripts
- `SPECS.md` — architecture + SSE event protocol docs

## Manual start (if you prefer)

```bash
n8n start                  # 1. n8n (port 5678)
python scripts/deploy.py   # 2. push workflows, wires webhooks into .env (once)
cd backend && uvicorn main:app --reload --port 8000   # 3. backend
python -m http.server 8080 --directory ui             # 4. UI → http://localhost:8080
```

## n8n fallback (if the n8n teammate is stuck)

A complete, ready-to-deploy n8n setup lives in `workflows/` and `templates/`:

1. Start n8n: `n8n start` (needs Node.js)
2. Put `N8N_API_KEY` (n8n → Settings → API) and an LLM key in `backend/.env`
3. Deploy everything (creates + activates the sub-agents, leaves the factory template inactive):

```bash
python scripts/deploy.py
```

`deploy.py` also writes the live webhook URLs back into `backend/.env` automatically.

Switch LLM providers in `backend/.env` anytime (`LLM_PROVIDER=groq|openrouter`, or `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL` for any other OpenAI-compatible API) and re-run `deploy.py`.

See `TASK_NISHCHAL_Backend_GitHub.md` for the full task breakdown.