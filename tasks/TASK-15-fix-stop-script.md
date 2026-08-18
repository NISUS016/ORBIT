# TASK-15: Fix stop.py to kill process trees

**Phase**: 0 — Bug Fix  
**Action**: MODIFY  
**File**: `D:\ORBIT\scripts\stop.py`  
**Dependencies**: None

---

## Read First

The entire `scripts/stop.py` file.

## Problem

Uses `taskkill /PID <pid> /F` without the `/T` flag. Child processes (n8n workers, uvicorn workers) survive and hold ports.

## Instructions

Find ALL occurrences of `taskkill` in the file. Add the `/T` flag to each one:

**Before**: `taskkill /PID {pid} /F`  
**After**: `taskkill /T /PID {pid} /F`

The `/T` flag kills the entire process tree (parent + all children).

## Acceptance Criteria

- [ ] ALL `taskkill` calls include `/T` flag
- [ ] Running `stop.bat` fully releases all ports (n8n, backend, UI)
