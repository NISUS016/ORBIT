# TASK-04: Fix error handling in n8n_client.py

**Phase**: 0 — Bug Fix  
**Action**: MODIFY  
**File**: `D:\ORBIT\backend\n8n_client.py`  
**Dependencies**: None

---

## Read First

The entire file. Focus on `create_workflow()`, `activate()`, `call_webhook()`, and `call_spawned()`.

## Problem

- `create_workflow()` and `activate()` don't check HTTP status codes
- `call_webhook()` and `call_spawned()` call `resp.json()` without handling `JSONDecodeError` — crashes if n8n returns an HTML error page

## Instructions

Add `import json` at the top if not already present.

### Step 1: Fix `create_workflow()`

After the POST call, add:

```python
resp.raise_for_status()
```

Wrap the `resp.json()` call:

```python
try:
    return resp.json()
except (json.JSONDecodeError, ValueError):
    return {"error": f"n8n returned non-JSON response (HTTP {resp.status_code}): {resp.text[:200]}"}
```

### Step 2: Fix `activate()`

Add `resp.raise_for_status()` after the POST call. Wrap in try/except `httpx.HTTPStatusError`:

```python
try:
    resp = await self.client.post(...)
    resp.raise_for_status()
    return resp.json()
except httpx.HTTPStatusError as e:
    print(f"[n8n_client] activate failed: {e}")
    return {"error": str(e)}
```

### Step 3: Fix `call_webhook()` and `call_spawned()`

Wrap every `resp.json()` call in:

```python
try:
    data = resp.json()
except (json.JSONDecodeError, ValueError):
    return f"n8n error (HTTP {resp.status_code}): {resp.text[:200]}", resp.status_code
```

## Acceptance Criteria

- [ ] `create_workflow()` raises on HTTP errors, handles JSON decode failures
- [ ] `activate()` raises on HTTP errors with descriptive messages
- [ ] `call_webhook()` handles non-JSON responses gracefully
- [ ] `call_spawned()` handles non-JSON responses gracefully
- [ ] Error messages include HTTP status codes and partial response bodies
