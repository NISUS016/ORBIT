# TASK-12: Update routes.py for the new agentic pipeline

**Phase**: 3 — Integration  
**Action**: MODIFY  
**File**: `D:\ORBIT\backend\routes.py`  
**Dependencies**: TASK-02, TASK-03, TASK-05, TASK-09, TASK-10, TASK-13

---

## Read First

- `D:\ORBIT\backend\routes.py` — current full file
- `D:\ORBIT\backend\orchestrator.py` — new version from TASK-09
- `D:\ORBIT\backend\workflow_builder.py` — new version from TASK-10

## Purpose

Update the `/chat` SSE pipeline to use the new agentic workflow generation. The classify → design → build → deploy → execute flow changes.

## Instructions

### Step 1: Update imports

Ensure these imports exist:
```python
from typing import AsyncGenerator
import orchestrator
import workflow_builder
import config
from n8n_client import N8NClient, call_webhook
```

Remove any import of `build_workflow` from workflow_builder (it no longer exists).

### Step 2: Update `chat_stream()`

Replace the entire `chat_stream()` function body:

```python
async def chat_stream(req: ChatRequest) -> AsyncGenerator[str, None]:
    model = (req.model or config.get_llm_model()).strip() or config.get_llm_model()

    # Classify
    yield _sse("status", {"stage": "classify", "message": "Classifying task…"})
    task_type = await orchestrator.classify_task_async(req.message, model)

    # Check webhooks LIVE (not stale snapshot)
    webhooks = config.get_webhooks_live()
    if task_type in webhooks and webhooks[task_type]:
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
    result, status_code = await client.call_spawned(req.message, model, webhook_url)

    yield _sse("done", {
        "response": result,
        "agent_used": workflow.get("name", "Generated Agent"),
        "spawned": True,
        "agent_summary": workflow.get("summary", ""),
        "model": model,
        "node_count": len(workflow.get("nodes", [])),
    })
```

### Step 3: Verify no stale references

- No `config.WEBHOOKS` — use `config.get_webhooks_live()`
- No `orchestrator.design_agent` — use `orchestrator.design_workflow_async`
- No `workflow_builder.build_workflow` — use `workflow_builder.patch_credentials` + `ensure_unique_webhook`
- No `orchestrator.classify_task` direct call — use `orchestrator.classify_task_async`

## Acceptance Criteria

- [ ] Uses `classify_task_async` and `design_workflow_async` (non-blocking)
- [ ] Uses `config.get_webhooks_live()` instead of `config.WEBHOOKS`
- [ ] Novel task: design_workflow → patch_credentials → ensure_unique_webhook → deploy → execute
- [ ] SSE `design` event includes `node_count` and `generation_log`
- [ ] Error messages from n8n creation failures are forwarded
- [ ] No references to old functions (`design_agent`, `build_workflow`, `config.WEBHOOKS`)
- [ ] Only ONE `/health` endpoint
