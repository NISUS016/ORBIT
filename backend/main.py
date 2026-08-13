from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import json
import glob
import uuid
from openai import OpenAI
from dotenv import load_dotenv
from llm_config import resolve_llm_config, patch_llm_node

load_dotenv()
app = FastAPI()

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

def classify_task(message: str) -> str:
    """Ask LLM to classify the task into one of 4 categories."""
    resp = client.chat.completions.create(
        model=LLM_MODEL,
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

async def call_webhook(url: str, task: str) -> str:
    """POST to an n8n webhook and return the result."""
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(url, json={"task": task})
        data = resp.json()
        # n8n returns a list by default
        if isinstance(data, list):
            data = data[0]
        return data.get("result", str(data))

async def factory_spawn(task: str) -> tuple[str, str]:
    """
    Pick a template JSON from /templates/, push it to n8n API,
    activate it, call its webhook, return (result, template_name).
    """
    template_files = glob.glob("../templates/*.json")
    if not template_files:
        return ("No templates available yet — template guy is still working!", "none")

    # Pick the first template (or let LLM pick — keep it simple for MVP)
    template_path = template_files[0]
    template_name = os.path.basename(template_path)

    with open(template_path) as f:
        workflow_json = json.load(f)

    # Give the spawned workflow a unique webhook path/id so multiple
    # spawns never collide in n8n.
    for node in workflow_json.get("nodes", []):
        if node.get("type") == "n8n-nodes-base.webhook":
            node["parameters"]["path"] = f"factory-{uuid.uuid4().hex[:10]}"
            node["webhookId"] = f"orbit-factory-{uuid.uuid4().hex[:16]}"
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
            return ("Factory: workflow creation failed", template_name)

        # Activate it
        await http.post(
            f"{n8n_base}/api/v1/workflows/{workflow_id}/activate",
            headers=headers,
        )

        # Get webhook URL from the created workflow's trigger node
        webhook_path = created.get("nodes", [{}])[0].get("parameters", {}).get("path", workflow_id)
        webhook_url  = f"{n8n_base}/webhook/{webhook_path}"

        result_resp = await http.post(webhook_url, json={"task": task})
        result_data = result_resp.json()
        if isinstance(result_data, list):
            result_data = result_data[0]
        result = result_data.get("result", str(result_data))

    return (result, template_name)


@app.post("/chat")
async def chat(req: ChatRequest):
    task_type = classify_task(req.message)
    spawned   = False
    agent_used = task_type

    if task_type in WEBHOOKS and WEBHOOKS[task_type]:
        # Route to known sub-agent
        result = await call_webhook(WEBHOOKS[task_type], req.message)
    else:
        # Novel task — try factory
        result, agent_used = await factory_spawn(req.message)
        spawned = True

    return {
        "response":   result,
        "agent_used": agent_used,
        "spawned":    spawned,
    }

@app.get("/health")
def health():
    return {"status": "ok"}