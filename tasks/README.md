# ORBIT Agentic Workflow Generator — Task List

This folder contains atomic tasks for transforming ORBIT into a truly agentic n8n workflow generator.

## Execution Order

| Order | Tasks (parallel within group) | Phase |
|-------|-------------------------------|-------|
| 1 | TASK-01 through TASK-05, TASK-14, TASK-15 | Phase 0: Bug fixes |
| 2 | TASK-06 | Phase 1: Node catalog |
| 3 | TASK-07, TASK-08 | Phase 1: Validator + prompt |
| 4 | TASK-09, TASK-10, TASK-11 | Phase 2: Core rewrite |
| 5 | TASK-12, TASK-13, TASK-16, TASK-17, TASK-18 | Phase 3: Integration |

## File Legend

- **NEW** = File does not exist yet, must be created
- **MODIFY** = Existing file, apply targeted changes
- **REWRITE** = Existing file, replace entirely

## Dependency Graph

```
Phase 0 (all parallel, no deps):
  TASK-01, TASK-02, TASK-03, TASK-04, TASK-05, TASK-14, TASK-15

Phase 1:
  TASK-06 (no deps)
  TASK-07 (needs TASK-06)
  TASK-08 (needs TASK-06)

Phase 2:
  TASK-09 (needs TASK-03, TASK-07, TASK-08)
  TASK-10 (needs TASK-11)
  TASK-11 (no deps)

Phase 3:
  TASK-12 (needs TASK-02, TASK-03, TASK-05, TASK-09, TASK-10, TASK-13)
  TASK-13 (no deps)
  TASK-16 (needs TASK-11)
  TASK-17 (needs TASK-07, TASK-09)
  TASK-18 (needs TASK-01)
```
