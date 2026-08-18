# n8n Nodes Reference — Orbit Workflow Architect

Reference for building valid n8n workflow JSON. Every workflow you design must
follow this structure and use ONLY the node types below.

## 1. Workflow JSON Structure

Top-level workflow object:

```json
{
  "name": "Workflow Name (human readable)",
  "nodes": [ ... ],
  "connections": { ... },
  "settings": { "executionOrder": "v1" }
}
```

Each node object:

```json
{
  "id": "unique-kebab-case-id",
  "name": "Human-readable Node Name",
  "type": "n8n-nodes-base.nodeType",
  "typeVersion": 2,
  "position": [0, 0],
  "parameters": { ... }
}
```

Connections map: key = source node NAME, value = `{"main": [...]}`. The `main`
array contains one sub-array per OUTPUT INDEX of the source node. Most nodes
have exactly one output: `"main": [[{"node": "Target", "type": "main", "index": 0}]]`.
IF has TWO outputs: sub-array 0 = true, sub-array 1 = false. Switch has one
sub-array per rule.

## 2. Available Node Types

### Webhook — `n8n-nodes-base.webhook` (typeVersion 2)
Workflow ENTRY POINT. Always the first node, always at position [0, 0].
Parameters: `httpMethod: "POST"`, `path: "your-path"` (unique, lowercase), `responseMode: "lastNode"`.
```json
{"id": "webhook", "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [0, 0], "parameters": {"httpMethod": "POST", "path": "my-task", "responseMode": "lastNode"}}
```

### HTTP Request — `n8n-nodes-base.httpRequest` (typeVersion 4.2)
External API calls (including LLM calls). Parameters: `method`, `url`, `sendHeaders`,
`headerParameters`, `sendBody`, `specifyBody`, `jsonBody`. For LLM calls use
placeholders: url = `REPLACE_LLM_URL`, Authorization header value = `Bearer REPLACE_LLM_KEY`,
model field in body = `REPLACE_LLM_MODEL`. See section 5 for the full LLM node template.

### Code — `n8n-nodes-base.code` (typeVersion 2)
JavaScript transformation. Parameters: `mode: "runOnceForAllItems"`, `jsCode` (string).
Input: `const items = $input.all();` — each item has a `.json` property.
Output: MUST `return [{json: {field: "value"}}]`.
```json
{"parameters": {"mode": "runOnceForAllItems", "jsCode": "const items = $input.all();\nconst t = items[0].json;\nreturn [{json: {clean: String(t.text || \"\").trim()}}];"}}
```

### IF — `n8n-nodes-base.if` (typeVersion 2)
Conditional branch, 2 outputs (0 = true, 1 = false).
Parameters: `conditions: {"options": {"caseSensitive": true}, "conditions": [{"id": "c1", "leftValue": "={{ $json.field }}", "rightValue": "value", "operator": {"type": "string", "operation": "equals"}, "typeValidation": "loose"}]}`.
Operators: string: equals/notEquals/contains/notContains/startsWith/endsWith;
number: gt/lt/gte/lte. Connect both outputs onward.

### Switch — `n8n-nodes-base.switch` (typeVersion 3)
Multi-way routing. Parameters: `dataType: "string"`, `rules: {"values": [{"id": "r1", "value": "a", "type": "string", "outputIndex": 0}, ...]}`.
Each rule creates a numbered output (outputIndex 0, 1, 2...). Connect outputs
per rule.

### Set — `n8n-nodes-base.set` (typeVersion 3.4)
Assign/transform fields. Parameters: `assignments: {"assignments": [{"id": "a1", "name": "result", "type": "string", "value": "={{ $json.field }}"}]}`.
Use as the FINAL "Format Result" node: name the node exactly `Format Result` and
set a `result` field equal to the answer.

### Merge — `n8n-nodes-base.merge` (typeVersion 3)
Combine 2 inputs. Parameters: `mode: "append"` (also "combineBySql", "chooseBranch").
Required if a workflow branches and must converge into one stream before Format Result.

### Split In Batches — `n8n-nodes-base.splitInBatches` (typeVersion 3)
Process items in batches. Parameters: `batchSize: 5` (number). Output 0 = next batch,
output 1 = loop done (connect it to what runs after all batches).

