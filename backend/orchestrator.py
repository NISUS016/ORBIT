"""orchestrator.py â€” the LLM brain: task classification + specialist
workflow design for novel tasks. Structured by orchestrator_instructions.md."""

import json
import os

from config import get_llm_client

FALLBACK_PROMPT = "You are a helpful AI assistant. Complete the given task as best you can."

_guide_path = os.path.join(os.path.dirname(__file__), "orchestrator_instructions.md")
with open(_guide_path, encoding="utf-8") as _guide:
    ORCHESTRATOR_GUIDE = _guide.read()


def classify_task(message: str, model: str) -> str:
    """Ask the LLM to classify the task into research/summarizer/extractor/novel."""
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
        max_tokens=5,
    )
    return resp.choices[0].message.content.strip().lower()


def design_agent(task: str, model: str) -> dict:
    """Ask the LLM (guided by ORCHESTRATOR_GUIDE) to design a NEW specialist
    workflow for a novel task.

    Returns {"name", "summary", "steps": [{"title", "system_prompt"}]}.
    Any parse failure falls back to a single generic step so the factory
    can still produce a working workflow."""
    try:
        resp = get_llm_client().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": ORCHESTRATOR_GUIDE},
                {"role": "user", "content": task},
            ],
            max_tokens=900,
            response_format={"type": "json_object"},
        )
        text = resp.choices[0].message.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        spec = json.loads(text)
    except Exception:
        spec = {}

    if not isinstance(spec, dict):
        spec = {}

    def _s(key: str) -> str:
        return str(spec.get(key, "") or "").strip()

    steps = spec.get("steps") if isinstance(spec.get("steps"), list) else None
    if not steps:
        prompt = _s("system_prompt")
        steps = [{"title": "Agent", "system_prompt": prompt or FALLBACK_PROMPT}]

    clean = []
    for s in steps:
        if not isinstance(s, dict):
            continue
        title = str(s.get("title") or "Agent").strip()
        prompt = str(s.get("system_prompt") or s.get("content") or "").strip()
        if not prompt:
            prompt = FALLBACK_PROMPT
        clean.append({"title": title[:40], "system_prompt": prompt[:400]})
        if len(clean) == 4:
            break
    if not clean:
        clean = [{"title": "Agent", "system_prompt": FALLBACK_PROMPT}]

    return {
        "name": _s("name") or "Factory Agent",
        "summary": _s("summary"),
        "steps": clean,
    }