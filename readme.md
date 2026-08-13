# Orbit — AI Meta-Agent Factory

FastAPI backend that classifies chat tasks (research / summarize / extract / novel) and routes them to n8n sub-agent webhooks, spawning new agents from templates for novel tasks.

## Structure

- `backend/` — FastAPI server (`main.py`)
- `workflows/` — n8n workflow exports
- `templates/` — agent template JSONs for the factory
- `ui/` — frontend
- `scripts/` — deploy scripts

## Run backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
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