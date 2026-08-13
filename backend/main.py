from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import json
import glob
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
    """Ask the LLM (guided by ORCHESTRATOR_GUIDE) to design a specialist
    agent for a novel task. Returns {name, system_prompt, summary}."""
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": ORCHESTRATOR_GUIDE},
                {"role": "user", "content": task},
            ],
            max_tokens=700,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        spec = json.loads(text)
    except Exception:
        spec = {}
    return {
        "name": str(spec.get("name", "")).strip(),
        "system_prompt": str(spec.get("system_prompt", "")).strip(),
        "summary": str(spec.get("summary", "")).strip(),
    }

def inject_system_prompt(body_json: str, prompt: str) -> str:
    """Swap the REPLACE_SYSTEM_PROMPT placeholder inside an n8n HTTP node
    body with the generated prompt (JSON-escaped)."""
    safe = prompt.replace("{{", "(").replace("}}", ")")
    escaped = json.dumps(safe)[1:-1]  # strip outer quotes, keep escapes
    return body_json.replace("REPLACE_SYSTEM_PROMPT", escaped)

async def factory_spawn(task: str, model: str) -> tuple[str, str, str]:
    """
    Pick a template JSON from /templates/, ask the LLM to design a
    specialist agent for it, push to n8n, activate, call its webhook,
    return (result, template_name, agent_summary).
    """
    template_files = glob.glob("../templates/*.json")
    if not template_files:
        return ("No templates available yet — template guy is still working!", "none", "")

    # Pick the first template (or let LLM pick — keep it simple for MVP)
    template_path = template_files[0]
    template_name = os.path.basename(template_path)

    with open(template_path) as f:
        workflow_json = json.load(f)

    # The LLM designs a unique agent brain for THIS task
    design = design_agent(task, model)
    design_name = design["name"] or "Factory Agent"
    design_summary = design["summary"] or ""

    # Name each spawned workflow after its task so agents are visible/unique in n8n
    label = " ".join(task.split()[:5]).translate({ord(c): None for c in '"\\/\n\t'})[:45]
    workflow_json["name"] = f"06 - {design_name} · {label}"

    # Give the spawned workflow a unique webhook path/id so multiple
    # spawns never collide in n8n, and inject the designed brain.
    for node in workflow_json.get("nodes", []):
        if node.get("type") == "n8n-nodes-base.webhook":
            node["parameters"]["path"] = f"factory-{uuid.uuid4().hex[:10]}"
            node["webhookId"] = f"orbit-factory-{uuid.uuid4().hex[:16]}"
        if node.get("type") == "n8n-nodes-base.httpRequest" and design["system_prompt"]:
            body = node.get("parameters", {}).get("bodyParametersJson", "")
            if body:
                node["parameters"]["bodyParametersJson"] = inject_system_prompt(body, design["system_prompt"])
        patch_llm_node(node, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL)

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
            return ("Factory: workflow creation failed", template_name, design_summary)

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

    return (result, template_name, design_summary)


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