# ⚙️ YOUR TASK — n8n Workflows + Templates
### Project: Orbit — AI Meta-Agent Factory
**Your role:** Set up n8n locally, build 3 sub-agent workflows, create factory templates

> ⚠️ None of us have n8n experience. This doc walks you through everything step by step from zero. Follow it in order and you'll be fine.

---

## WHAT YOU'RE BUILDING

You're setting up **n8n** (a visual workflow tool) locally and creating 4 workflows:

1. **Research Agent** — takes a query, does a web search or LLM lookup, returns findings
2. **Summarizer Agent** — takes text, returns a concise summary
3. **Extractor Agent** — takes text, pulls out key fields as structured data
4. **Template Workflow** — a blank-ish workflow the backend uses to "spawn" new agents for novel tasks

Each workflow is triggered by a **webhook** (a URL the backend can POST to). You'll give those URLs to Nishchal.

---

## STEP 1 — Install n8n locally (15 min)

You need Node.js installed. Check: `node --version` in terminal. If not installed: https://nodejs.org → download LTS.

```bash
# Install n8n globally
npm install -g n8n

# Start it
n8n start
```

It will print something like:
```
n8n ready on port 5678
Editor is now accessible via:  http://localhost:5678
```

Open http://localhost:5678 in your browser. Create a free account (just email + password, no credit card). **Keep this terminal open the whole time.**

---

## STEP 2 — Add your OpenRouter API credential (5 min)

> Nishchal will give you the OpenRouter API key.

In n8n:
1. Top-right corner → **Settings** → **Credentials**
2. Click **Add Credential**
3. Search for: `OpenAI`
4. Fill in:
   - **API Key:** paste the OpenRouter key
   - **Base URL:** `https://openrouter.ai/api/v1`
5. Click **Save** — name it `OpenRouter`

You'll use this credential in all 4 workflows.

---

## STEP 3 — Build the Research Agent (20 min)

**What it does:** Receives a task via webhook → asks an LLM to research/answer it → returns the result.

### Create new workflow:
1. Click **+ New Workflow** → name it `02 - Research Agent`
2. Add these nodes in order:

### Node 1: Webhook (trigger)
- Click **+** → search `Webhook` → add it
- Settings:
  - **HTTP Method:** POST
  - **Path:** `research`  ← type this exactly
  - **Response Mode:** `Last Node`
- Click **Save**
- Copy the **Test URL** shown — send it to Nishchal as `N8N_RESEARCH_WEBHOOK`

### Node 2: Basic LLM Chain
- Click **+** after the Webhook node → search `Basic LLM Chain` → add it
- Settings:
  - **Prompt:** paste this:
    ```
    You are a research assistant. Answer the following task thoroughly with facts and key points.
    
    Task: {{ $json.task }}
    ```
  - **Model:** click the credential picker → select `OpenRouter` → choose model `openai/gpt-4o-mini`
- Connect it to the Webhook node (drag the dot)

### Node 3: Set (format output)
- Click **+** → search `Edit Fields (Set)` → add it
- Click **Add field**:
  - **Name:** `result`
  - **Value:** click the lightning icon → select `Basic LLM Chain` → `response` (or `text`)
- Connect it to the LLM Chain node

### Activate & Test:
- Top-right toggle: **Inactive → Active**
- In n8n, click **Execute Workflow** (or test via Postman):
  ```
  POST http://localhost:5678/webhook/research
  Body: { "task": "What are the top 3 AI frameworks in 2026?" }
  ```
- You should get back `{ "result": "..." }`

---

## STEP 4 — Build the Summarizer Agent (15 min)

Same process as Research, with different prompt and path.

1. **+ New Workflow** → name: `03 - Summarizer Agent`
2. **Webhook node** → Path: `summarizer` → copy URL for Nishchal
3. **Basic LLM Chain** → Prompt:
   ```
   Summarize the following text in 3-5 clear bullet points. Be concise.
   
   Text: {{ $json.task }}
   ```
4. **Edit Fields (Set)** → field: `result` → value: LLM response
5. Activate → test with:
   ```
   POST http://localhost:5678/webhook/summarizer
   Body: { "task": "The quick brown fox jumps over the lazy dog. This is a classic pangram..." }
   ```

---

## STEP 5 — Build the Extractor Agent (15 min)

1. **+ New Workflow** → name: `04 - Extractor Agent`
2. **Webhook node** → Path: `extractor` → copy URL for Nishchal
3. **Basic LLM Chain** → Prompt:
   ```
   Extract all key information from the following text. Return it as a clear labeled list: names, dates, numbers, locations, and key facts.
   
   Text: {{ $json.task }}
   ```
4. **Edit Fields (Set)** → field: `result` → value: LLM response
5. Activate → test with:
   ```
   POST http://localhost:5678/webhook/extractor
   Body: { "task": "On July 20 1969, Neil Armstrong landed on the Moon in the Sea of Tranquility." }
   ```

---

## STEP 6 — Export all 3 workflows as JSON (10 min)

For each workflow (Research, Summarizer, Extractor):
1. Open the workflow
2. Top-right ⋮ menu → **Download** (or Export)
3. It downloads a `.json` file
4. Rename them:
   - `02_research_agent.json`
   - `03_summarizer_agent.json`
   - `04_extractor_agent.json`

Put these files in the `workflows/` folder of the GitHub repo and push:
```bash
git add workflows/
git commit -m "workflows: research, summarizer, extractor agents"
git push
```

