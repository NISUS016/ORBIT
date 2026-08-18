# TASK-07: Create a workflow validation module

**Phase**: 1 — Knowledge Base  
**Action**: NEW FILE  
**File to create**: `D:\ORBIT\backend\workflow_validator.py`  
**Dependencies**: TASK-06

---

## Read First

- `D:\ORBIT\backend\n8n_nodes_catalog.md` (from TASK-06) — to know valid node types
- `D:\ORBIT\workflows\02_research_agent.json` — a valid workflow example

## Purpose

Create a validation module that checks LLM-generated n8n workflow JSON for structural correctness before deploying to n8n. Also includes a parser for extracting JSON from LLM responses that may include markdown fences or preamble text.

## Instructions

Create `D:\ORBIT\backend\workflow_validator.py` with two main functions:

### Function 1: `validate_workflow(workflow: dict) -> list[str]`

Validates an n8n workflow dict. Returns a list of error strings. Empty list means valid.

Checks to perform:
1. **Top-level structure**: Must have `nodes` (list) and `connections` (dict)
2. **Minimum nodes**: At least 2 nodes (Webhook + output)
3. **Node structure**: Each node must have `name`, `type`, `position` ([x,y] array), `parameters` (dict)
4. **Valid node types**: `type` must be one of the 10+1 valid types:
   - `n8n-nodes-base.webhook`, `n8n-nodes-base.httpRequest`, `n8n-nodes-base.code`, `n8n-nodes-base.if`, `n8n-nodes-base.switch`, `n8n-nodes-base.set`, `n8n-nodes-base.merge`, `n8n-nodes-base.splitInBatches`, `n8n-nodes-base.noOp`, `n8n-nodes-base.stopAndError`, `n8n-nodes-base.errorTrigger`
5. **No duplicate names**: Node names must be unique
6. **Webhook required**: At least one `n8n-nodes-base.webhook` node must exist with `responseMode: "lastNode"` and a non-empty `path`
7. **Format Result required**: A node named "Format Result" must exist
8. **Connection validity**: All source and target node names in connections must reference existing nodes
9. **Reachability**: All non-webhook nodes should be reachable (have at least one incoming connection)

### Function 2: `parse_llm_workflow_response(text: str) -> tuple[dict | None, str]`

Extracts JSON from an LLM response. Returns `(parsed_dict, error_string)`. Error is empty on success.

Must handle:
- Raw JSON: `{"nodes": [...]}`
- Fenced JSON: ` ```json\n{...}\n``` `
- JSON with preamble: `Here is the workflow:\n{...}`
- Invalid JSON: return `(None, "error message")`
- Non-JSON: return `(None, "No JSON object found")`

Strip markdown fences, find the first `{` and last `}`, try `json.loads()`.

### Constants

Define `VALID_NODE_TYPES` as a set of all valid type strings.

### Dependencies

Only stdlib: `json`, `re`. No external packages.

## Acceptance Criteria

- [ ] File exists at `D:\ORBIT\backend\workflow_validator.py`
- [ ] `validate_workflow()` returns empty list for `D:\ORBIT\workflows\02_research_agent.json`
- [ ] Catches: missing nodes/connections, unknown types, duplicate names, no webhook, unreachable nodes, no Format Result
- [ ] `parse_llm_workflow_response()` handles raw JSON, fenced JSON, JSON with preamble, invalid JSON, and no-JSON
- [ ] All functions have docstrings
- [ ] No external dependencies
