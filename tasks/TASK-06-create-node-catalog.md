# TASK-06: Create the n8n node catalog reference document

**Phase**: 1 — Knowledge Base  
**Action**: NEW FILE  
**File to create**: `D:\ORBIT\backend\n8n_nodes_catalog.md`  
**Dependencies**: None

---

## Read First

- `D:\ORBIT\workflows\02_research_agent.json` — to understand the existing n8n node JSON format
- `D:\ORBIT\backend\workflow_builder.py` — to understand the JSON structure being generated

## Purpose

Create a markdown file that serves as an LLM-consumable reference for n8n workflow generation. This file gets appended to the orchestrator's system prompt so the LLM knows what n8n nodes exist and how to use them.

**CRITICAL**: The file must be under 15KB (~4000 tokens) to fit in the LLM context window alongside the system prompt and user task.

## Instructions

Create `D:\ORBIT\backend\n8n_nodes_catalog.md` with these sections:

### Section 1: Workflow JSON Structure (~500 tokens)

Document the top-level workflow schema:
```json
{"name": "...", "nodes": [...], "connections": {...}, "settings": {"executionOrder": "v1"}}
```

Document the node object schema:
```json
{"id": "unique-id", "name": "Human Name", "type": "n8n-nodes-base.nodeType", "typeVersion": 2, "position": [x, y], "parameters": {...}}
```

Document the connection map schema — explain that connections go from source node name to target, with `main` array where each sub-array represents an output index (important for IF/Switch nodes with multiple outputs).

### Section 2: Available Node Types (~2000 tokens)

Document each of these 10 nodes with their exact type string, typeVersion, purpose, required parameters, and a minimal JSON example:

1. **Webhook** — `n8n-nodes-base.webhook` (typeVersion 2)
   - Entry point. Parameters: `httpMethod: "POST"`, `path: "your-path"`, `responseMode: "lastNode"`
   - Always at position [0, 0]

2. **HTTP Request** — `n8n-nodes-base.httpRequest` (typeVersion 4.2)
   - External API calls. Parameters: `method`, `url`, `sendHeaders`, `headerParameters`, `sendBody`, `specifyBody`, `jsonBody`
   - For LLM calls: use placeholders `REPLACE_LLM_URL`, `Bearer REPLACE_LLM_KEY`, `REPLACE_LLM_MODEL`

3. **Code** — `n8n-nodes-base.code` (typeVersion 2)
   - JavaScript execution. Parameters: `jsCode` (string), `mode` ("runOnceForAllItems")
   - Input: `const items = $input.all();` — each item has `.json` property
   - Output: Must return `[{json: {fieldName: "value"}}]`

4. **IF** — `n8n-nodes-base.if` (typeVersion 2)
   - Conditional branching with 2 outputs. Output 0 = true, Output 1 = false
   - Parameters: `conditions` object with rules array
   - Show the exact conditions structure with operator types (string equals, number greaterThan, etc.)

5. **Switch** — `n8n-nodes-base.switch` (typeVersion 3)
   - Multi-way routing. Each rule creates a numbered output
   - Parameters: `rules.values` array

6. **Set** — `n8n-nodes-base.set` (typeVersion 3.4)
   - Assign/transform data fields
   - Parameters: `assignments.assignments` array with `id`, `name`, `type`, `value`
   - Use for final "Format Result" node

7. **Merge** — `n8n-nodes-base.merge` (typeVersion 3)
   - Combine data from 2 inputs. Parameters: `mode` ("append", "combineBySql", "chooseBranch")

8. **Split In Batches** — `n8n-nodes-base.splitInBatches` (typeVersion 3)
   - Process items in batches. Parameters: `batchSize`
   - Output 0 = next batch, Output 1 = loop done

9. **No Operation** — `n8n-nodes-base.noOp` (typeVersion 1)
   - Pass-through placeholder. No parameters.

10. **Stop And Error** — `n8n-nodes-base.stopAndError` (typeVersion 1)
    - Halt with error. Parameters: `errorMessage`

### Section 3: n8n Expression Syntax (~300 tokens)

- Prefix with `=` to make expressions: `"value": "={{ $json.name }}"`
- Access previous node output: `{{ $json.fieldName }}`
- Access specific node: `{{ $node["Node Name"].json.field }}`
- JavaScript in expressions: `{{ $json.items.length > 5 ? "many" : "few" }}`
- JSON.stringify: `{{ JSON.stringify($json.body) }}`
- CRITICAL: Never use `{{` or `}}` in regular string values, only in `=`-prefixed expressions

### Section 4: Workflow Patterns (~800 tokens)

Include 3 complete, minimal, VALID workflow JSON examples:

**Pattern A: Linear chain**
Webhook → Code (parse input) → HTTP Request (LLM call) → Set (Format Result)

**Pattern B: Conditional branching**
Webhook → Code (analyze) → IF (check condition) → [true: Code (process A)] / [false: Code (process B)] → Merge → Set (Format Result)

**Pattern C: Multi-step LLM pipeline**
Webhook → HTTP Request (LLM step 1) → Code (extract/transform) → HTTP Request (LLM step 2) → Set (Format Result)

Each example must be complete valid JSON that n8n would accept (nodes + connections + settings).

## Acceptance Criteria

- [ ] File exists at `D:\ORBIT\backend\n8n_nodes_catalog.md`
- [ ] File is under 15KB
- [ ] All 10 node types documented with type strings, typeVersions, parameter examples
- [ ] Workflow JSON structure fully explained (nodes, connections, settings)
- [ ] Expression syntax documented with examples
- [ ] At least 3 complete workflow pattern examples
- [ ] No bare `{{ }}` in string literals (only in `=`-prefixed expression values)
