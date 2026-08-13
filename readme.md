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

See `TASK_NISHCHAL_Backend_GitHub.md` for the full task breakdown.