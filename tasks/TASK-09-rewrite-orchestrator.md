# TASK-09: Rewrite orchestrator.py with agentic generation loop

**Phase**: 2 — Agentic Orchestrator  
**Action**: REWRITE  
**File**: `D:\ORBIT\backend\orchestrator.py`  
**Dependencies**: TASK-03, TASK-06, TASK-07, TASK-08

---

## Read First

- `D:\ORBIT\backend\orchestrator.py` — current code (keep `classify_task` logic with TASK-03 fixes)
- `D:\ORBIT\backend\orchestrator_instructions.md` — new prompt from TASK-08
- `D:\ORBIT\backend\n8n_nodes_catalog.md` — node catalog from TASK-06
- `D:\ORBIT\backend\workflow_validator.py` — validator from TASK-07
- `D:\ORBIT\backend\config.py` — for `get_llm_client`

## Purpose

Rewrite the file to replace `design_agent()` (which outputs `{name, summary, steps}`) with `design_workflow()` (which outputs full n8n workflow JSON via an agentic multi-turn loop).

## Instructions

Rewrite the entire file with these functions:

### 1. Module-level setup

```python
import asyncio, json, os, uuid
from config import get_llm_client
from workflow_validator import validate_workflow, parse_llm_workflow_response
```

Load both prompt files at module startup:
- `orchestrator_instructions.md` → `SYSTEM_PROMPT`
- `n8n_nodes_catalog.md` → `NODE_CATALOG`
- Combine: `FULL_SYSTEM_PROMPT = SYSTEM_PROMPT + "\n\n## Available n8n Nodes Reference\n\n" + NODE_CATALOG`

### 2. `classify_task(message, model) -> str`

Keep from current code but with TASK-03 fixes (try/except, fuzzy matching, return "novel" on error).

### 3. `classify_task_async(message, model) -> str`

`await asyncio.to_thread(classify_task, message, model)`

### 4. `design_workflow(task, model, max_attempts=3) -> tuple[dict, list[str]]`

The core agentic function. Flow:

1. Build initial messages: `[{system: FULL_SYSTEM_PROMPT}, {user: task}]`
2. Loop up to `max_attempts` times:
   a. Call LLM with `response_format={"type": "json_object"}`, `max_tokens=4000`, `temperature=0.3`
   b. Parse response with `parse_llm_workflow_response()`
   c. If parse fails: append assistant message + user error message to conversation, continue
   d. Validate with `validate_workflow()`
   e. If valid: return `(workflow, log)`
   f. If invalid: append assistant message with the workflow JSON + user message listing all errors, continue
3. If all attempts fail: return `(_fallback_workflow(task), log)`

Return a tuple of `(workflow_dict, generation_log)` where log is a list of strings describing each attempt.

### 5. `design_workflow_async(task, model, max_attempts=3)`

`await asyncio.to_thread(design_workflow, task, model, max_attempts)`

### 6. `_fallback_workflow(task) -> dict`

Generates a simple valid 3-node workflow (Webhook → HTTP Request → Set) as a last resort. Must pass `validate_workflow()`. Use `uuid.uuid4().hex[:10]` for unique IDs.

The fallback uses `REPLACE_LLM_URL`, `REPLACE_LLM_KEY`, `REPLACE_LLM_MODEL` placeholders.

### Functions to REMOVE

- `design_agent()` — replaced by `design_workflow()`
- `design_agent_async()` — replaced by `design_workflow_async()`
- `FALLBACK_PROMPT` constant — replaced by `_fallback_workflow()`
- `ORCHESTRATOR_GUIDE` constant — replaced by `FULL_SYSTEM_PROMPT`

## Acceptance Criteria

- [ ] `classify_task()` has error handling and fuzzy matching
- [ ] `classify_task_async()` exists
- [ ] `design_workflow(task, model)` returns `(workflow_dict, log_list)`
- [ ] Multi-turn: generates → validates → feeds errors back → retries (up to 3 attempts)
- [ ] `design_workflow_async()` exists
- [ ] Loads both `orchestrator_instructions.md` and `n8n_nodes_catalog.md`
- [ ] `_fallback_workflow()` generates a valid 3-node workflow
- [ ] The fallback workflow passes `validate_workflow()`
- [ ] No references to `design_agent`, `FALLBACK_PROMPT`, or `ORCHESTRATOR_GUIDE`
