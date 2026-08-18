# TASK-13: Update n8n_client.py webhook_url method

**Phase**: 3 — Integration  
**Action**: MODIFY  
**File**: `D:\ORBIT\backend\n8n_client.py`  
**Dependencies**: None

---

## Read First

The entire file. Focus on the `webhook_url()` method in the `N8NClient` class.

## Purpose

Update `webhook_url()` to extract the webhook path from LLM-generated workflow JSON and accept a direct path string from `ensure_unique_webhook()`.

## Instructions

Replace the `webhook_url()` method:

```python
def webhook_url(self, workflow_or_created: dict, default_path: str) -> str:
    """Build the full webhook URL. Tries to extract path from workflow nodes,
    falls back to default_path."""
    base = self.base_url.rstrip("/")
    
    # Try to extract from the workflow's Webhook node
    nodes = workflow_or_created.get("nodes", [])
    for node in nodes:
        if node.get("type") == "n8n-nodes-base.webhook":
            path = node.get("parameters", {}).get("path", "")
            if path:
                return f"{base}/webhook/{path}"
    
    # Fallback to provided path
    if default_path.startswith("http"):
        return default_path
    return f"{base}/webhook/{default_path}"
```

## Acceptance Criteria

- [ ] Extracts webhook path from Webhook node in the workflow JSON
- [ ] Falls back to `default_path` argument
- [ ] Returns full URL with n8n base URL
- [ ] Handles both old and new workflow JSON formats
