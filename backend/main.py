from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import json
import uuid
import asyncio
from openai import OpenAI
from dotenv import load_dotenv
from llm_config import resolve_llm_config, patch_llm_node, fetch_models

load_dotenv()
app = FastAPI()

# The orchestrator's guide: tells the LLM how to design each spawned agent
with open(os.path.join(os.path.dirname(__file__), "orchestrator_instructions.md"), encoding="utf-8") as _guide:
    ORCHESTRATOR_GUIDE = _guide.read()

# Allow UI (running on localhost:any port) to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LLM_PROVIDER, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL = resolve_llm_config()

client = OpenAI(
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
)

WEBHOOKS = {
    "research":   os.getenv("N8N_RESEARCH_WEBHOOK", ""),
    "summarizer": os.getenv("N8N_SUMMARIZER_WEBHOOK", ""),
    "extractor":  os.getenv("N8N_EXTRACTOR_WEBHOOK", ""),
}

class ChatRequest(BaseModel):
    message: str
    model: str | None = None

def classify_task(message: str, model: str) -> str:
    """Ask LLM to classify the task into one of 4 categories."""
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Classify the user's task into exactly one of these: "
                    "research, summarizer, extractor, novel. "
                    "- research: find info, look something up, current events\n"
                    "- summarizer: shorten/condense/summarize text\n"
                    "- extractor: pull out fields/data from text\n"
                    "- novel: anything else\n"
                    "Reply with ONLY the one word, lowercase."
                )
            },
            {"role": "user", "content": message}
        ],
        max_tokens=5,
    )
    return resp.choices[0].message.content.strip().lower()

async def call_webhook(url: str, task: str, model: str) -> str:
    """POST to an n8n webhook and return the result."""
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(url, json={"task": task, "model": model})
        data = resp.json()
        # n8n returns a list by default
        if isinstance(data, list):
            data = data[0]
        return data.get("result", str(data))

def design_agent(task: str, model: str) -> dict:
    """Ask the LLM (guided by ORCHESTRATOR_GUIDE) to design a NEW specialist
    workflow for a novel task. Returns {name, summary, steps:[{title,system_prompt}]}."""
    fallback_prompt = "You are a helpful AI assistant. Complete the given task as best you can."
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": ORCHESTRATOR_GUIDE},
                {"role": "user", "content": task},
            ],
            max_tokens=900,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        spec = json.loads(text)
    except Exception:
        spec = {}

    def _s(key: str) -> str:
        return str(spec.get(key, "") or "").strip()

    steps = spec.get("steps") if isinstance(spec, dict) else None
    if not isinstance(steps, list):
        prompt = _s("system_prompt")
        steps = [{"title": "Agent", "system_prompt": prompt or fallback_prompt}]
    clean = []
    for s in steps:
        if not isinstance(s, dict):
            continue
        title = str(s.get("title") or "Agent").strip()
        prompt = str(s.get("system_prompt") or s.get("content") or "").strip()
        if not prompt:
            prompt = fallback_prompt
        clean.append({"title": title[:40], "system_prompt": prompt[:400]})
        if len(clean) == 4:
            break
    if not clean:
        clean = [{"title": "Agent", "system_prompt": fallback_prompt}]

    return {
        "name": _s("name") or "Factory Agent",
        "summary": _s("summary"),
        "steps": clean,
    }

