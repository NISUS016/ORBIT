"""workflow_builder.py — post-processing for LLM-generated n8n workflows.

The LLM (orchestrator.py) designs the full workflow JSON; this module patches
credentials into placeholder nodes, guarantees unique webhook paths, names
spawned workflows, and produces renderable graph summaries for the UI."""

import uuid

import config
from llm_config import patch_llm_node

ALLOWED_WORKFLOW_KEYS = {"name", "nodes", "connections", "settings"}
ALLOWED_NODE_KEYS = {
    "id", "name", "type", "typeVersion", "position", "parameters",
    "webhookId", "credentials", "onError", "disabled", "notes", "notesInFlow",
}


def sanitize_for_n8n(workflow: dict) -> dict:
    """Strip keys n8n's API schema rejects (e.g. 'summary') so that
    POST /api/v1/workflows accepts the payload. Returns a NEW dict."""
    clean = {k: v for k, v in workflow.items() if k in ALLOWED_WORKFLOW_KEYS}
    nodes = clean.get("nodes")
    if isinstance(nodes, list):
        clean["nodes"] = [
            {k: v for k, v in n.items() if k in ALLOWED_NODE_KEYS}
            for n in nodes
            if isinstance(n, dict)
        ]
    return clean


def patch_credentials(workflow: dict, model: str | None = None) -> dict:
    """Patch LLM credentials into every placeholder node. Returns the workflow."""
    for node in workflow.get("nodes", []):
        patch_llm_node(
            node,
            config.get_llm_base_url(),
            config.get_llm_api_key(),
            model or config.get_llm_model(),
        )
    return workflow


def ensure_unique_webhook(workflow: dict) -> str:
    """Make the webhook path unique and return the webhook path string."""
    path = ""
    for node in workflow.get("nodes", []):
        if node.get("type") == "n8n-nodes-base.webhook":
            params = node.setdefault("parameters", {})
            current = str(params.get("path", "") or "")
            if "UNIQUE" in current or not current.strip():
                path = f"factory-{uuid.uuid4().hex[:10]}"
                params["path"] = path
            else:
                path = current
            node.setdefault("webhookId", f"orbit-factory-{uuid.uuid4().hex[:16]}")
            break
    return path


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