---

## STEP 7 — Build the Factory Template Workflow (20 min)

This is a "blank" workflow that the backend can clone when it gets a novel task. It should be a generic LLM responder.

1. **+ New Workflow** → name: `05 - Factory Template`
2. **Webhook node** → Path: `factory-spawned-REPLACE` (leave as is — backend changes it)
3. **Basic LLM Chain** → Prompt:
   ```
   You are a helpful AI assistant. Complete the following task as best you can.
   
   Task: {{ $json.task }}
   ```
4. **Edit Fields (Set)** → field: `result` → value: LLM response
5. **Do NOT activate this one** — it's just a template for the backend to copy
6. Export → rename `05_template_workflow.json` → put in `templates/` folder

---

## STEP 8 — Write the deploy script (15 min)

This script pushes all workflow JSONs to n8n via API so the team doesn't have to import manually.

Create `scripts/deploy.py`:

```python
"""
deploy.py — pushes all workflow JSONs to n8n via API.
Run: python scripts/deploy.py
Requires: N8N_BASE_URL and N8N_API_KEY in .env
"""

import os
import json
import glob
import httpx
from dotenv import load_dotenv

load_dotenv()

N8N_BASE = os.getenv("N8N_BASE_URL", "http://localhost:5678")
N8N_KEY  = os.getenv("N8N_API_KEY", "")
HEADERS  = {"X-N8N-API-KEY": N8N_KEY, "Content-Type": "application/json"}

def deploy_folder(folder: str, activate: bool = True):
    files = glob.glob(f"{folder}/*.json")
    if not files:
        print(f"  No JSONs found in {folder}/")
        return

    for path in files:
        name = os.path.basename(path)
        with open(path) as f:
            workflow = json.load(f)

        resp = httpx.post(f"{N8N_BASE}/api/v1/workflows", json=workflow, headers=HEADERS)
        if resp.status_code not in (200, 201):
            print(f"  ❌ {name}: {resp.status_code} {resp.text[:100]}")
            continue

        wf_id = resp.json().get("id")
        print(f"  ✅ {name} → id={wf_id}")

        if activate and wf_id:
            httpx.patch(
                f"{N8N_BASE}/api/v1/workflows/{wf_id}",
                json={"active": True},
                headers=HEADERS,
            )
            print(f"     Activated.")

if __name__ == "__main__":
    print("Deploying sub-agent workflows (workflows/)...")
    deploy_folder("workflows", activate=True)

    print("\nDeploying factory templates (templates/) — NOT activating...")
    deploy_folder("templates", activate=False)

    print("\nDone! Check n8n at", N8N_BASE)
```

Push it:
```bash
git add scripts/ templates/
git commit -m "templates + deploy script"
git push
```

---

## STEP 9 — Get your n8n API key (for deploy.py)

1. In n8n: top-right → **Settings** → **API**
2. Click **Create API Key**
3. Copy the key
4. Give it to Nishchal — he'll add it to `.env` as `N8N_API_KEY`

---

## GIVE NISHCHAL THESE WEBHOOK URLS

After activating all 3 sub-agent workflows, copy the webhook URLs from each:
- The **production URL** (not the test URL) looks like: `http://localhost:5678/webhook/research`

Send Nishchal:
```
N8N_RESEARCH_WEBHOOK=http://localhost:5678/webhook/research
N8N_SUMMARIZER_WEBHOOK=http://localhost:5678/webhook/summarizer
N8N_EXTRACTOR_WEBHOOK=http://localhost:5678/webhook/extractor
N8N_API_KEY=<your key from Step 9>
```

---

## YOUR DELIVERABLES CHECKLIST

- [ ] n8n running locally on port 5678
- [ ] OpenRouter credential added in n8n
- [ ] Research Agent: working + webhook URL sent to Nishchal
- [ ] Summarizer Agent: working + webhook URL sent to Nishchal
- [ ] Extractor Agent: working + webhook URL sent to Nishchal
- [ ] All 3 workflow JSONs in `workflows/` folder on GitHub
- [ ] Factory template JSON in `templates/` folder on GitHub
- [ ] `scripts/deploy.py` pushed to GitHub
- [ ] n8n API key sent to Nishchal

---

## IF SOMETHING BREAKS

| Problem | Fix |
|---------|-----|
| n8n won't start | Make sure Node.js is installed: `node --version` |
| Port 5678 already in use | `n8n start --port 5679` and update all URLs |
| Webhook returns nothing | Make sure workflow is **Activated** (toggle top-right) |
| LLM returns error | Check the OpenRouter key is correct in credentials |
| "Cannot find module" | Run `npm install -g n8n` again |
| deploy.py errors | Check `.env` has `N8N_API_KEY` and `N8N_BASE_URL` filled |

---

## QUICK n8n GLOSSARY (since none of us know it)

| Term | What it means |
|------|--------------|
| **Workflow** | A pipeline of connected nodes — like a flowchart |
| **Node** | One step in the workflow (webhook, LLM call, etc.) |
| **Webhook** | A URL that triggers a workflow when you POST to it |
| **Credential** | API key stored securely in n8n (you add once, use everywhere) |
| **Activate** | Makes the webhook URL live and listening |
| **Execute Workflow** | Test-runs the workflow manually in the editor |
| **Export** | Downloads the workflow as a JSON file |
