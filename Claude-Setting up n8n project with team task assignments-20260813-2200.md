# Setting up n8n project with team task assignments

**Created:** 8/13/2026 21:59:37  
**Updated:** 8/13/2026 21:59:37  
**Exported:** 8/13/2026 22:00:15  
**Link:** [https://claude.ai/share/e99b0562-1f71-4dd9-8aa7-54635f5c3ce3](https://claude.ai/share/e99b0562-1f71-4dd9-8aa7-54635f5c3ce3)  

## User:

> 8/13/2026 21:34:14

help me out with documentation i will do backend , and github repo it has to be local host , ui one guy and one template configurer , none of us have n8n experience , and i have to give them all task files of what to do

## Assistant:

> 8/13/2026 21:37:03

> Viewed 4 files
>
> - Tool: view
> - Tool: view
> - Tool: view
> - Tool: view
> - **Done**

Now I have everything I need. Let me create the three task files — one for you (backend + GitHub), one for the UI person, and one for the template configurer — all written to be n8n-beginner friendly.

> Viewed file
>
> - Tool: view
> - **Done**

Now I have enough context. Let me create three task files — one per person, clear and beginner-friendly for n8n.

> Created 3 files, presented file
>
> - Task file for Nishchal - Backend + GitHub
> - Task file for UI person
> - Task file for template configurer / n8n person
> - Presenting file(s)...
> - **Done**

Three task files, one per person. Here's the summary so you can hand them out immediately:

**TASK_NISHCHAL_Backend_GitHub.md — YOU**
- Create the GitHub repo + folder structure (do this first, everyone else clones after)
- Full `main.py` code is in there — FastAPI, classify with LLM, route to n8n, factory spawn
- `.env.example` template included
- Checklist of what Nishchal needs from the n8n guy (webhook URLs + API key) and at what time to wire them

**TASK_UI_Person.md — UI Guy**
- Complete `ui/index.html` code, copy-paste ready — dark themed, chat bubbles, agent badges, ✨ spawned badge
- Zero dependencies, no npm, just open in Chrome
- Tells him exactly what backend URL to hit and what to do if it's down

**TASK_Template_Configurer.md — Template Configurer (n8n guy)**
- Written assuming zero n8n experience — step-by-step from installing n8n to activating workflows
- Builds all 3 sub-agents (Research, Summarizer, Extractor) with exact prompts to paste
- Builds the factory template + `deploy.py` script
- Tells him exactly what to send you (webhook URLs + API key) and when

**Sync points to tell everyone:**
- **T+0:** You push the folder structure, everyone clones
- **T+60:** Everyone has working stubs — n8n guy should have webhook URLs ready
- **T+90:** Wire meeting — n8n guy pastes URLs into your `.env`, restart backend, UI guy tests end-to-end
- **T+110:** Full demo run-through

> File: /mnt/user-data/outputs/TASK_NISHCHAL_Backend_GitHub.md

> File: /mnt/user-data/outputs/TASK_UI_Person.md

> File: /mnt/user-data/outputs/TASK_Template_Configurer.md

## User:

> 8/13/2026 21:47:00

okay give me a description to make a pitch ppt dont make a doc tell me in chat

## Assistant:

> 8/13/2026 21:47:16

Here's your pitch narrative, slide by slide:

---

**Slide 1 — Title**
"Orbit: The AI That Builds AI Agents"
Subtitle: *An intelligent meta-agent that spawns specialized sub-agents on demand*

---

**Slide 2 — The Problem**
Every AI task is different — but most tools give you one generic chatbot. Summarizing a research paper needs different logic than extracting invoice data or answering a current-events question. You end up doing the routing manually, or building separate tools for each.

---

**Slide 3 — Our Solution**
Orbit is a meta-agent. You give it any task in plain English, it figures out what kind of task it is, and either routes to the right specialist agent — or builds a new one on the fly if nothing fits.

---

**Slide 4 — How It Works (Architecture)**
Three layers: a chat UI, a FastAPI backend that classifies the task using an LLM, and n8n handling the actual agent workflows. Known tasks (research, summarize, extract) hit pre-built sub-agents. Novel tasks hit the factory — which picks a template, spins up a new workflow via the n8n API, and calls it immediately.

---

**Slide 5 — Live Demo**
Show the UI. Type a research query → backend classifies → Research Agent responds. Then type something weird and novel → Factory spawns → ✨ badge appears. That's the wow moment.

---

**Slide 6 — Why n8n**
n8n gives you visual, modular, API-accessible workflows with zero infra overhead. Each sub-agent is an isolated workflow with its own webhook. The orchestrator doesn't know or care how they work internally — it just calls them. This makes the system naturally extensible.

---

**Slide 7 — Real-World Use Cases**
Customer support triage that routes to different agents by issue type. Research pipelines that spawn domain-specific agents per topic. Enterprise automation where new task types get new agents without redeploying anything.

---

**Slide 8 — What We Built (Team + Tech Stack)**
3-person team, 2 hours. Stack: Python FastAPI, n8n (self-hosted), OpenRouter (LLM via OpenAI-compatible API), vanilla HTML/CSS/JS UI. Runs fully on localhost.

---

**Slide 9 — Future Roadmap**
Phase 2: LLM writes the entire workflow JSON — true autonomous agent generation. Phase 3: OpenClaw as the orchestrator frontend for memory and persistence. Phase 4: Multi-user dashboard to manage, monitor, and retire spawned agents.

---

**Slide 10 — Closing**
"Orbit doesn't just answer tasks — it assembles the right mind for each one."
GitHub link + team names.

---

Keep slides visual and minimal — one idea per slide, big font, diagram on slide 4. The demo on slide 5 is your strongest moment so make sure it's working before you present.

Powered by Claude Exporter (https://www.ai-chat-exporter.net)
