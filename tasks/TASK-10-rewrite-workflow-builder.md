# TASK-10: Rewrite workflow_builder.py as validator and credential patcher

**Phase**: 2 — Agentic Orchestrator  
**Action**: REWRITE  
**File**: `D:\ORBIT\backend\workflow_builder.py`  
**Dependencies**: TASK-11

---

## Read First

- `D:\ORBIT\backend\workflow_builder.py` — current code
- `D:\ORBIT\backend\llm_config.py` — for `patch_llm_node()` function
- `D:\ORBIT\backend\config.py` — for credential accessors

## Purpose

The file no longer BUILDS workflows (the LLM does that via TASK-09). It now:
1. Patches LLM credentials into placeholder nodes
2. Ensures unique webhook paths
3. Generates workflow names
4. Produces graph summaries for UI

## Instructions

Rewrite the entire file with these functions:

### 1. `patch_credentials(workflow: dict, model: str | None = None) -> dict`

Loop through all nodes. For each one, call `patch_llm_node(node, base_url, api_key, llm_model)`. Get base_url/api_key/model from `config.get_llm_base_url()`, `config.get_llm_api_key()`, `config.get_llm_model()`.

### 2. `ensure_unique_webhook(workflow: dict) -> str`

Find the Webhook node. If its `path` contains "UNIQUE" or is empty, replace with `f"factory-{uuid.uuid4().hex[:10]}"`. Add `webhookId` if missing. Return the webhook path string.

### 3. `name_for_task(design_name: str, task: str) -> str`

KEEP from current code. Generates `"06 - {design_name} · {first 5 words of task}"`.

### 4. `graph_summary(workflow: dict) -> dict`

KEEP from current code. Extracts renderable node list (id, name, type, position) and connections.

### Functions to REMOVE

- `build_workflow()` — no longer needed, the LLM generates the full workflow

## Acceptance Criteria

- [ ] `build_workflow()` function does NOT exist
- [ ] `patch_credentials()` patches all HTTP Request nodes
- [ ] `ensure_unique_webhook()` makes paths unique and returns the path
- [ ] `name_for_task()` works as before
- [ ] `graph_summary()` works as before
- [ ] No references to `steps`, `system_prompt`, or the old spec format
