# TASK-14: Fix requirements.txt

**Phase**: 0 — Bug Fix  
**Action**: MODIFY  
**File**: `D:\ORBIT\backend\requirements.txt`  
**Dependencies**: None

---

## Instructions

Replace the contents with version-pinned dependencies:

```
fastapi>=0.100.0
uvicorn>=0.23.0
httpx>=0.24.0
python-dotenv>=1.0.0
openai>=1.0.0
pydantic>=2.0.0
```

Note: `pydantic` is used directly in `routes.py` but was missing. `requests` is NOT used (the codebase uses `httpx`), so do NOT add it.

## Acceptance Criteria

- [ ] `pydantic` is explicitly listed
- [ ] All packages have minimum version constraints
- [ ] `requests` is NOT in the file
- [ ] `pip install -r requirements.txt` succeeds
