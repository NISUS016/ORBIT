# TASK-11: Update llm_config.py patch function for new HTTP Request format

**Phase**: 2 — Agentic Orchestrator  
**Action**: MODIFY  
**File**: `D:\ORBIT\backend\llm_config.py`  
**Dependencies**: None

---

## Read First

The entire file. Focus on the `patch_llm_node()` function.

## Problem

The current `patch_llm_node()` only handles typeVersion 2 HTTP Request nodes with `bodyParametersJson` and `headerParametersJson` string fields. The new LLM-generated workflows use typeVersion 4.2 with `headerParameters`, `jsonBody`, etc.

## Instructions

Update `patch_llm_node()` to handle BOTH formats:

```python
def patch_llm_node(node: dict, base_url: str, api_key: str, model: str):
    """Patch LLM credential placeholders in an HTTP Request node.
    Handles both old (typeVersion 2) and new (typeVersion 4+) formats."""
    if node.get("type") != "n8n-nodes-base.httpRequest":
        return
    
    params = node.get("parameters", {})
    
    # Patch URL
    if params.get("url") == "REPLACE_LLM_URL":
        params["url"] = f"{base_url.rstrip('/')}/chat/completions"
    
    # Old format (typeVersion 2): string-based fields
    for field in ("headerParametersJson", "bodyParametersJson"):
        if field in params and isinstance(params[field], str):
            params[field] = params[field].replace("REPLACE_LLM_KEY", api_key)
            params[field] = params[field].replace("REPLACE_LLM_MODEL", model)
    
    # New format (typeVersion 4+): structured fields
    header_params = params.get("headerParameters", {})
    if isinstance(header_params, dict):
        for p in header_params.get("parameters", []):
            if isinstance(p, dict) and isinstance(p.get("value"), str):
                p["value"] = p["value"].replace("REPLACE_LLM_KEY", api_key)
    
    json_body = params.get("jsonBody")
    if isinstance(json_body, str):
        params["jsonBody"] = json_body.replace("REPLACE_LLM_MODEL", model)
        params["jsonBody"] = params["jsonBody"].replace("REPLACE_LLM_KEY", api_key)
    
    # Normalize old requestMethod to method
    if "requestMethod" in params and "method" not in params:
        params["method"] = params.pop("requestMethod")
```

Keep the rest of the file unchanged.

## Acceptance Criteria

- [ ] Handles typeVersion 2 nodes (old: `headerParametersJson`/`bodyParametersJson`)
- [ ] Handles typeVersion 4+ nodes (new: `headerParameters`/`jsonBody`)
- [ ] Replaces `REPLACE_LLM_URL` with `{base_url}/chat/completions`
- [ ] Replaces `REPLACE_LLM_KEY` and `REPLACE_LLM_MODEL` in all parameter locations
- [ ] Does nothing for non-httpRequest nodes
- [ ] Existing deploy.py still works with old workflow JSONs