def build_workflow(spec: dict) -> dict:
    """Assemble a NEW n8n workflow JSON from the LLM's design:
    Webhook -> LLM step 1 -> ... -> LLM step N -> Format -> respond.

    Each step is its own LLM call node: step 1 sees the user's task,
    later steps see the previous step's output.
    """
    steps = spec["steps"]
    uid = uuid.uuid4().hex[:10]

    nodes = [{
        "parameters": {
            "httpMethod": "POST",
            "path": f"factory-{uid}",
            "responseMode": "lastNode",
        },
        "id": f"orbit-{uid}-webhook",
        "name": "Webhook",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [0, 0],
        "webhookId": f"orbit-factory-{uuid.uuid4().hex[:16]}",
    }]
    connections = {}

    prev = "Webhook"
    for i, step in enumerate(steps, start=1):
        title = f"Step {i}: {step['title']}"
        system = step["system_prompt"].replace("{{", "(").replace("}}", ")")
        # JSON.stringify keeps multi-line/quoted model output valid inside the JSON body
        user_input = (
            "{{ JSON.stringify($json.body.task) }}"
            if i == 1
            else "{{ JSON.stringify($json.choices[0].message.content) }}"
        )
        body = "=" + json.dumps({
            "model": "REPLACE_LLM_MODEL",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_input},
            ],
        }, indent=2)
        # content is an expression, not a literal string — unquote it
        body = body.replace('"content": "%s"' % user_input, f'"content": {user_input}')
        nodes.append({
            "parameters": {
                "requestMethod": "POST",
                "url": "REPLACE_LLM_URL",
                "responseFormat": "json",
                "jsonParameters": True,
                "headerParametersJson": "{\n  \"Content-Type\": \"application/json\",\n  \"Authorization\": \"Bearer REPLACE_LLM_KEY\"\n}",
                "bodyParametersJson": body,
                "options": {},
            },
            "id": f"orbit-{uid}-llm{i}",
            "name": title,
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 2,
            "position": [220 * i, 60 * (i % 2)],
        })
        connections[prev] = {"main": [[{"node": title, "type": "main", "index": 0}]]}
        prev = title

    nodes.append({
        "parameters": {
            "assignments": {
                "assignments": [{
                    "id": f"orbit-{uid}-result",
                    "name": "result",
                    "type": "string",
                    "value": "={{ $json.choices[0].message.content }}",
                }]
            }
        },
        "id": f"orbit-{uid}-set",
        "name": "Format Result",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [220 * (len(steps) + 1), 0],
    })
    connections[prev] = {"main": [[{"node": "Format Result", "type": "main", "index": 0}]]}

    workflow_json = {
        "name": "06 - Factory Agent",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
    }
    for node in nodes:
        patch_llm_node(node, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL)
    return workflow_json

async def factory_spawn(task: str, model: str) -> tuple[str, str, str]:
    """
    Ask the LLM to design a NEW specialist workflow for a novel task,
    build its JSON, push to n8n, activate, call its webhook.
    Returns (result, agent_name, agent_summary).
    """
    # The LLM designs a NEW workflow for THIS task (structure + brains)
    spec = design_agent(task, model)
    design_name = spec["name"]
    design_summary = spec["summary"]

    workflow_json = build_workflow(spec)

    # Name each spawned workflow after its agent so it's visible/unique in n8n
    label = " ".join(task.split()[:5]).translate({ord(c): None for c in '"\\/\n\t'})[:45]
    workflow_json["name"] = f"06 - {design_name} · {label}"

    n8n_base = os.getenv("N8N_BASE_URL", "http://localhost:5678")
    n8n_key  = os.getenv("N8N_API_KEY", "")
    headers  = {"X-N8N-API-KEY": n8n_key, "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=20) as http:
        # Create the workflow
        create_resp = await http.post(
            f"{n8n_base}/api/v1/workflows",
            json=workflow_json,
            headers=headers,
        )
        created = create_resp.json()
        workflow_id = created.get("id")

        if not workflow_id:
            return ("Factory: workflow creation failed", design_name, design_summary)

        # Activate it (n8n activation is async — webhook may take a moment)
        await http.post(
            f"{n8n_base}/api/v1/workflows/{workflow_id}/activate",
            headers=headers,
        )

        # Get webhook URL from the created workflow's trigger node
        webhook_path = created.get("nodes", [{}])[0].get("parameters", {}).get("path", workflow_id)
        webhook_url  = f"{n8n_base}/webhook/{webhook_path}"

        # Wait for the webhook to be live, retrying activation races
        result_data = None
        for attempt in range(5):
            result_resp = await http.post(webhook_url, json={"task": task, "model": model})
            result_data = result_resp.json()
            if isinstance(result_data, list):
                result_data = result_data[0]
            err = str(result_data)
            if "Error in workflow" not in err and result_resp.status_code < 500:
                break
            await asyncio.sleep(0.6)
        result = result_data.get("result", str(result_data))

    return (result, design_name, design_summary)


@app.post("/chat")
async def chat(req: ChatRequest):
    model      = (req.model or LLM_MODEL).strip() or LLM_MODEL
    task_type  = classify_task(req.message, model)
    spawned    = False
    agent_used = task_type

    if task_type in WEBHOOKS and WEBHOOKS[task_type]:
        # Route to known sub-agent
        result = await call_webhook(WEBHOOKS[task_type], req.message, model)
        agent_summary = ""
    else:
        # Novel task — factory designs a specialist agent
        result, agent_used, agent_summary = await factory_spawn(req.message, model)
        spawned = True

    return {
        "response":     result,
        "agent_used":   agent_used,
        "spawned":      spawned,
        "agent_summary": agent_summary,
        "model":        model,
    }

@app.get("/models")
async def models():
    try:
        model_ids = await fetch_models(LLM_BASE_URL, LLM_API_KEY)
    except Exception:
        model_ids = []
    return {
        "provider": LLM_PROVIDER,
        "model":    LLM_MODEL,
        "models":   model_ids,
    }

@app.get("/health")
def health():
    return {"status": "ok"}