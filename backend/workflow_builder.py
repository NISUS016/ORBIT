"""workflow_builder.py — assembles a brand-new n8n workflow JSON from an
LLM-produced agent design: Webhook -> LLM step 1 -> ... -> LLM step N ->
Format Result. Each step is its own LLM HTTP Request node."""

import json
import uuid

import config
from llm_config import patch_llm_node


def build_workflow(spec: dict, model: str | None = None) -> dict:
    """Turns an agent design spec into an n8n workflow JSON.

    spec: {"name", "summary", "steps": [{"title", "system_prompt"}, ...]}
    model: per-request model to patch into the LLM nodes; defaults to the
    provider's configured model.
    """
    steps = spec["steps"]
    uid = uuid.uuid4().hex[:10]

    nodes = [{
        "parameters": {
            "httpMethod": "POST",
            "path": f"factory-{uid}",
            "responseMode": "lastNode",
        },
        "id": f"orbit-{uid}-webhook",
        "name": "Webhook",
        "type": "n8n-nodes-base.webhook",
        "typeVersion": 2,
        "position": [0, 0],
        "webhookId": f"orbit-factory-{uuid.uuid4().hex[:16]}",
    }]
    connections = {}

    prev = "Webhook"
    for i, step in enumerate(steps, start=1):
        title = f"Step {i}: {step['title']}"
        system = step["system_prompt"].replace("{{", "(").replace("}}", ")")
        # JSON.stringify keeps multi-line/quoted model output valid inside the JSON body
        user_input = (
            "{{ JSON.stringify($json.body.task) }}"
            if i == 1
            else "{{ JSON.stringify($json.choices[0].message.content) }}"
        )
        body = "=" + json.dumps({
            "model": "REPLACE_LLM_MODEL",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_input},
            ],
        }, indent=2)
        # content is an expression, not a literal string — unquote it
        body = body.replace('"content": "%s"' % user_input, f'"content": {user_input}')
        nodes.append({
            "parameters": {
                "requestMethod": "POST",
                "url": "REPLACE_LLM_URL",
                "responseFormat": "json",
                "jsonParameters": True,
                "headerParametersJson": "{\n  \"Content-Type\": \"application/json\",\n  \"Authorization\": \"Bearer REPLACE_LLM_KEY\"\n}",
                "bodyParametersJson": body,
                "options": {},
            },
            "id": f"orbit-{uid}-llm{i}",
            "name": title,
            "type": "n8n-nodes-base.httpRequest",
            "typeVersion": 2,
            "position": [220 * i, 60 * (i % 2)],
        })
        connections[prev] = {"main": [[{"node": title, "type": "main", "index": 0}]]}
        prev = title

    nodes.append({
        "parameters": {
            "assignments": {
                "assignments": [{
                    "id": f"orbit-{uid}-result",
                    "name": "result",
                    "type": "string",
                    "value": "={{ $json.choices[0].message.content }}",
                }]
            }
        },
        "id": f"orbit-{uid}-set",
        "name": "Format Result",
        "type": "n8n-nodes-base.set",
        "typeVersion": 3.4,
        "position": [220 * (len(steps) + 1), 0],
    })
    connections[prev] = {"main": [[{"node": "Format Result", "type": "main", "index": 0}]]}

    workflow_json = {
        "name": "06 - Factory Agent",
        "nodes": nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1"},
    }
    for node in nodes:
        patch_llm_node(
            node,
            config.get_llm_base_url(),
            config.get_llm_api_key(),
            model or config.get_llm_model(),
        )
    return workflow_json


def name_for_task(design_name: str, task: str) -> str:
    """Name each spawned workflow after its agent + task root so it's
    visible/unique in n8n."""
    label = " ".join(task.split()[:5]).translate({ord(c): None for c in '"\\/\n\t'})[:45]
    return f"06 - {design_name} · {label}"


def graph_summary(workflow: dict) -> dict:
    """Renderable view of the workflow for the artifact window:
    strips prompt bodies, keeps node identity, position and type."""
    nodes = [
        {
            "id": n.get("id", ""),
            "name": n.get("name", ""),
            "type": n.get("type", ""),
            "position": n.get("position", [0, 0]),
        }
        for n in workflow.get("nodes", [])
    ]
    return {
        "nodes": nodes,
        "connections": workflow.get("connections", {}),
    }