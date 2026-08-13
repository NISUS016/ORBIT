# 🛠️ YOUR TASK — Backend + GitHub Setup
### Project: Orbit — AI Meta-Agent Factory
**Your role:** FastAPI backend, GitHub repo setup, glue everything together

---

## WHAT YOU'RE BUILDING

A FastAPI server that:
1. Receives a chat message from the UI
2. Uses an LLM to classify the task (research / summarize / extract / novel)
3. Routes **known tasks** → calls the right n8n webhook (n8n guy gives you these URLs)
4. Routes **novel tasks** → picks a template JSON from `/templates/`, pushes it to n8n API, gets a webhook back, calls it
5. Returns the result to the UI

---

## STEP 1 — Create the GitHub Repo (do this first, 10 min)

```
1. Go to github.com → New repo → name: orbit-agent-factory
2. Add README.md (just a title for now), set to Public
3. Clone locally: git clone https://github.com/YOUR_USERNAME/orbit-agent-factory
4. Add all 3 teammates as collaborators: Settings → Collaborators → Add people
5. Create this folder structure and commit it:

orbit-agent-factory/
├── backend/
│   ├── main.py          ← you write this
│   └── requirements.txt ← you write this
├── workflows/           ← n8n guy puts files here
├── templates/           ← template guy puts files here
├── ui/                  ← UI guy puts files here
├── scripts/
│   └── deploy.py        ← template guy writes this
├── .env.example         ← you write this
└── README.md

git add . && git commit -m "initial structure" && git push
```

Tell everyone to `git pull` after this.

---

## STEP 2 — Write the Backend (60-75 min)

### requirements.txt
```
fastapi
uvicorn
httpx
python-dotenv
openai
```

### .env.example
```
OPENROUTER_API_KEY=your_key_here
N8N_BASE_URL=http://localhost:5678
N8N_API_KEY=your_n8n_api_key_here

# Paste these in after n8n guy imports and activates his workflows
N8N_RESEARCH_WEBHOOK=
N8N_SUMMARIZER_WEBHOOK=
N8N_EXTRACTOR_WEBHOOK=
```

Copy `.env.example` → `.env` and fill in your OpenRouter key.

---

### main.py (full code, copy-paste this)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import os
import json
import glob
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

# Allow UI (running on localhost:any port) to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
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
        model="openai/gpt-4o-mini",
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
        await http.patch(
            f"{n8n_base}/api/v1/workflows/{workflow_id}",
            json={"active": True},
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
```

---

## STEP 3 — Run It (5 min)

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Test: open http://localhost:8000/health → should return `{"status":"ok"}`

---

## STEP 4 — Wire n8n Webhooks (after n8n guy is done, ~T+90min)

When the n8n guy gives you webhook URLs, paste them into your `.env`:
```
N8N_RESEARCH_WEBHOOK=http://localhost:5678/webhook/research
N8N_SUMMARIZER_WEBHOOK=http://localhost:5678/webhook/summarizer
N8N_EXTRACTOR_WEBHOOK=http://localhost:5678/webhook/extractor
```
Restart uvicorn. Done.

---

## STEP 5 — GitHub Commits (ongoing)

```bash
git add backend/
git commit -m "backend: FastAPI server with classify + route logic"
git push
```

Remind everyone to commit their files to their folders and push.

---

## YOUR DELIVERABLES CHECKLIST

- [ ] GitHub repo created, all 3 teammates added
- [ ] Folder structure committed and pushed
- [ ] `backend/main.py` working locally (`/health` returns ok)
- [ ] `.env.example` committed (never commit `.env` itself)
- [ ] Backend wired to n8n webhooks (after T+90min)
- [ ] End-to-end test passes (UI → backend → n8n → result)

---

## IF SOMETHING BREAKS

| Problem | Fix |
|---------|-----|
| CORS error from UI | Already handled — CORSMiddleware is in main.py |
| n8n webhook not responding | Check n8n guy has activated his workflows |
| OpenRouter key error | Make sure `.env` is in the `backend/` folder |
| Factory fails | That's okay — it'll return a message, not crash |
| Port 8000 busy | `uvicorn main:app --port 8001` and tell UI guy |
