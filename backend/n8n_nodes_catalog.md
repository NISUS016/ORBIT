## Key n8n Node Reference

### 1. Webhook (`n8n-nodes-base.webhook`, v2)
Entry point for API workflows. Position [0, 0].
Parameters: `{"httpMethod": "POST", "path": "task-slug", "responseMode": "lastNode"}`

### 2. HTTP Request (`n8n-nodes-base.httpRequest`, v4.2)
External API & LLM calls.
Parameters for LLM call:
```json
{
  "method": "POST",
  "url": "REPLACE_LLM_URL",
  "sendHeaders": true,
  "headerParameters": {"parameters": [
    {"name": "Content-Type", "value": "application/json"},
    {"name": "Authorization", "value": "Bearer REPLACE_LLM_KEY"}
  ]},
  "sendBody": true,
  "specifyBody": "json",
  "jsonBody": "={\n  \"model\": \"REPLACE_LLM_MODEL\",\n  \"messages\": [{\"role\": \"user\", \"content\": \"{{ JSON.stringify($json.body.task) }}\"}]\n}"
}
```

### 3. Code (`n8n-nodes-base.code`, v2)
JavaScript transform.
Parameters: `{"mode": "runOnceForAllItems", "jsCode": "const items = $input.all();\nreturn [{json: {data: items[0].json}}];"}`

### 4. IF (`n8n-nodes-base.if`, v2)
Conditional branching (output 0 = true, output 1 = false).
Parameters: `{"conditions": {"options": {"caseSensitive": true}, "conditions": [{"id": "c1", "leftValue": "={{ $json.status }}", "rightValue": "success", "operator": {"type": "string", "operation": "equals"}, "typeValidation": "loose"}]}}`

### 5. Set (`n8n-nodes-base.set`, v3.4)
Field assignment / formatting result.
Parameters: `{"assignments": {"assignments": [{"id": "a1", "name": "result", "type": "string", "value": "={{ $json.choices[0].message.content }}"}]}}`

### 6. Merge (`n8n-nodes-base.merge`, v3)
Combine parallel branch streams. Parameters: `{"mode": "append"}`

### 7. Google Sheets Trigger (`n8n-nodes-base.googleSheetsTrigger`, v1)
Trigger on row added/updated. Parameters: `{"pollTimes": {"item": [{"mode": "everyMinute"}]}, "event": "rowAdded"}`

### 8. Gmail (`n8n-nodes-base.gmail`, v2)
Send emails. Parameters: `{"resource": "message", "operation": "send", "toEmail": "admin@example.com", "subject": "Alert", "message": "={{ $json.data }}"}`

### 9. Other standard nodes: `n8n-nodes-base.slack`, `n8n-nodes-base.postgres`, `n8n-nodes-base.splitInBatches`, `n8n-nodes-base.switch`, `n8n-nodes-base.wait`, `n8n-nodes-base.noOp`.