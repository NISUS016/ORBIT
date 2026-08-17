# Orbit — Specs: Modularity, Setup, and Streaming Artifacts

Version 1 — development-stage slice. Final Docker deployment is a separate,
later milestone.

## 1. Backend modularity

Split the 316-line `backend/main.py` monolith into focused modules.

| File | Responsibility |
|------|----------------|
| `backend/config.py` | Single source of env loading + resolved settings (`LLM_*`, `N8N_*`, `WEBHOOKS`, `LLM_CLIENT`) |
| `backend/llm_config.py` | (unchanged) provider resolution + node patching + model fetch |
| `backend/orchestrator.py` | `classify_task` + `design_agent`; loads `orchestrator_instructions.md` |
| `backend/workflow_builder.py` | `build_workflow(spec)` — assembles the n8n JSON + patch |
| `backend/n8n_client.py` | `N8NClient` (create/activate/call/find) + `call_webhook` |
| `backend/routes.py` | FastAPI `app`, endpoints `/chat` (SSE), `/models`, `/health` |
| `backend/main.py` | Thin entrypoint: `app` + `uvicorn` run |

Routing rule: modules never read env directly — only `config.py` does. Everything
else imports the resolved values from `config`.

## 2. Setup & portability (dev stage)

- **Path portability** — `scripts/deploy.py` resolves `workflows/`, `templates/`,
  and `backend/.env` from `Path(__file__)`, not CWD, so it runs from anywhere.
- **Preflight script** — `scripts/setup.py`:
  1. Checks python deps import cleanly.
  2. Validates `.env` exists (copies from `.env.example` if missing, stops short of secrets).
  3. Health-checks backend + n8n (`GET /health` and `/api/v1/workflows`) and reports which
      of the 4 required vars (`N8N_BASE_URL`, `N8N_API_KEY`, LLM key, provider) are missing.
- **Milestone (later)** — `docker-compose.yml` (backend + n8n + node). Not part of this slice.

## 3. Streaming artifacts (SSE)

`/chat` becomes a `text/event-stream` so the UI can render the workflow as it is built.

### Event protocol (named SSE events, `event:`/`data:` frames, data is JSON)

| event | payload | meaning |
|-------|---------|---------|
| `status` | `{stage}` | lifecycle hint (`classify`, `design`, `built`, `activated`, `run`) |
| `design` | `{name, summary, steps:[{title, system_prompt}]}` | agent design finished |
| `workflow` | `{nodes, connections}` | the assembled graph (renderable) — nodes carry `id/name/type/position` |
| `done` | `{response, agent_used, spawned, agent_summary, model}` | final answer |
| `error` | `{message}` | terminal failure |

- Known tasks (research/summarize/extractor): `status` → `done`.
- Novel tasks: `status(classify)` → `design` → `workflow` → `status(built/activated)` → `done`/`error`.

`workflow.nodes` is derived from the real n8n JSON (positions + types included), so the
artifact window can render the true node graph; it can graduate to Vue Flow in the polished UI.

## 4. Artifact window (current UI, placeholder for UI guy)

A small card in `ui/index.html` that appears during a novel task and is discarded on `done`:

- Header: agent `name` + summary.
- Node graph: the `workflow` nodes laid out as chips with connectors, revealed
  left→right with a stagger animation; the active/last node pulses while deploying.
- Footer: live `status` hint.
- Styling matches the existing dark Orbit theme; left intentionally simple for the
  UI guy to replace with the polished Vue Flow render.

## 5. Settings panel (live config)

Everything is writable at runtime — the backend re-resolves settings per request,
no restarts:

| Endpoint | Purpose |
|----------|---------|
| `GET /settings` | current provider/model, provider list, n8n config + connectivity |
| `PUT /settings/n8n` | save n8n base URL / API key |
| `GET /providers` | catalog (built-ins + user-added) |
| `POST /providers` | add a new OpenAI-compatible provider |
| `PUT /providers/{id}` | edit base URL / default model / API key |
| `DELETE /providers/{id}` | remove a user provider (resets active to groq if needed) |
| `POST /providers/select` | set the active provider (`LLM_PROVIDER`) |
| `POST /providers/test` | one-shot ping (by provider id, or explicit config) |

- Provider catalog: `backend/providers.json` (user-added only); built-ins
  (groq, openrouter) are code-defined. Secrets always live in `backend/.env`
  under per-provider vars (`GROQ_API_KEY`, `MYPROVIDER_API_KEY`, ...) — never in JSON.
- `providers.set_setting()` writes `.env` AND `os.environ`, so
  `config.get_llm_client()` / `get_n8n_*()` / `resolve_llm_config()` pick changes
  up on the next call. Hot-path modules use these accessors, not import-time constants.
- Workflow factory patches are made at spawn time, so new providers apply to
  spawned agents immediately (they carry their own URL/key/model).

## Acceptance
- `uvicorn main:app` starts, `/health` ok, `/models` ok.
- `/chat` streams SSE; novel task yields the full event sequence and a `done`.
- UI: artifact renders the node graph + animation, then the bot answer appears.
- `python scripts/deploy.py` runs from a directory other than repo root.
- `python scripts/setup.py` performs preflight and reports missing config.