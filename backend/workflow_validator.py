"""workflow_validator.py — structural validation of n8n workflow JSON.

Used to sanity-check LLM-generated workflows before they are pushed to n8n,
plus a parser that extracts JSON from raw LLM responses (markdown fences,
preamble text, etc.). Stdlib only.
"""

import json
import re

CORE_NODE_TYPES = {
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


def is_valid_node_type(ntype: str) -> bool:
    """Check if node type is a valid n8n node type."""
    if not isinstance(ntype, str) or not ntype.strip():
        return False
    if ntype in CORE_NODE_TYPES:
        return True
    # Allow all standard n8n-nodes-base and langchain community nodes
    if ntype.startswith("n8n-nodes-base.") or ntype.startswith("@n8n/") or ntype.startswith("n8n-nodes-langchain."):
        return True
    return False


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
        return errors

    # 2. Minimum nodes: at least 1 node
    if len(nodes) < 1:
        errors.append(f"at least 1 node required, got {len(nodes)}")
        return errors

    # 3. Node structure and valid node types
    node_names = []
    has_trigger_or_webhook = False
    for i, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"node #{i} is not a dict")
            continue
        name = node.get("name")
        if not name:
            errors.append(f"node #{i} missing 'name'")
            continue
        node_names.append(name)
        for field in ("type", "position", "parameters"):
            if field not in node:
                errors.append(f"node {name!r} missing '{field}'")
        position = node.get("position")
        if not (isinstance(position, list) and len(position) == 2):
            errors.append(f"node {name!r} 'position' must be a [x, y] array")
        if not isinstance(node.get("parameters"), dict):
            errors.append(f"node {name!r} 'parameters' must be a dict")
        ntype = node.get("type", "")
        if not is_valid_node_type(ntype):
            errors.append(f"node {name!r} has unknown type {ntype!r}")

        if ntype == "n8n-nodes-base.webhook" or "trigger" in ntype.lower() or "trigger" in name.lower():
            has_trigger_or_webhook = True
            if ntype == "n8n-nodes-base.webhook":
                params = node.get("parameters") or {}
                if not (params.get("path") or "").strip():
                    errors.append(f"webhook node {name!r} must have a non-empty 'path'")

    # 4. No duplicate names
    seen = set()
    for name in node_names:
        if name in seen:
            errors.append(f"duplicate node name {name!r}")
        seen.add(name)

    # 5. Connection validity: all source and target names must exist
    name_set = set(seen)
    for src, outs in connections.items():
        if src not in name_set:
            errors.append(f"connection source {src!r} does not exist in nodes")
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

    return errors


def parse_llm_workflow_response(text: str) -> tuple[dict | None, str]:
    """Extract a workflow JSON object from an LLM response.

    Handles raw JSON, markdown-fenced JSON, and JSON with preamble or reasoning text.
    Returns (parsed_dict, error_string); error is empty on success."""
    if not isinstance(text, str) or not text.strip():
        return None, "empty response"

    content = text.strip()

    # Strip markdown fences if present
    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
    if fenced_match:
        try:
            parsed = json.loads(fenced_match.group(1))
            if isinstance(parsed, dict) and "nodes" in parsed:
                return parsed, ""
        except json.JSONDecodeError:
            pass

    # Try finding JSON object containing "nodes"
    nodes_idx = content.find('"nodes"')
    if nodes_idx != -1:
        # Find opening { before "nodes"
        start = content.rfind("{", 0, nodes_idx)
        if start != -1:
            # Find matching or last closing }
            end = content.rfind("}")
            if end > start:
                candidate = content[start:end + 1]
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict):
                        return parsed, ""
                except json.JSONDecodeError:
                    pass

    # General search: first { to last }
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end > start:
        candidate = content[start:end + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed, ""
        except json.JSONDecodeError as exc:
            return None, f"Invalid JSON: {exc}"

    return None, "No valid JSON workflow object found in response"
