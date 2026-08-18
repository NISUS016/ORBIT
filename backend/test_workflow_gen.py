"""test_workflow_gen.py — integration tests for the agentic workflow pipeline.
Run with: python test_workflow_gen.py"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from workflow_validator import validate_workflow, parse_llm_workflow_response


def test_valid_existing_workflows():
    """Existing workflow JSONs should pass validation."""
    print("\n=== Existing Workflow Validation ===")
    workflows_dir = os.path.join(os.path.dirname(__file__), "..", "workflows")
    for fname in sorted(os.listdir(workflows_dir)):
        if fname.endswith(".json"):
            with open(os.path.join(workflows_dir, fname)) as f:
                wf = json.load(f)
            errors = validate_workflow(wf)
            status = "PASS" if not errors else "FAIL"
            print(f"  [{status}] {fname}: {errors or 'OK'}")


def test_invalid_workflows():
    """Invalid workflows should be caught."""
    print("\n=== Invalid Workflow Detection ===")
    cases = [
        ({}, "empty object"),
        ({"nodes": [], "connections": {}}, "no nodes"),
        ({"nodes": [{"name": "X", "type": "fake.type", "position": [0,0], "parameters": {}}], "connections": {}}, "unknown node type"),
        ({"nodes": [
            {"name": "A", "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [0,0], "parameters": {}},
            {"name": "A", "type": "n8n-nodes-base.set", "typeVersion": 3.4, "position": [200,0], "parameters": {}}
        ], "connections": {}}, "duplicate node name"),
    ]
    for wf, desc in cases:
        errors = validate_workflow(wf)
        status = "PASS" if errors else "FAIL"
        print(f"  [{status}] {desc}: caught {len(errors)} error(s)")


def test_parse_llm_response():
    """JSON extraction from LLM responses."""
    print("\n=== LLM Response Parsing ===")
    cases = [
        ('{"nodes": []}', True, "raw JSON"),
        ('```json\n{"nodes": []}\n```', True, "fenced JSON"),
        ('Here is the workflow:\n{"nodes": []}', True, "JSON with preamble"),
        ('no json here', False, "no JSON"),
        ('{"broken": }', False, "invalid JSON"),
    ]
    for text, should_pass, desc in cases:
        result, error = parse_llm_workflow_response(text)
        passed = (result is not None) == should_pass
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {desc}")


def test_fallback_workflow():
    """Fallback workflow should be valid."""
    print("\n=== Fallback Workflow ===")
    from orchestrator import _fallback_workflow
    wf = _fallback_workflow("test task")
    errors = validate_workflow(wf)
    status = "PASS" if not errors else "FAIL"
    print(f"  [{status}] fallback workflow: {errors or 'OK'}")


if __name__ == "__main__":
    test_valid_existing_workflows()
    test_invalid_workflows()
    test_parse_llm_response()
    test_fallback_workflow()
    print("\n=== All tests complete ===")