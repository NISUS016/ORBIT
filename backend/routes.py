"""routes.py — FastAPI app: /chat (SSE stream), /models, /health.

/chat streams build progress as named SSE events so the UI can render the
workflow artifact live (see SPECS.md §3 for the event protocol).
"""

import asyncio
import json
import os
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from openai import OpenAI
from pydantic import BaseModel

import config
import orchestrator
import providers
import workflow_builder
from llm_config import fetch_models, resolve_llm_config
from n8n_client import N8NClient, call_webhook

app = FastAPI()

# Allow UI (running on localhost:any port) to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    model: str | None = None


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def chat_stream(req: ChatRequest) -> AsyncGenerator[str, None]:
    """Async generator yielding SSE frames for a /chat request."""
    model = (req.model or config.get_llm_model()).strip() or config.get_llm_model()

    yield _sse("status", {"stage": "classify", "message": "Classifying task…"})
    task_type = await orchestrator.classify_task_async(req.message, model)

    webhooks = config.get_webhooks_live()
    if task_type in webhooks and webhooks[task_type]:
        # Known task — route to its sub-agent
        yield _sse("status", {"stage": "run", "agent": task_type})
        result, _status = await call_webhook(webhooks[task_type], req.message, model)
        yield _sse("done", {
            "response": result,
            "agent_used": task_type,
            "spawned": False,
            "agent_summary": "",
            "model": model,
        })
        return

    # Novel task — AGENTIC workflow generation
    yield _sse("status", {"stage": "design", "message": "Designing workflow with AI…"})
    workflow, gen_log = await orchestrator.design_workflow_async(req.message, model)

    yield _sse("design", {
        "name": workflow.get("name", "Generated Workflow"),
        "summary": workflow.get("summary", ""),
        "node_count": len(workflow.get("nodes", [])),
        "generation_log": gen_log,
    })

    # Patch credentials and finalize
    workflow_builder.patch_credentials(workflow, model)
    webhook_path = workflow_builder.ensure_unique_webhook(workflow)
    workflow["name"] = workflow_builder.name_for_task(
        workflow.get("name", "Agent"), req.message
    )
    yield _sse("workflow", workflow_builder.graph_summary(workflow))

    # Deploy to n8n
    yield _sse("status", {"stage": "built", "message": "Deploying workflow to n8n…"})
    client = N8NClient()
    created = await client.create_workflow(workflow)
    workflow_id = created.get("id")
    if not workflow_id:
        error_detail = created.get("error", created.get("message", "Unknown error"))
        yield _sse("error", {"message": f"Workflow creation failed: {error_detail}"})
        return

    await client.activate(workflow_id)
    yield _sse("status", {"stage": "activated", "message": "Workflow activated — running…"})

    webhook_url = client.webhook_url(created, webhook_path)
    # Wait for the webhook to be live, retrying activation races
    result, status_code = await client.call_spawned(req.message, model, webhook_url)

    yield _sse("done", {
        "response": result,
        "agent_used": workflow.get("name", "Generated Agent"),
        "spawned": True,
        "agent_summary": workflow.get("summary", ""),
        "model": model,
        "node_count": len(workflow.get("nodes", [])),
    })


