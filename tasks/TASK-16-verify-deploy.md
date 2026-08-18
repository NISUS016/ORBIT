# TASK-16: Verify deploy.py compatibility

**Phase**: 3 — Integration  
**Action**: VERIFY (modify only if needed)  
**File**: `D:\ORBIT\scripts\deploy.py`  
**Dependencies**: TASK-11

---

## Read First

- `D:\ORBIT\scripts\deploy.py` — full file
- `D:\ORBIT\backend\llm_config.py` — updated `patch_llm_node` from TASK-11

## Instructions

1. Read `deploy.py` and check how it imports and calls `patch_llm_node`
2. Verify the existing workflow JSONs in `D:\ORBIT\workflows\` use typeVersion 2 HTTP Request nodes
3. Confirm the updated `patch_llm_node()` from TASK-11 is backward compatible (handles typeVersion 2)
4. If any imports or function signatures changed, update the calls
5. Run `python scripts/deploy.py` mentally — trace the code path to ensure no errors

If everything is compatible, no changes needed. If something breaks, fix the import or call.

## Acceptance Criteria

- [ ] `deploy.py` would run without import errors after TASK-11 changes
- [ ] Existing `02_research_agent.json`, `03_summarizer_agent.json`, `04_extractor_agent.json` deploy correctly
- [ ] LLM credentials are properly patched into typeVersion 2 nodes