### No Operation — `n8n-nodes-base.noOp` (typeVersion 1)
Pass-through. No parameters. Use as placeholder for unused branch outputs.

### Stop And Error — `n8n-nodes-base.stopAndError` (typeVersion 1)
Halt with error. Parameters: `errorMessage` (string). Use after IF false-branch
when a workflow must fail loudly on bad input.

## 3. n8n Expression Syntax

- Prefix a string value with `=` to make it an expression: `"value": "={{ $json.name }}"`.
- Previous node's output: `{{ $json.fieldName }}`.
- A specific node's output: `{{ $node["Node Name"].json.field }}`.
- JavaScript inside expressions: `{{ $json.items.length > 5 ? "many" : "few" }}`.
- JSON.stringify: `{{ JSON.stringify($json.body) }}`.
- CRITICAL: never use `{{` or `}}` inside a regular (non-expression) string
  value — only inside values prefixed with `=`.

## 4. Workflow Patterns

### Pattern A: Linear chain
```json
{"name": "Linear QA", "nodes": [
{"id": "webhook", "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [0, 0], "parameters": {"httpMethod": "POST", "path": "linear-qa", "responseMode": "lastNode"}},
{"id": "parse", "name": "Parse Input", "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [220, 0], "parameters": {"mode": "runOnceForAllItems", "jsCode": "const items = $input.all();\nreturn [{json: {question: String(items[0].json.body.task || \"\")}}];"}},
{"id": "llm", "name": "Ask LLM", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [440, 0], "parameters": {"method": "POST", "url": "REPLACE_LLM_URL", "sendHeaders": true, "headerParameters": {"parameters": [{"name": "Content-Type", "value": "application/json"}, {"name": "Authorization", "value": "Bearer REPLACE_LLM_KEY"}]}, "sendBody": true, "specifyBody": "json", "jsonBody": "={\n  \"model\": \"REPLACE_LLM_MODEL\",\n  \"messages\": [{\"role\": \"user\", \"content\": \"{{ $json.question }}\"}]\n}"}},
{"id": "format", "name": "Format Result", "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [660, 0], "parameters": {"assignments": {"assignments": [{"id": "a1", "name": "result", "type": "string", "value": "={{ $json.choices[0].message.content }}"}]}}}
], "connections": {"Webhook": {"main": [[{"node": "Parse Input", "type": "main", "index": 0}]]}, "Parse Input": {"main": [[{"node": "Ask LLM", "type": "main", "index": 0}]]}, "Ask LLM": {"main": [[{"node": "Format Result", "type": "main", "index": 0}]]}}, "settings": {"executionOrder": "v1"}}
```

### Pattern B: Conditional branching
```json
{"name": "Branching QA", "nodes": [
{"id": "webhook", "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [0, 0], "parameters": {"httpMethod": "POST", "path": "branch-qa", "responseMode": "lastNode"}},
{"id": "analyze", "name": "Analyze", "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [220, 0], "parameters": {"mode": "runOnceForAllItems", "jsCode": "const items = $input.all();\nconst task = String(items[0].json.body.task || \"\");\nreturn [{json: {urgent: task.toLowerCase().includes(\"asap\"), text: task}}];"}},
{"id": "check", "name": "Is Urgent?", "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [440, 0], "parameters": {"conditions": {"options": {"caseSensitive": true}, "conditions": [{"id": "c1", "leftValue": "={{ $json.urgent }}", "rightValue": "true", "operator": {"type": "boolean", "operation": "true"}, "typeValidation": "loose"}]}}},
{"id": "quick", "name": "Quick Path", "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [660, -120], "parameters": {"mode": "runOnceForAllItems", "jsCode": "const items = $input.all();\nreturn [{json: {out: \"URGENT: \" + items[0].json.text}}];"}},
{"id": "deep", "name": "Deep Path", "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [660, 120], "parameters": {"mode": "runOnceForAllItems", "jsCode": "const items = $input.all();\nreturn [{json: {out: \"NORMAL: \" + items[0].json.text}}];"}},
{"id": "merge", "name": "Merge", "type": "n8n-nodes-base.merge", "typeVersion": 3, "position": [880, 0], "parameters": {"mode": "append"}},
{"id": "format", "name": "Format Result", "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [1100, 0], "parameters": {"assignments": {"assignments": [{"id": "a1", "name": "result", "type": "string", "value": "={{ $json.out }}"}]}}}
], "connections": {"Webhook": {"main": [[{"node": "Analyze", "type": "main", "index": 0}]]}, "Analyze": {"main": [[{"node": "Is Urgent?", "type": "main", "index": 0}]]}, "Is Urgent?": {"main": [[{"node": "Quick Path", "type": "main", "index": 0}], [{"node": "Deep Path", "type": "main", "index": 0}]]}, "Quick Path": {"main": [[{"node": "Merge", "type": "main", "index": 0}]]}, "Deep Path": {"main": [[{"node": "Merge", "type": "main", "index": 1}]]}, "Merge": {"main": [[{"node": "Format Result", "type": "main", "index": 0}]]}}, "settings": {"executionOrder": "v1"}}
```

