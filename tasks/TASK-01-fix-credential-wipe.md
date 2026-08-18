# TASK-01: Fix silent credential wipe in providers.py

**Phase**: 0 — Bug Fix  
**Action**: MODIFY  
**File**: `D:\ORBIT\backend\providers.py`  
**Dependencies**: None

---

## Read First

Read the entire `backend/providers.py` file. Focus on the `_load()` and `_save()` functions.

## Problem

The `_load()` function has a bare `except Exception: pass` that swallows JSON parse errors. If `credentials.json` is corrupted or locked, `_load()` returns empty defaults. A subsequent `_save()` then **overwrites the real file with blank data**, destroying all API keys and webhook URLs.

## Instructions

### Step 1: Fix `_load()`

Find the `_load()` function. It currently has something like:

```python
try:
    data = json.loads(CREDS_FILE.read_text())
except Exception:
    pass
```

Replace with:

```python
try:
    data = json.loads(CREDS_FILE.read_text(encoding="utf-8"))
except FileNotFoundError:
    pass  # File doesn't exist yet, use defaults
except Exception as e:
    print(f"[providers] WARNING: Failed to read {CREDS_FILE}: {e}")
    # If the file exists and has content, don't silently discard it
    if CREDS_FILE.exists() and CREDS_FILE.stat().st_size > 0:
        raise  # Re-raise — don't overwrite valid data with empty defaults
```

### Step 2: Add atomic writes to `_save()`

Add `import shutil` at the top of the file.

In the `_save()` function, before writing:

```python
def _save(data: dict):
    # Backup existing file before overwriting
    if CREDS_FILE.exists() and CREDS_FILE.stat().st_size > 0:
        import shutil
        shutil.copy2(CREDS_FILE, CREDS_FILE.with_suffix(".json.bak"))
    
    # Atomic write: write to temp file, then rename
    tmp_file = CREDS_FILE.with_suffix(".json.tmp")
    tmp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    import os
    os.replace(str(tmp_file), str(CREDS_FILE))
```

## Acceptance Criteria

- [ ] `_load()` no longer silently swallows exceptions with bare `except: pass`
- [ ] `_load()` prints a warning when it can't parse the file
- [ ] `_load()` re-raises if the file exists and has content (don't overwrite valid data)
- [ ] `_load()` still returns defaults silently for `FileNotFoundError` (file doesn't exist yet)
- [ ] `_save()` creates a `.bak` backup before writing
- [ ] `_save()` uses atomic write (write to `.tmp`, then `os.replace()`)
- [ ] All existing `get_*` and `set_*` functions still work correctly
