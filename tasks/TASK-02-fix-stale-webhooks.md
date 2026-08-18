# TASK-02: Fix stale webhook snapshot in config.py and routes.py

**Phase**: 0 — Bug Fix  
**Action**: MODIFY  
**Files**:
- `D:\ORBIT\backend\config.py`
- `D:\ORBIT\backend\routes.py`

**Dependencies**: None

---

## Read First

Both files. In `config.py`, find the line `WEBHOOKS = get_webhooks()` (evaluated once at import time). In `routes.py`, find `if task_type in config.WEBHOOKS`.

## Problem

`config.WEBHOOKS` is set once when the module is imported. Runtime webhook updates (via deploy or UI settings) are silently ignored until the server restarts.

## Instructions

### Step 1: Add live accessor in `config.py`

Keep the existing `WEBHOOKS = ...` line (don't break anything that reads it at startup). Add a new function:

```python
def get_webhooks_live() -> dict:
    """Always returns the CURRENT webhooks from credentials.json.
    Use this instead of the WEBHOOKS constant for runtime access."""
    from providers import get_webhooks
    return get_webhooks()
```

### Step 2: Update `routes.py`

In the `chat_stream()` function, find:

```python
if task_type in config.WEBHOOKS and config.WEBHOOKS[task_type]:
```

Replace with:

```python
webhooks = config.get_webhooks_live()
if task_type in webhooks and webhooks[task_type]:
```

Also update the `call_webhook()` call on the next line to use `webhooks[task_type]` instead of `config.WEBHOOKS[task_type]`.

## Acceptance Criteria

- [ ] `config.get_webhooks_live()` function exists and returns fresh data
- [ ] `routes.py` uses `config.get_webhooks_live()` instead of `config.WEBHOOKS`
- [ ] No circular import issues (the `from providers` import is inside the function)
- [ ] Webhook changes at runtime are immediately reflected
