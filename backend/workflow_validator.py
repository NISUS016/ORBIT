"""workflow_validator.py — structural validation of n8n workflow JSON.

Used to sanity-check LLM-generated workflows before they are pushed to n8n,
plus a parser that extracts JSON from raw LLM responses (markdown fences,
preamble text, etc.). Stdlib only.
"""

import json
import re

VALID_NODE_TYPES = {
    "n8n-nodes-base.webhook",
    "n8n-nodes-base.httpRequest",
    "n8n-nodes-base.code",
    "n8n-nodes-base.if",
    "n8n-nodes-base.switch",
    "n8n-nodes-base.set",
    "n8n-nodes-base.merge",
    "n8n-nodes-base.splitInBatches",
    "n8n-nodes-base.noOp",
    "n8n-nodes-base.stopAndError",
    "n8n-nodes-base.errorTrigger",
}


def validate_workflow(workflow: dict) -> list[str]:
    """Validate an n8n workflow dict. Returns a list of error strings;
    an empty list means the workflow is valid."""
    errors: list[str] = []

    if not isinstance(workflow, dict):
        return ["workflow is not a dict"]

    # 1. Top-level structure: must have nodes (list) and connections (dict)
    nodes = workflow.get("nodes")
    connections = workflow.get("connections")
    if not isinstance(nodes, list):
        errors.append("missing or invalid 'nodes' (must be a list)")
        return errors
    if not isinstance(connections, dict):
        errors.append("missing or invalid 'connections' (must be a dict)")

    # 2. Minimum nodes: at least 2 (Webhook + output)
    if len(nodes) < 2:
        errors.append(f"at least 2 nodes required, got {len(nodes)}")

    # 3+4. Node structure and valid node types
    node_names = []
    has_webhook = False
    has_format_result = False
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"node #{i} is not a dict")
            continue
        name = node.get("name")
        node_names.append(name)
        for field in ("name", "type", "position", "parameters"):
            if field not in node:
                errors.append(f"node {name!r} missing '{field}'")
        position = node.get("position")
        if not (isinstance(position, list) and len(position) == 2):
            errors.append(f"node {name!r} 'position' must be a [x, y] array")
        if not isinstance(node.get("parameters"), dict):
            errors.append(f"node {name!r} 'parameters' must be a dict")
        ntype = node.get("type")
        if ntype not in VALID_NODE_TYPES:
            errors.append(f"node {name!r} has unknown type {ntype!r}")
        if ntype == "n8n-nodes-base.webhook":
            params = node.get("parameters") or {}
            if params.get("responseMode") != "lastNode":
                errors.append(f"webhook node {name!r} must have responseMode 'lastNode'")
            if not (params.get("path") or "").strip():
                errors.append(f"webhook node {name!r} must have a non-empty 'path'")
            has_webhook = True
        if name == "Format Result":
            has_format_result = True

    # 5. No duplicate names
    seen = set()
    for name in node_names:
        if name in seen:
            errors.append(f"duplicate node name {name!r}")
        seen.add(name)

    # 6. Webhook required
    if not has_webhook:
        errors.append("workflow must contain at least one webhook node")

    # 7. Format Result required
    if not has_format_result:
        errors.append("workflow must contain a node named 'Format Result'")

    # 8. Connection validity: all source and target names must exist
    name_set = set(seen)
    for src, outs in connections.items():
        if src not in name_set:
            errors.append(f"connection source {src!r} does not exist")
            continue
        mains = outs.get("main") if isinstance(outs, dict) else None
        if not isinstance(mains, list):
            errors.append(f"connection from {src!r} has invalid 'main' structure")
            continue
        for output in mains:
            if not isinstance(output, list):
                continue
            for link in output:
                if isinstance(link, dict) and link.get("node") not in name_set:
                    errors.append(
                        f"connection from {src!r} targets missing node {link.get('node')!r}"
                    )

    # 9. Reachability: all non-webhook nodes need at least one incoming connection
    if isinstance(connections, dict):
        connected = set()
        for outs in connections.values():
            mains = outs.get("main") if isinstance(outs, dict) else None
            if not isinstance(mains, list):
                continue
            for output in mains:
                if isinstance(output, list):
                    for link in output:
                        if isinstance(link, dict) and link.get("node"):
                            connected.add(link["node"])
        for name in node_names:
            if name not in connected:
                # webhook nodes are entry points, everything else must be fed
                node = next((n for n in nodes if n.get("name") == name), {})
                if node.get("type") != "n8n-nodes-base.webhook":
                    errors.append(f"node {name!r} is not reachable (no incoming connection)")

    return errors


def parse_llm_workflow_response(text: str) -> tuple[dict | None, str]:
    """Extract a workflow JSON object from an LLM response.

    Handles raw JSON, markdown-fenced JSON, and JSON with preamble text.
    Returns (parsed_dict, error_string); error is empty on success."""
    if not isinstance(text, str) or not text.strip():
        return None, "empty response"

    content = text.strip()
    # Strip markdown fences (```json ... ```)
    fenced = re.match(r"```(?:json)?\s*(.*?)```", content, re.DOTALL)
    if fenced:
        content = fenced.group(1).strip()

    # Find the first { and the last }
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None, "No JSON object found"

    candidate = content[start:end + 1]
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON: {exc}"
    if not isinstance(parsed, dict):
        return None, "JSON object is not a dict"
    return parsed, ""
