# TASK-05: Remove duplicate health endpoint and fix type annotation

**Phase**: 0 — Bug Fix  
**Action**: MODIFY  
**File**: `D:\ORBIT\backend\routes.py`  
**Dependencies**: None

---

## Read First

Lines 298-320 of `routes.py`. There are two identical `@app.get("/health")` definitions.

## Instructions

### Step 1: Remove duplicate

Delete the SECOND `@app.get("/health")` block (the one near the end of the file, around line 318-320):

```python
# DELETE THIS ENTIRE BLOCK:
@app.get("/health")
def health():
    return {"status": "ok"}
```

Keep the FIRST one (around line 298-300).

### Step 2: Fix type annotation

Add `from typing import AsyncGenerator` to the imports.

Change the `chat_stream` function signature from:
```python
async def chat_stream(req: ChatRequest) -> str:
```
To:
```python
async def chat_stream(req: ChatRequest) -> AsyncGenerator[str, None]:
```

## Acceptance Criteria

- [ ] Only ONE `/health` endpoint exists in the file
- [ ] `chat_stream` has correct `AsyncGenerator[str, None]` return type
- [ ] Server starts without errors
- [ ] `GET /health` returns `{"status": "ok"}`
