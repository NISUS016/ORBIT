"""orchestrator.py — the LLM brain: task classification + agentic n8n
workflow design for novel tasks.

design_workflow() runs a generate -> validate -> feed-errors-back loop so the
LLM iterates until it produces a structurally valid workflow (or falls back
to a guaranteed-valid 3-node skeleton).
"""

import asyncio
import json
import os
import time
import uuid

from config import get_llm_client
from workflow_validator import parse_llm_workflow_response, validate_workflow

_guide_path = os.path.join(os.path.dirname(__file__), "orchestrator_instructions.md")
_catalog_path = os.path.join(os.path.dirname(__file__), "n8n_nodes_catalog.md")

with open(_guide_path, encoding="utf-8") as _guide:
    SYSTEM_PROMPT = _guide.read()

with open(_catalog_path, encoding="utf-8") as _catalog:
    NODE_CATALOG = _catalog.read()

FULL_SYSTEM_PROMPT = SYSTEM_PROMPT + "\n\n" + NODE_CATALOG


def classify_task(message: str, model: str) -> str:
    """Ask the LLM to classify the task into research/summarizer/extractor/novel."""
    try:
        resp = get_llm_client().chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify the user's task into exactly one of these: "
                        "research, summarizer, extractor, novel. "
                        "- research: find info, look something up, current events\n"
                        "- summarizer: shorten/condense/summarize text\n"
                        "- extractor: pull out fields/data from text\n"
                        "- novel: anything else\n"
                        "Reply with ONLY the one word, lowercase."
                    ),
                },
                {"role": "user", "content": message},
            ],
            max_tokens=20,
        )
        result = resp.choices[0].message.content.strip().lower()
        # Fuzzy match
        for category in ("research", "summarizer", "extractor"):
            if category in result:
                return category
        return "novel"
    except Exception as e:
        print(f"[orchestrator] classify_task error: {e}")
        return "novel"


async def classify_task_async(message: str, model: str) -> str:
    """Non-blocking wrapper around classify_task."""
    return await asyncio.to_thread(classify_task, message, model)


def design_workflow(task: str, model: str, max_attempts: int = 3) -> tuple[dict, list[str]]:
    """Agentic loop: LLM designs a full n8n workflow JSON, we validate it and
    feed errors back until it's valid or attempts run out.

    Returns (workflow_dict, generation_log) where log lists each attempt."""
    messages = [
        {"role": "system", "content": FULL_SYSTEM_PROMPT},
        {"role": "user", "content": f"Task description:\n{task}\n\nGenerate the complete n8n workflow JSON for this task."},
    ]
    log: list[str] = []

    for attempt in range(1, max_attempts + 1):
        try:
            resp = get_llm_client().chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=3500,
                temperature=0.2,
            )
            text = resp.choices[0].message.content or ""
        except Exception as e:
            err_str = str(e)
            log.append(f"attempt {attempt}: LLM call failed ({err_str[:120]})")
            if "rate_limit" in err_str.lower() or "429" in err_str or "413" in err_str:
                time.sleep(2.0)
            continue

        workflow, parse_error = parse_llm_workflow_response(text)
        if parse_error:
            log.append(f"attempt {attempt}: parse failed — {parse_error}")
            messages = [
                {"role": "system", "content": FULL_SYSTEM_PROMPT},
                {"role": "user", "content": f"Task: {task}\n\nYour previous response was not valid JSON. Error: {parse_error}. Please output ONLY a valid JSON object with name, nodes, connections, settings."},
            ]
            continue

        errors = validate_workflow(workflow)
        if not errors:
            log.append(f"attempt {attempt}: valid workflow ({len(workflow.get('nodes', []))} nodes)")
            workflow.setdefault("name", "Factory Agent")
            workflow.setdefault("summary", "")
            workflow.setdefault("settings", {"executionOrder": "v1"})
            return workflow, log

        log.append(f"attempt {attempt}: validation failed — {'; '.join(errors)}")
        messages = [
            {"role": "system", "content": FULL_SYSTEM_PROMPT},
            {"role": "user", "content": f"Task: {task}\n\nYour workflow had validation issues:\n- " + "\n- ".join(errors) + "\n\nPlease fix these and return the corrected complete JSON workflow object."},
        ]

    log.append("max attempts reached — using fallback workflow")
    return _fallback_workflow(task), log


async def design_workflow_async(task: str, model: str, max_attempts: int = 3):
    """Non-blocking wrapper around design_workflow."""
    return await asyncio.to_thread(design_workflow, task, model, max_attempts)


def _fallback_workflow(task: str) -> dict:
    """Guaranteed-valid 3-node skeleton: Webhook -> LLM -> Format Result.
    Must pass validate_workflow()."""
    uid = uuid.uuid4().hex[:10]
    label = " ".join(task.split()[:5])[:45]
    webhook_path = f"factory-{uid}"
    return {
        "name": f"06 - Factory Agent · {label}",
        "summary": f"Fallback single-LLM agent for: {task[:100]}",
        "nodes": [
            {
                "id": f"orbit-{uid}-webhook",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [0, 0],
                "parameters": {
                    "httpMethod": "POST",
                    "path": webhook_path,
                    "responseMode": "lastNode",
                },
                "webhookId": f"orbit-factory-{uuid.uuid4().hex[:16]}",
            },
            {
                "id": f"orbit-{uid}-llm",
                "name": "LLM Call",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.2,
                "position": [220, 0],
                "parameters": {
                    "method": "POST",
                    "url": "REPLACE_LLM_URL",
                    "sendHeaders": True,
                    "headerParameters": {"parameters": [
                        {"name": "Content-Type", "value": "application/json"},
                        {"name": "Authorization", "value": "Bearer REPLACE_LLM_KEY"},
                    ]},
                    "sendBody": True,
                    "specifyBody": "json",
                    "jsonBody": (
                        "={\n  \"model\": \"REPLACE_LLM_MODEL\",\n  \"messages\": "
                        "[{\"role\": \"user\", \"content\": \"Task: {{ JSON.stringify($json.body.task) }}\"}]\n}"
                    ),
                },
            },
            {
                "id": f"orbit-{uid}-set",
                "name": "Format Result",
                "type": "n8n-nodes-base.set",
                "typeVersion": 3.4,
                "position": [440, 0],
                "parameters": {
                    "assignments": {"assignments": [
                        {
                            "id": f"orbit-{uid}-result",
                            "name": "result",
                            "type": "string",
                            "value": "={{ $json.choices[0].message.content }}",
                        }
                    ]}
                },
            },
        ],
        "connections": {
            "Webhook": {"main": [[{"node": "LLM Call", "type": "main", "index": 0}]]},
            "LLM Call": {"main": [[{"node": "Format Result", "type": "main", "index": 0}]]},
        },
        "settings": {"executionOrder": "v1"},
    }