### Pattern C: Multi-step LLM pipeline
```json
{"name": "Two LLM Steps", "nodes": [
{"id": "webhook", "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [0, 0], "parameters": {"httpMethod": "POST", "path": "multi-llm", "responseMode": "lastNode"}},
{"id": "llm1", "name": "LLM Step 1", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [220, 0], "parameters": {"method": "POST", "url": "REPLACE_LLM_URL", "sendHeaders": true, "headerParameters": {"parameters": [{"name": "Content-Type", "value": "application/json"}, {"name": "Authorization", "value": "Bearer REPLACE_LLM_KEY"}]}, "sendBody": true, "specifyBody": "json", "jsonBody": "={\n  \"model\": \"REPLACE_LLM_MODEL\",\n  \"messages\": [{\"role\": \"user\", \"content\": \"{{ JSON.stringify($json.body.task) }}\"}]\n}"}},
{"id": "extract", "name": "Extract Text", "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [440, 0], "parameters": {"mode": "runOnceForAllItems", "jsCode": "const items = $input.all();\nlet text = \"\";\nfor (const it of items) { if (it.json && it.json.choices) text += it.json.choices[0].message.content; }\nreturn [{json: {draft: text}}];"}},
{"id": "llm2", "name": "LLM Step 2", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [660, 0], "parameters": {"method": "POST", "url": "REPLACE_LLM_URL", "sendHeaders": true, "headerParameters": {"parameters": [{"name": "Content-Type", "value": "application/json"}, {"name": "Authorization", "value": "Bearer REPLACE_LLM_KEY"}]}, "sendBody": true, "specifyBody": "json", "jsonBody": "={\n  \"model\": \"REPLACE_LLM_MODEL\",\n  \"messages\": [{\"role\": \"user\", \"content\": \"Polish this draft:\\n{{ $json.draft }}\"}]\n}"}},
{"id": "format", "name": "Format Result", "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [880, 0], "parameters": {"assignments": {"assignments": [{"id": "a1", "name": "result", "type": "string", "value": "={{ $json.choices[0].message.content }}"}]}}}
], "connections": {"Webhook": {"main": [[{"node": "LLM Step 1", "type": "main", "index": 0}]]}, "LLM Step 1": {"main": [[{"node": "Extract Text", "type": "main", "index": 0}]]}, "Extract Text": {"main": [[{"node": "LLM Step 2", "type": "main", "index": 0}]]}, "LLM Step 2": {"main": [[{"node": "Format Result", "type": "main", "index": 0}]]}}, "settings": {"executionOrder": "v1"}}
```

## 5. HTTP Request Node for LLM Calls (typeVersion 4.2)

Exact structure — always use placeholders, never real credentials:

```json
{"type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "parameters": {
  "method": "POST",
  "url": "REPLACE_LLM_URL",
  "sendHeaders": true,
  "headerParameters": {"parameters": [
    {"name": "Content-Type", "value": "application/json"},
    {"name": "Authorization", "value": "Bearer REPLACE_LLM_KEY"}
  ]},
  "sendBody": true,
  "specifyBody": "json",
  "jsonBody": "={\n  \"model\": \"REPLACE_LLM_MODEL\",\n  \"messages\": [{\"role\": \"user\", \"content\": \"...\"}]\n}"
}}
```