@app.post("/chat")
async def chat(req: ChatRequest):
    async def safe_stream():
        try:
            async for frame in chat_stream(req):
                yield frame
        except Exception as exc:  # keep the connection alive: emit a terminal error event
            yield _sse("error", {"message": f"Factory: {type(exc).__name__}: {exc}"})

    return StreamingResponse(
        safe_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/models")
async def models():
    provider, base_url, api_key, model = resolve_llm_config()
    try:
        model_ids = await fetch_models(base_url, api_key)
    except Exception:
        model_ids = []
    return {
        "provider": provider,
        "model": model,
        "models": model_ids,
        "providers": providers.get_all(),
    }


@app.get("/workflows")
async def workflows():
    """All n8n workflows, condensed for the UI's card view."""
    client = N8NClient()
    try:
        data = await client.list_workflows()
    except Exception as exc:
        return {"base_url": config.N8N_BASE_URL, "workflows": [], "error": str(exc)}
    items = []
    for w in data:
        items.append({
            "id": w.get("id"),
            "name": w.get("name", "Untitled"),
            "active": bool(w.get("active")),
            "node_count": len(w.get("nodes") or []),
            "updated_at": (w.get("updatedAt") or "")[:10],
        })
    return {"base_url": config.get_n8n_base_url(), "workflows": items}


# ---- Settings ----------------------------------------------------------------


class N8NSettings(BaseModel):
    base_url: str
    api_key: str | None = None


class ProviderCreate(BaseModel):
    name: str
    base_url: str
    api_key: str = ""
    default_model: str = ""


class ProviderUpdate(BaseModel):
    base_url: str | None = None
    default_model: str | None = None
    api_key: str = ""


class ProviderSelect(BaseModel):
    id: str


class ProviderTest(BaseModel):
    """Either test an explicit config, or reference a catalog provider by id."""
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    provider_id: str | None = None


@app.get("/settings")
async def settings():
    provider, _, _, model = resolve_llm_config()
    connected = False
    try:
        await N8NClient().list_workflows()
        connected = True
    except Exception:
        connected = False
    return {
        "provider": provider,
        "model": model,
        "providers": providers.get_all(),
        "n8n": {
            "base_url": config.get_n8n_base_url(),
            "has_key": bool(config.get_n8n_api_key()),
            "connected": connected,
        },
    }


@app.put("/settings/n8n")
async def update_n8n(req: N8NSettings):
    providers.set_setting("N8N_BASE_URL", req.base_url.strip().rstrip("/"))
    if req.api_key:
        providers.set_setting("N8N_API_KEY", req.api_key.strip())
    connected = False
    try:
        await N8NClient().list_workflows()
        connected = True
    except Exception:
        connected = False
    return {"base_url": config.get_n8n_base_url(), "connected": connected}


@app.get("/providers")
async def list_providers():
    return {"providers": providers.get_all()}


@app.post("/providers")
async def create_provider(req: ProviderCreate):
    if not req.name.strip() or not req.base_url.strip():
        raise HTTPException(status_code=400, detail="name and base_url are required")
    try:
        return providers.add_provider(req.name, req.base_url, req.api_key, req.default_model)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.put("/providers/{provider_id}")
async def update_provider(provider_id: str, req: ProviderUpdate):
    try:
        return providers.update_provider(
            provider_id, req.base_url, req.default_model, req.api_key
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="provider not found")


@app.delete("/providers/{provider_id}")
async def delete_provider(provider_id: str):
    catalog = providers.get_catalog()
    if provider_id not in catalog:
        raise HTTPException(status_code=404, detail="provider not found")
    if catalog[provider_id].get("builtin"):
        raise HTTPException(status_code=400, detail="cannot delete a built-in provider")
    providers.delete_provider(provider_id)
    return {"deleted": provider_id}


@app.post("/providers/select")
async def select_provider(req: ProviderSelect):
    if req.id not in providers.get_catalog():
        raise HTTPException(status_code=404, detail="provider not found")
    providers.set_active_provider(req.id)
    return {"provider": req.id}


@app.post("/providers/test")
async def test_provider(req: ProviderTest):
    """One-shot ping against an OpenAI-compatible endpoint."""
    base_url, api_key, model = req.base_url, req.api_key, req.model
    if req.provider_id:
        info = providers.get_catalog().get(req.provider_id)
        if not info:
            return JSONResponse(status_code=200, content={"ok": False, "error": "provider not found"})
        base_url = info["base_url"]
        api_key = info.get("api_key", "") or os.getenv(info.get("key_env", ""), "")
        model = req.model or info.get("default_model") or ""
    if not base_url or not api_key or not model:
        missing = [n for n, v in (("base_url", base_url), ("api_key", api_key), ("model", model)) if not v]
        hint = ""
        if req.provider_id and "api_key" in missing:
            hint = f" — provider '{req.provider_id}' has no API key set; click Edit and save the key"
        return JSONResponse(status_code=200, content={
            "ok": False,
            "error": "need base_url + api_key + model (or a provider with a key + default model)"
                     + hint,
        })
    try:
        client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/"))
        resp = await asyncio.to_thread(
            client.chat.completions.create,
            model=model,
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=5,
        )
        return {"ok": True, "reply": resp.choices[0].message.content}
    except Exception as exc:
        return JSONResponse(status_code=200, content={"ok": False, "error": f"{type(exc).__name__}: {exc}"})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """Delete a workflow in n8n."""
    client = N8NClient()
    try:
        ok = await client.delete_workflow(workflow_id)
    except Exception as exc:
        return JSONResponse(status_code=502, content={"error": f"n8n: {exc}"})
    if not ok:
        return JSONResponse(
            status_code=404, content={"error": "Workflow not found or delete failed"}
        )
    return {"deleted": workflow_id}