# TASK-08: Rewrite orchestrator system prompt

**Phase**: 2 — Agentic Orchestrator  
**Action**: REWRITE  
**File**: `D:\ORBIT\backend\orchestrator_instructions.md`  
**Dependencies**: TASK-06

---

## Read First

- `D:\ORBIT\backend\orchestrator_instructions.md` — current prompt (understand what it does)
- `D:\ORBIT\backend\n8n_nodes_catalog.md` (from TASK-06) — this gets appended dynamically

## Problem

The current prompt tells the LLM to output `{name, summary, steps: [{title, system_prompt}]}` — a simple step list. The workflow builder then mechanically converts these into identical HTTP Request chains.

The new prompt must instruct the LLM to generate **full n8n workflow JSON** with diverse node types.

## Instructions

Completely replace the contents of `D:\ORBIT\backend\orchestrator_instructions.md` with a new system prompt. The prompt must:

1. **Role**: Tell the LLM it is the "Orbit Workflow Architect" that designs n8n automation workflows

2. **Output format**: Return ONLY valid JSON (no markdown fences, no explanation) with this schema:
   ```
   {name, summary, nodes[], connections{}, settings: {executionOrder: "v1"}}
   ```

3. **Mandatory rules**:
   - Always start with a Webhook node (type: `n8n-nodes-base.webhook`, typeVersion 2, responseMode "lastNode")
   - Always end with a Set node named "Format Result" that outputs a `result` field
   - Every node needs: `id` (unique kebab-case), `name`, `type`, `typeVersion`, `position`, `parameters`
   - Node ids must be unique lowercase-kebab-case (e.g., "parse-input", "check-sentiment")
   - Positions: start [0,0], increment x by 220. Branches offset y by ±120

4. **LLM placeholders**: For HTTP Request nodes calling LLMs:
   - url: `REPLACE_LLM_URL`
   - Authorization header: `Bearer REPLACE_LLM_KEY`
   - model field: `REPLACE_LLM_MODEL`

5. **Design principles**:
   - Use the RIGHT node type for the job
   - Code nodes for data transformation
   - IF/Switch for decision points
   - Don't just chain HTTP Request nodes with different prompts
   - 3-8 nodes ideal, max 12

6. **Expression syntax**: Document `={{ }}` prefix rule, `$json.field` access, NEVER use `{{ }}` in regular strings

7. **Code node template**: Show input (`$input.all()`), output (`return [{json: {...}}]`), wrap in try/catch

8. **HTTP Request node for LLM calls**: Show exact parameter structure for typeVersion 4.2 with `sendHeaders`, `headerParameters`, `sendBody`, `specifyBody`, `jsonBody`

The file must be under 3000 tokens. It will be combined with `n8n_nodes_catalog.md` at runtime.

## Acceptance Criteria

- [ ] Prompt instructs LLM to output full n8n workflow JSON
- [ ] Includes mandatory Webhook start and Format Result end rules
- [ ] Documents LLM placeholders (REPLACE_LLM_URL, REPLACE_LLM_KEY, REPLACE_LLM_MODEL)
- [ ] Documents Code node input/output pattern
- [ ] Documents HTTP Request node structure for LLM calls
- [ ] Contains expression syntax reference with `=` prefix rule
- [ ] Under 3000 tokens
- [ ] No markdown code fences in the content itself (the LLM should not be confused)
