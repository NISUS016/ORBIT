# TASK-03: Fix sync LLM calls blocking asyncio event loop

**Phase**: 0 — Bug Fix  
**Action**: MODIFY  
**Files**:
- `D:\ORBIT\backend\orchestrator.py`
- `D:\ORBIT\backend\routes.py`

**Dependencies**: None

---

## Read First

Both files. In `orchestrator.py`, both `classify_task()` and `design_agent()` use synchronous `OpenAI` client calls. In `routes.py`, they're called from async `chat_stream()`.

## Problem

Synchronous `client.chat.completions.create()` blocks the asyncio event loop for 5-30 seconds per call, stalling ALL concurrent requests.

## Instructions

### Step 1: Add async wrappers in `orchestrator.py`

Add `import asyncio` at the top. Then add these wrapper functions after the existing sync functions:

```python
async def classify_task_async(message: str, model: str) -> str:
    """Non-blocking wrapper around classify_task."""
    return await asyncio.to_thread(classify_task, message, model)

async def design_agent_async(task: str, model: str) -> dict:
    """Non-blocking wrapper around design_agent."""
    return await asyncio.to_thread(design_agent, task, model)
```

### Step 2: Add error handling to `classify_task()`

Wrap the body of `classify_task()` in try/except and add fuzzy matching:

```python
def classify_task(message: str, model: str) -> str:
    try:
        resp = get_llm_client().chat.completions.create(
            model=model,
            messages=[...],  # keep existing messages
            max_tokens=10,
        )
        result = resp.choices[0].message.content.strip().lower()
        # Fuzzy match
        for category in ("research", "summarizer", "extractor"):
            if category in result:
                return category
        return "novel"
    except Exception as e:
        print(f"[orchestrator] classify_task error: {e}")
        return "novel"
```

### Step 3: Update calls in `routes.py`

In `chat_stream()`, change:
- `orchestrator.classify_task(req.message, model)` → `await orchestrator.classify_task_async(req.message, model)`
- `orchestrator.design_agent(req.message, model)` → `await orchestrator.design_agent_async(req.message, model)`

## Acceptance Criteria

- [ ] `classify_task_async()` and `design_agent_async()` exist in `orchestrator.py`
- [ ] `classify_task()` has try/except and fuzzy category matching
- [ ] `routes.py` uses the async versions with `await`
- [ ] `/health` endpoint responds immediately while an LLM call is in progress
